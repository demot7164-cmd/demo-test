"""
Main workflow for DOCX translation.
Preserves all formatting including tables, headers, footers, styles, and images.
"""

import time
from typing import Any, Dict, List, Optional

import mistralai.workflows as workflows

from src.models.schemas import (
    DOCXContent,
    DOCXElementType,
    Language,
    TranslationChunk,
    TranslationInput,
    TranslationResult,
)
from src.workflows.activities import (
    extract_docx_content,
    rebuild_docx,
    translate_content_chunks,
)


@workflows.workflow.define(
    name="docx-translation",
    workflow_display_name="DOCX Translation Workflow",
    workflow_description=(
        "Translate DOCX files to one of the top 10 most spoken languages "
        "while preserving all formatting including tables, headers, footers, "
        "styles, and images."
    ),
    enforce_determinism=True,
)
class DOCXTranslationWorkflow:
    """
    Main workflow class for DOCX translation.
    
    This workflow:
    1. Extracts all content from the DOCX file
    2. Splits content into translatable chunks
    3. Translates each chunk to the target language
    4. Rebuilds the DOCX with translated content and original formatting
    """

    @workflows.workflow.entrypoint
    async def run(
        self,
        input: TranslationInput,
        mistral_api_key: Optional[str] = None,
    ) -> TranslationResult:
        """
        Main entry point for the workflow.
        
        Args:
            input: TranslationInput containing DOCX bytes and target language
            mistral_api_key: Optional Mistral API key for translation
            
        Returns:
            TranslationResult with translated DOCX bytes
        """
        start_time = time.time()
        
        # Step 1: Extract all content from DOCX
        logger = workflows.workflow.logger
        logger.info(f"Starting DOCX translation to {input.target_language.value}")
        
        content: DOCXContent = await extract_docx_content(input)
        logger.info(f"Extracted {len(content.paragraphs)} paragraphs, {len(content.tables)} tables")
        
        # Step 2: Create translation chunks
        chunks: List[TranslationChunk] = await self._create_translation_chunks(content, input)
        logger.info(f"Created {len(chunks)} translation chunks")
        
        # Step 3: Translate all chunks
        translated_chunks: List[TranslationChunk] = await translate_content_chunks(
            chunks,
            input.target_language,
            mistral_api_key,
        )
        logger.info(f"Translated all chunks")
        
        # Step 4: Rebuild DOCX with translated content
        translated_docx_bytes: bytes = await rebuild_docx(content, translated_chunks)
        logger.info(f"Rebuilt DOCX with translated content")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Create result
        result = TranslationResult(
            translated_docx_bytes=translated_docx_bytes,
            original_language=self._detect_language(content),
            translation_summary={
                "paragraphs_translated": len([c for c in chunks if c.element_type == DOCXElementType.PARAGRAPH]),
                "tables_translated": len([c for c in chunks if c.element_type == DOCXElementType.TABLE]),
                "headers_footers_translated": len([c for c in chunks if c.element_type in [DOCXElementType.HEADER, DOCXElementType.FOOTER]]),
                "total_chunks": len(chunks),
            },
            processing_time_seconds=processing_time,
        )
        
        logger.info(f"Translation completed in {processing_time:.2f} seconds")
        return result
    
    async def _create_translation_chunks(
        self,
        content: DOCXContent,
        input: TranslationInput,
    ) -> List[TranslationChunk]:
        """
        Create translation chunks from extracted content.
        
        Each chunk represents a piece of text that needs translation,
        along with its context (element type, position).
        """
        chunks: List[TranslationChunk] = []
        chunk_index = 0
        
        # Add paragraphs
        for para_idx, para in enumerate(content.paragraphs):
            if para.text.strip():
                chunks.append(TranslationChunk(
                    text=para.text,
                    element_type=DOCXElementType.PARAGRAPH,
                    element_index=para_idx,
                ))
                chunk_index += 1
        
        # Add tables
        for table_idx, table in enumerate(content.tables):
            for row_idx, row in enumerate(table.rows):
                for col_idx, cell in enumerate(row):
                    if cell.text.strip():
                        chunks.append(TranslationChunk(
                            text=cell.text,
                            element_type=DOCXElementType.TABLE,
                            element_index=table_idx,
                            sub_element_index=row_idx * 1000 + col_idx,  # Unique per cell
                        ))
                        chunk_index += 1
        
        # Add headers if enabled
        if input.translate_headers_footers:
            for section_idx, section_headers in enumerate(content.headers):
                for para_idx, para in enumerate(section_headers):
                    if para.text.strip():
                        chunks.append(TranslationChunk(
                            text=para.text,
                            element_type=DOCXElementType.HEADER,
                            element_index=section_idx,
                            sub_element_index=para_idx,
                        ))
                        chunk_index += 1
        
        # Add footers if enabled
        if input.translate_headers_footers:
            for section_idx, section_footers in enumerate(content.footers):
                for para_idx, para in enumerate(section_footers):
                    if para.text.strip():
                        chunks.append(TranslationChunk(
                            text=para.text,
                            element_type=DOCXElementType.FOOTER,
                            element_index=section_idx,
                            sub_element_index=para_idx,
                        ))
                        chunk_index += 1
        
        return chunks
    
    def _detect_language(self, content: DOCXContent) -> str:
        """
        Detect the original language from content.
        Simple heuristic based on common words.
        """
        # Collect all text
        all_text = []
        for para in content.paragraphs:
            all_text.append(para.text)
        for table in content.tables:
            for row in table.rows:
                for cell in row:
                    all_text.append(cell.text)
        
        text = " ".join(all_text).lower()
        
        # Simple language detection
        language_indicators = {
            "en": ["the", "and", "of", "to", "in"],
            "fr": ["le", "la", "les", "de", "et"],
            "es": ["el", "la", "los", "las", "de"],
            "de": ["der", "die", "das", "und", "in"],
            "it": ["il", "la", "i", "le", "di"],
            "pt": ["o", "a", "os", "as", "de"],
            "ru": ["и", "в", "не", "на", "я"],
            "zh": ["的", "了", "和", "是", "在"],
            "ar": ["ال", "و", "في", "من", "إلى"],
            "hi": ["का", "की", "में", "और", "है"],
        }
        
        for lang, indicators in language_indicators.items():
            count = sum(text.count(indicator) for indicator in indicators)
            if count > 5:  # Threshold
                return lang
        
        return "unknown"


@workflows.workflow.define(
    name="docx-translation-simple",
    workflow_display_name="Simple DOCX Translation",
    workflow_description=(
        "Simplified version of DOCX translation workflow for testing purposes."
    ),
)
class SimpleDOCXTranslationWorkflow:
    """
    Simplified workflow for testing without full formatting preservation.
    """

    @workflows.workflow.entrypoint
    async def run(
        self,
        docx_bytes: bytes,
        target_language: str = "fr",
    ) -> bytes:
        """
        Simple translation workflow.
        
        Args:
            docx_bytes: Raw DOCX file bytes
            target_language: Target language code
            
        Returns:
            Translated DOCX bytes
        """
        from docx import Document
        import io
        
        # Extract text
        doc = Document(io.BytesIO(docx_bytes))
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        
        # Simple translation (mock for testing)
        translated_texts = []
        for text in full_text:
            translated_texts.append(f"[Translated to {target_language}] {text}")
        
        # Create new document
        new_doc = Document()
        for text in translated_texts:
            new_doc.add_paragraph(text)
        
        # Save
        buffer = io.BytesIO()
        new_doc.save(buffer)
        buffer.seek(0)
        
        return buffer.read()
