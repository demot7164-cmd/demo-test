"""
Activities for DOCX translation workflow.
Handles extraction, translation, and reconstruction of DOCX files
with table and header/footer preservation.
"""

import io
import logging
from typing import Any, Dict, List, Optional

import httpx
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
    Translate content chunks using mock translation.
    In production, this would call the Mistral API.
    """
    language_names = {
        "en": "English", "zh": "Chinese", "hi": "Hindi", "es": "Spanish",
        "fr": "French", "ar": "Arabic", "bn": "Bengali", "ru": "Russian",
        "pt": "Portuguese", "id": "Indonesian",
    }
    
    translated_chunks = []
    for chunk in chunks:
        if not chunk.text.strip():
            translated_chunks.append(chunk)
            continue
        
        translated_text = f"[Translated to {language_names.get(target_language.value, target_language.value)}] {chunk.text}"
        
        translated_chunks.append(TranslationChunk(
            text=translated_text,
            element_type=chunk.element_type,
            element_index=chunk.element_index,
            sub_element_index=chunk.sub_element_index,
        ))
    
    return translated_chunks


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
