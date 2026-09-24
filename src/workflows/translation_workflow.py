"""
Main DOCX translation workflow.
Inherits from InteractiveWorkflow for form-based input.
"""

from typing import Any

from mistralai.workflows import workflow
from mistralai.workflows.conversational import (
    FileField,
    FileWithMetadataValue,
    FormInput,
    ChatAssistantWorkflowOutput,
    TextOutput,
    TodoList,
    TodoListItem,
)

from src.models.schemas import TargetLanguage, TranslationInput
from src.workflows.activities import (
    download_file,
    extract_text_with_runs,
    translate_with_mistral,
    replace_text_in_docx,
    upload_file,
    get_signed_url,
)


class Formulaire(FormInput):
    """Form for document upload."""
    document: FileWithMetadataValue = FileField(
        description="Document Word à traduire",
        include_metadata=True,
    )


@workflow.define(
    name="docx-translation",
    workflow_display_name="DOCX Translation",
    workflow_description="Translate DOCX files while preserving all formatting",
)
class DocxTranslation(workflows.InteractiveWorkflow):
    """
    DOCX Translation Workflow.
    
    Steps:
    1. Show form to upload DOCX file
    2. Extract all text elements with run tags
    3. Translate using Mistral API (mistral-medium-latest)
    4. Replace text in original DOCX preserving formatting
    5. Upload result and return signed URL
    """

    @workflow.entrypoint
    async def run(self, input: TranslationInput) -> Any:
        """Main workflow entry point."""
        # Initialize todo list
        todos = TodoList()
        todos.add(TodoListItem(description="Demander le document à traduire", status="in_progress"))
        
        # Wait for document upload
        form_data = await self.wait_for_input(Formulaire, label="Document à traduire")
        
        todos.update(0, status="completed")
        todos.add(TodoListItem(description="Télécharger le fichier", status="in_progress"))
        
        # Download the file
        file_url = form_data.document.url
        docx_bytes = await download_file(file_url)
        
        todos.update(1, status="completed")
        todos.add(TodoListItem(description="Extraire le texte avec les runs", status="in_progress"))
        
        # Extract text with run tags
        elements = await extract_text_with_runs(docx_bytes)
        
        todos.update(2, status="completed")
        todos.add(TodoListItem(description=f"Traduire vers {input.langue_cible.value}", status="in_progress"))
        
        # Translate with Mistral
        translated_elements = await translate_with_mistral(elements, input.langue_cible.value)
        
        todos.update(3, status="completed")
        todos.add(TodoListItem(description="Remplacer le texte dans le DOCX", status="in_progress"))
        
        # Replace text in DOCX
        translated_docx_bytes = await replace_text_in_docx(docx_bytes, translated_elements)
        
        todos.update(4, status="completed")
        todos.add(TodoListItem(description="Uploader le fichier traduit", status="in_progress"))
        
        # Upload file
        import mistralai
        client = mistralai.Mistral()
        file_id = await upload_file(client, translated_docx_bytes, f"translated_{input.langue_cible.value}.docx")
        
        todos.update(5, status="completed")
        todos.add(TodoListItem(description="Générer le lien de téléchargement", status="in_progress"))
        
        # Get signed URL
        signed_url = await get_signed_url(client, file_id)
        
        todos.update(6, status="completed")
        
        # Return output
        return ChatAssistantWorkflowOutput(
            content=[TextOutput(text=f"Traduction terminée ! Téléchargez votre fichier: {signed_url}")]
        )
