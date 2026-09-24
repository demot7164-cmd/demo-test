"""
Pydantic schemas for DOCX translation workflow.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    """Top 10 most spoken languages by native speakers."""
    ENGLISH = "en"
    MANDARIN = "zh"
    HINDI = "hi"
    SPANISH = "es"
    FRENCH = "fr"
    ARABIC = "ar"
    BENGALI = "bn"
    RUSSIAN = "ru"
    PORTUGUESE = "pt"
    INDONESIAN = "id"


class DOCXElementType(str, Enum):
    """Types of elements that can be preserved in DOCX."""
    PARAGRAPH = "paragraph"
    TABLE = "table"
    HEADER = "header"
    FOOTER = "footer"


class TranslatableText(BaseModel):
    """Text with its formatting context for translation."""
    text: str


class TranslationInput(BaseModel):
    """Input schema for the translation workflow."""
    docx_bytes: bytes = Field(..., description="Raw DOCX file bytes")
    target_language: Language = Field(..., description="Target language for translation")
    preserve_formatting: bool = Field(
        default=True, description="Whether to preserve all formatting"
    )
    translate_headers_footers: bool = Field(
        default=True, description="Whether to translate headers and footers"
    )
    translate_table_text: bool = Field(
        default=True, description="Whether to translate table content"
    )


class TranslationResult(BaseModel):
    """Output schema for the translation workflow."""
    translated_docx_bytes: bytes = Field(..., description="Translated DOCX file bytes")
    original_language: Optional[str] = Field(
        default=None, description="Detected original language"
    )
    translation_summary: Dict[str, Any] = Field(
        default_factory=dict, description="Summary of translation statistics"
    )
    processing_time_seconds: float = Field(
        default=0.0, description="Total processing time"
    )


class TranslationChunk(BaseModel):
    """Chunk of text for batch translation."""
    text: str
    element_type: DOCXElementType
    element_index: int
    sub_element_index: Optional[int] = None


# Simplified content structure for tables
# tables is a list of list of list of TranslatableText
# tables[table_index][row_index][cell_index] = TranslatableText
class DOCXContent(BaseModel):
    """Complete DOCX content structure."""
    paragraphs: List[TranslatableText] = Field(default_factory=list)
    tables: List[List[List[TranslatableText]]] = Field(default_factory=list)
    headers: List[List[TranslatableText]] = Field(default_factory=list)
    footers: List[List[TranslatableText]] = Field(default_factory=list)
