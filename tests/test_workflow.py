"""
Tests for DOCX translation workflow.
"""

import asyncio
import base64
import io
import tempfile
import pytest
from pathlib import Path

from docx import Document

from src.workflows.translation_workflow import SimpleDOCXTranslationWorkflow


@pytest.mark.asyncio
async def test_simple_workflow():
    """Test the simple translation workflow."""
    # Create a simple DOCX for testing
    doc = Document()
    doc.add_heading('Test Document', 0)
    doc.add_paragraph('This is a test paragraph.')
    doc.add_paragraph('This is another paragraph.')
    
    # Add a table
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = 'Header 1'
    table.cell(0, 1).text = 'Header 2'
    table.cell(1, 0).text = 'Data 1'
    table.cell(1, 1).text = 'Data 2'
    
    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_bytes = buffer.read()
    
    # Test workflow
    workflow = SimpleDOCXTranslationWorkflow()
    result = await workflow.run(docx_bytes, 'fr')
    
    # Verify result is bytes
    assert isinstance(result, bytes)
    assert len(result) > 0
    
    # Save result and verify it's a valid DOCX
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        f.write(result)
        temp_path = f.name
    
    try:
        # Try to open the result as a DOCX
        result_doc = Document(temp_path)
        assert len(result_doc.paragraphs) > 0
        
        # Check that translation placeholder is present
        full_text = '\n'.join([p.text for p in result_doc.paragraphs])
        assert '[Translated to fr]' in full_text
        
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_workflow_with_formatting():
    """Test workflow preserves basic formatting."""
    # Create DOCX with formatting
    doc = Document()
    
    # Add paragraph with bold
    p = doc.add_paragraph('This is bold text.')
    run = p.runs[0]
    run.bold = True
    
    # Add paragraph with italic
    p = doc.add_paragraph('This is italic text.')
    run = p.runs[0]
    run.italic = True
    
    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_bytes = buffer.read()
    
    # Test workflow
    workflow = SimpleDOCXTranslationWorkflow()
    result = await workflow.run(docx_bytes, 'es')
    
    # Verify result
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_workflow_with_tables():
    """Test workflow handles tables correctly."""
    # Create DOCX with table
    doc = Document()
    
    # Add a 3x3 table
    table = doc.add_table(rows=3, cols=3)
    for i in range(3):
        for j in range(3):
            table.cell(i, j).text = f'Cell {i},{j}'
    
    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_bytes = buffer.read()
    
    # Test workflow
    workflow = SimpleDOCXTranslationWorkflow()
    result = await workflow.run(docx_bytes, 'de')
    
    # Verify result
    assert isinstance(result, bytes)
    assert len(result) > 0
    
    # Open result and check table
    result_doc = Document(io.BytesIO(result))
    assert len(result_doc.tables) == 1
    assert len(result_doc.tables[0].rows) == 3
    assert len(result_doc.tables[0].columns) == 3


@pytest.mark.asyncio
async def test_workflow_with_headers():
    """Test workflow handles headers."""
    # Create DOCX with header
    doc = Document()
    
    # Add header
    header = doc.sections[0].header
    header_para = header.add_paragraph('This is a header')
    
    # Add content
    doc.add_paragraph('Main content')
    
    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_bytes = buffer.read()
    
    # Test workflow
    workflow = SimpleDOCXTranslationWorkflow()
    result = await workflow.run(docx_bytes, 'pt')
    
    # Verify result
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_workflow_multiple_languages():
    """Test workflow with different target languages."""
    # Create simple DOCX
    doc = Document()
    doc.add_paragraph('Test text')
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_bytes = buffer.read()
    
    # Test with multiple languages
    languages = ['fr', 'es', 'de', 'it', 'pt']
    workflow = SimpleDOCXTranslationWorkflow()
    
    for lang in languages:
        result = await workflow.run(docx_bytes, lang)
        assert isinstance(result, bytes)
        assert len(result) > 0
        
        # Verify translation placeholder
        result_doc = Document(io.BytesIO(result))
        full_text = '\n'.join([p.text for p in result_doc.paragraphs])
        assert f'[Translated to {lang}]' in full_text
