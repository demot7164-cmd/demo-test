"""
Worker for DOCX translation workflow.
Provides an interface callable from Vibe Work via workflow execution.
"""

import base64
import logging
import os
from typing import Any, Dict, Optional

import mistralai.workflows as workflows
from mistralai.workflows import run_worker, workflow
from pydantic import BaseModel, Field

from src.models.schemas import Language, TranslationInput, TranslationResult
from src.workflows.translation_workflow import DOCXTranslationWorkflow, SimpleDOCXTranslationWorkflow

logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("WORKFLOW_TIMEOUT", "600"))  # 10 minutes
DEFAULT_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRIES", "3"))


class DOCXTranslationInput(BaseModel):
    """Input schema for direct workflow execution (callable from Vibe Work)."""
    docx_base64: str = Field(
        ...,
        description="DOCX file encoded as base64 string",
        min_length=1,
    )
    target_language: Language = Field(
        ...,
        description="Target language for translation (top 10 most spoken)",
    )
    preserve_formatting: bool = Field(
        default=True,
        description="Whether to preserve all formatting (tables, headers, etc.)",
    )
    translate_headers_footers: bool = Field(
        default=True,
        description="Whether to translate headers and footers",
    )
    translate_table_text: bool = Field(
        default=True,
        description="Whether to translate table content",
    )
    mistral_api_key: Optional[str] = Field(
        default=None,
        description="Mistral API key for translation (optional, falls back to env var)",
    )


class DOCXTranslationOutput(BaseModel):
    """Output schema for the workflow."""
    translated_docx_base64: str = Field(
        ...,
        description="Translated DOCX file encoded as base64 string",
    )
    original_language: Optional[str] = Field(
        default=None,
        description="Detected original language",
    )
    translation_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of translation statistics",
    )
    processing_time_seconds: float = Field(
        default=0.0,
        description="Total processing time",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if translation failed",
    )


@workflows.workflow.define(
    name="docx-translator",
    workflow_display_name="DOCX Translator",
    workflow_description=(
        "Translate DOCX files to one of the top 10 most spoken languages "
        "while preserving all formatting including tables, headers, footers, "
        "styles, and images. Callable from Vibe Work."
    ),
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
)
class DOCXTranslatorWorkflow:
    """
    Workflow for translating DOCX files, callable from Vibe Work.
    
    This workflow wraps the DOCXTranslationWorkflow and provides
    a user-friendly interface with base64-encoded input/output.
    """

    @workflows.workflow.entrypoint(
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        retry_policy=workflows.RetryPolicy(
            max_attempts=DEFAULT_RETRY_ATTEMPTS,
            backoff_coefficient=2.0,
        ),
    )
    async def run(self, input: DOCXTranslationInput) -> DOCXTranslationOutput:
        """
        Translate a DOCX file.
        
        Args:
            input: DOCXTranslationInput containing base64-encoded DOCX and translation options
            
        Returns:
            DOCXTranslationOutput with base64-encoded translated DOCX
        """
        try:
            # Validate input
            if not input.docx_base64:
                return DOCXTranslationOutput(
                    translated_docx_base64="",
                    error="docx_base64 is required",
                    processing_time_seconds=0.0,
                )
            
            # Decode base64 DOCX
            try:
                docx_bytes = base64.b64decode(input.docx_base64)
            except Exception as e:
                return DOCXTranslationOutput(
                    translated_docx_base64="",
                    error=f"Invalid base64 encoding: {str(e)}",
                    processing_time_seconds=0.0,
                )
            
            # Create translation input
            translation_input = TranslationInput(
                docx_bytes=docx_bytes,
                target_language=input.target_language,
                preserve_formatting=input.preserve_formatting,
                translate_headers_footers=input.translate_headers_footers,
                translate_table_text=input.translate_table_text,
            )
            
            # Execute the main translation workflow
            main_workflow = DOCXTranslationWorkflow()
            result: TranslationResult = await main_workflow.run(translation_input)
            # Encode result to base64
            translated_docx_base64 = base64.b64encode(result.translated_docx_bytes).decode("utf-8")
            
            # Return output
            return DOCXTranslationOutput(
                translated_docx_base64=translated_docx_base64,
                original_language=result.original_language,
                translation_summary=result.translation_summary,
                processing_time_seconds=result.processing_time_seconds,
                error=None,
            )
            
        except Exception as e:
            logger.error(f"Error in DOCX translation: {str(e)}", exc_info=True)
            return DOCXTranslationOutput(
                translated_docx_base64="",
                original_language=None,
                translation_summary={},
                processing_time_seconds=0.0,
                error=str(e),
            )


# Export for worker registration
# Note: In Mistral Workflows, workflows are registered automatically when imported
# The worker is started via run_worker() which discovers workflows in the package

# Register workflows by importing them
from src.workflows.translation_workflow import DOCXTranslationWorkflow, SimpleDOCXTranslationWorkflow

# The DOCXTranslatorWorkflow is defined above and will be registered automatically

logger.info("DOCX Translation workflows are ready for registration")
