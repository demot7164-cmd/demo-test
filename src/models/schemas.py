"""
Pydantic schemas for DOCX translation workflow.
"""

from enum import Enum

from pydantic import BaseModel, Field


class TargetLanguage(str, Enum):
    """Supported target languages."""
    EN = "en"
    ES = "es"
    DE = "de"
    IT = "it"
    PT = "pt"
    RU = "ru"
    ZH = "zh"
    JA = "ja"
    AR = "ar"
    HI = "hi"


class TranslationInput(BaseModel):
    """Input schema for the translation workflow."""
    langue_cible: TargetLanguage = Field(
        ...,
        description="Langue cible pour la traduction"
    )
