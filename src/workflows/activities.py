"""
Activities for DOCX translation workflow.
Handles extraction, translation, and reconstruction of DOCX files
with table and header/footer preservation.
"""

import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from mistralai import client
from docx import Document

import mistralai.workflows as workflows

from src.models.schemas import (
    DOCXContent,
    DOCXElementType,
    Language,
    TranslatableText,
    TranslationChunk,
    TranslationInput,
)

logger = logging.getLogger(__name__)

# Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MAX_TOKENS_PER_REQUEST = 30000  # Mistral limit is 32K, keep margin
TOKEN_ESTIMATION_RATIO = 4  # 1 token ≈ 4 characters for estimation


class TranslationError(Exception):
    """Custom exception for translation failures."""
    pass


class APIRateLimitError(TranslationError):
    """Rate limit exceeded."""
    pass


class APIAuthenticationError(TranslationError):
    """Authentication failed."""
    pass


@workflows.activity(
    name="extract_docx_content",
    retry_policy_max_attempts=3,
)
async def extract_docx_content(input: TranslationInput) -> DOCXContent:
    """
    Extract all content from DOCX file.
    Handles paragraphs, tables, headers, footers.
    """
    docx_bytes = input.docx_bytes
    doc = Document(io.BytesIO(docx_bytes))
    
    content = DOCXContent()
    
    # Extract main document paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            content.paragraphs.append(TranslatableText(text=para.text))
    
    # Extract tables
    for table in doc.tables:
        table_rows = []
        for row in table.rows:
            row_cells = []
            for cell in row.cells:
                cell_text = '\n'.join([p.text for p in cell.paragraphs if p.text.strip()])
                if cell_text.strip():
                    row_cells.append(TranslatableText(text=cell_text))
            if row_cells:
                table_rows.append(row_cells)
        if table_rows:
            content.tables.append(table_rows)
    
    # Extract headers
    if input.translate_headers_footers:
        for section in doc.sections:
            if section.header:
                header_paras = []
                for para in section.header.paragraphs:
                    if para.text.strip():
                        header_paras.append(TranslatableText(text=para.text))
                if header_paras:
                    content.headers.append(header_paras)
    
    # Extract footers
    if input.translate_headers_footers:
        for section in doc.sections:
            if section.footer:
                footer_paras = []
                for para in section.footer.paragraphs:
                    if para.text.strip():
                        footer_paras.append(TranslatableText(text=para.text))
                if footer_paras:
                    content.footers.append(footer_paras)
    
    return content


def _get_language_name(language_code: str) -> str:
    """Get full language name from code."""
    language_names = {
        "en": "English", "zh": "Chinese", "hi": "Hindi", "es": "Spanish",
        "fr": "French", "ar": "Arabic", "bn": "Bengali", "ru": "Russian",
        "pt": "Portuguese", "id": "Indonesian",
    }
    return language_names.get(language_code, language_code)


def _estimate_token_count(text: str) -> int:
    """Estimate token count for a text."""
    return len(text.encode('utf-8')) // TOKEN_ESTIMATION_RATIO


def _create_translation_batches(
    chunks: List[TranslationChunk],
    max_tokens: int = MAX_TOKENS_PER_REQUEST,
) -> List[List[TranslationChunk]]:
    """
    Group chunks into batches that respect token limits.
    Each batch will be sent as a single API request.
    """
    batches = []
    current_batch: List[TranslationChunk] = []
    current_token_count = 0
    
    for chunk in chunks:
        if not chunk.text.strip():
            # Empty chunks go through without translation
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_token_count = 0
            continue
        
        chunk_tokens = _estimate_token_count(chunk.text)
        
        # Account for prompt overhead (~500 tokens for system prompt + formatting)
        prompt_overhead = 500
        total_with_chunk = current_token_count + chunk_tokens + prompt_overhead
        
        if total_with_chunk > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_token_count = 0
        
        current_batch.append(chunk)
        current_token_count += chunk_tokens
    
    if current_batch:
        batches.append(current_batch)
    
    return batches


def _build_translation_prompt(
    texts: List[str],
    target_language: Language,
) -> str:
    """Build prompt for batch translation."""
    lang_name = _get_language_name(target_language.value)
    
    # Create numbered list for clear separation
    numbered_texts = []
    for i, text in enumerate(texts, 1):
        numbered_texts.append(f"{i}. {text}")
    
    texts_joined = "\n".join(numbered_texts)
    
    return f"""Vous êtes un traducteur professionnel. Traduisiez chaque texte suivant en {lang_name}.
Conservez le ton, le style et la structure originale.
Ne traduisez que le texte, sans ajouter d'explications, de commentaires ou de numéros.
Répondez avec les traductions dans le même ordre, séparées par des sauts de ligne.

Textes à traduire:
{texts_joined}

Traductions:"""


def _parse_batch_translations(
    response_text: str,
    num_texts: int,
) -> List[str]:
    """Parse translations from API response."""
    # Split by newlines and filter empty lines
    lines = [line.strip() for line in response_text.strip().split('\n') if line.strip()]
    
    # Take first num_texts lines
    translations = lines[:num_texts]
    
    # If we got fewer translations than expected, pad with empty strings
    while len(translations) < num_texts:
        translations.append("")
    
    return translations


@workflows.activity(
    name="translate_content_chunks",
    retry_policy_max_attempts=5,
    retry_policy_backoff_coefficient=2.0,
)
async def translate_content_chunks(
    chunks: List[TranslationChunk],
    target_language: Language,
    api_key: Optional[str] = None,
) -> List[TranslationChunk]:
    """
    Translate content chunks using Mistral API.
    Handles token limits with intelligent batching.
    
    Args:
        chunks: List of TranslationChunk to translate
        target_language: Target language for translation
        api_key: Optional Mistral API key (falls back to env var)
        
    Returns:
        List of TranslationChunk with translated text
        
    Raises:
        TranslationError: If translation fails
        APIAuthenticationError: If API key is invalid
        APIRateLimitError: If rate limit is exceeded
    """
    # Get API key
    effective_api_key = api_key or MISTRAL_API_KEY
    if not effective_api_key:
        raise APIAuthenticationError("MISTRAL_API_KEY is required")
    
    # Separate empty chunks (no need to translate)
    empty_chunks = [c for c in chunks if not c.text.strip()]
    non_empty_chunks = [c for c in chunks if c.text.strip()]
    
    if not non_empty_chunks:
        return chunks
    
    # Create batches respecting token limits
    batches = _create_translation_batches(non_empty_chunks, MAX_TOKENS_PER_REQUEST)
    
    logger.info(f"Translating {len(non_empty_chunks)} chunks in {len(batches)} batches")
    
    # Initialize client
    api_client = client.Mistral(api_key=effective_api_key)
    
    # Process batches
    all_translated_chunks: List[TranslationChunk] = []
    
    for batch_idx, batch in enumerate(batches):
        logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} with {len(batch)} chunks")
        
        # Extract texts for this batch
        batch_texts = [chunk.text for chunk in batch]
        
        # Build prompt
        prompt = _build_translation_prompt(batch_texts, target_language)
        
        # Estimate tokens
        prompt_tokens = _estimate_token_count(prompt)
        logger.debug(f"Batch {batch_idx}: Prompt tokens ~{prompt_tokens}")
        
        try:
            # Call Mistral API
            response = await api_client.chat.complete_async(
                model=MISTRAL_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"Vous êtes un traducteur professionnel. Traduisiez en {_get_language_name(target_language.value)}. Répondez uniquement avec la traduction, sans explications."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=MAX_TOKENS_PER_REQUEST,
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            translations = _parse_batch_translations(response_text, len(batch_texts))
            
            # Create translated chunks
            for chunk, translation in zip(batch, translations):
                all_translated_chunks.append(TranslationChunk(
                    text=translation,
                    element_type=chunk.element_type,
                    element_index=chunk.element_index,
                    sub_element_index=chunk.sub_element_index,
                ))
                
        except Exception as e:
            error_msg = str(e)
            if "rate limit" in error_msg.lower():
                raise APIRateLimitError(f"Rate limit exceeded: {error_msg}")
            elif "invalid" in error_msg.lower() or "unauthorized" in error_msg.lower():
                raise APIAuthenticationError(f"Authentication failed: {error_msg}")
            else:
                logger.error(f"Translation failed for batch {batch_idx}: {error_msg}")
                raise TranslationError(f"Translation error: {error_msg}")
    
    # Merge back with empty chunks
    result_chunks = []
    empty_idx = 0
    non_empty_idx = 0
    
    for original_chunk in chunks:
        if not original_chunk.text.strip():
            result_chunks.append(empty_chunks[empty_idx])
            empty_idx += 1
        else:
            result_chunks.append(all_translated_chunks[non_empty_idx])
            non_empty_idx += 1
    
    return result_chunks


@workflows.activity(
    name="rebuild_docx",
    retry_policy_max_attempts=3,
)
async def rebuild_docx(
    original_content: DOCXContent,
    translated_chunks: List[TranslationChunk],
) -> bytes:
    """
    Rebuild DOCX file from original structure with translated content.
    """
    new_doc = Document()
    
    # Clear default paragraph
    if new_doc.paragraphs:
        new_doc.paragraphs[0].clear()
    
    # Organize translated chunks by element
    para_chunks = {c.element_index: c for c in translated_chunks if c.element_type == DOCXElementType.PARAGRAPH}
    table_chunks = {}
    for c in translated_chunks:
        if c.element_type == DOCXElementType.TABLE:
            if c.element_index not in table_chunks:
                table_chunks[c.element_index] = {}
            table_chunks[c.element_index][c.sub_element_index or 0] = c
    
    # Rebuild paragraphs with translated text
    for idx, original_para in enumerate(original_content.paragraphs):
        if idx in para_chunks:
            new_doc.add_paragraph(para_chunks[idx].text)
        else:
            new_doc.add_paragraph(original_para.text)
    
    # Rebuild tables with translated text
    for table_idx, table_rows in enumerate(original_content.tables):
        table = new_doc.add_table(rows=len(table_rows), cols=len(table_rows[0]) if table_rows else 1)
        for row_idx, row_cells in enumerate(table_rows):
            for col_idx, cell in enumerate(row_cells):
                chunk_key = row_idx * 1000 + col_idx
                if table_idx in table_chunks and chunk_key in table_chunks[table_idx]:
                    table.cell(row_idx, col_idx).text = table_chunks[table_idx][chunk_key].text
                else:
                    table.cell(row_idx, col_idx).text = cell.text
    
    # Save to bytes
    buffer = io.BytesIO()
    new_doc.save(buffer)
    buffer.seek(0)
    
    return buffer.read()
