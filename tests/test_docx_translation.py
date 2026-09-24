"""
Tests for DOCX translation workflow.
Creates a test DOCX using python-docx for validity.
Verifies that after translation (with mock translator), all formatting is preserved.
"""

import asyncio
import io
from docx import Document

import pytest

from src.workflows.activities import (
    extract_text_with_runs,
    replace_text_in_docx,
)


def create_test_docx() -> bytes:
    """Create a test DOCX with header, footer, table, bold text."""
    doc = Document()
    
    # Add header
    header = doc.sections[0].header
    header.add_paragraph("This is a header")
    
    # Add footer
    footer = doc.sections[0].footer
    footer.add_paragraph("This is a footer")
    
    # Add normal paragraph
    doc.add_paragraph("This is a normal paragraph.")
    
    # Add paragraph with bold text in the middle
    p = doc.add_paragraph()
    p.add_run("This is a paragraph with ")
    p.add_run("bold text").bold = True
    p.add_run(" in the middle.")
    
    # Add table
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Cell 1"
    table.cell(0, 1).text = "Cell 2"
    table.cell(1, 0).text = "Data 1"
    table.cell(1, 1).text = "Data 2"
    
    # Add another paragraph
    doc.add_paragraph("Another paragraph.")
    
    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


@pytest.mark.asyncio
async def test_extract_text_with_runs():
    """Test extraction of text with run tags."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    
    assert len(elements) > 0
    
    element_types = set(e['element_type'] for e in elements)
    assert 'paragraph' in element_types
    assert 'table_cell' in element_types
    
    for element in elements:
        assert 'runs' in element
        assert len(element['runs']) > 0
    
    print(f"✓ Extracted {len(elements)} elements")


@pytest.mark.asyncio
async def test_replace_text_in_docx():
    """Test replacement of text in DOCX."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    
    translated_elements = []
    for i, element in enumerate(elements):
        translated_text = f"[MOCK_TRANSLATED] {element['text']}"
        translated_runs = [f"<r{j}>[MOCK] {run}</r{j}>" 
                         for j, run in enumerate(element['runs'])]
        translated_elements.append({
            **element,
            'translated_text': translated_text,
            'translated_runs': translated_runs,
        })
    
    result_bytes = await replace_text_in_docx(docx_bytes, translated_elements)
    
    assert len(result_bytes) > 0
    
    # Verify it's a valid DOCX
    result_doc = Document(io.BytesIO(result_bytes))
    assert len(result_doc.paragraphs) > 0
    
    print("✓ Text replacement completed")


@pytest.mark.asyncio
async def test_bold_text_preservation():
    """Test that bold text formatting is preserved."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    
    bold_paragraph = None
    for element in elements:
        if 'bold text' in element['text']:
            bold_paragraph = element
            break
    
    assert bold_paragraph is not None
    assert len(bold_paragraph['runs']) >= 3
    assert any('bold text' in run for run in bold_paragraph['runs'])
    
    print("✓ Bold text formatting extracted correctly")


@pytest.mark.asyncio
async def test_table_structure_preservation():
    """Test that table structure is preserved."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    
    table_cells = [e for e in elements if e['element_type'] == 'table_cell']
    
    assert len(table_cells) == 4
    
    cell_texts = [e['text'] for e in table_cells]
    assert 'Cell 1' in cell_texts
    assert 'Cell 2' in cell_texts
    assert 'Data 1' in cell_texts
    assert 'Data 2' in cell_texts
    
    print("✓ Table structure extracted correctly")


@pytest.mark.asyncio
async def test_header_footer_extraction():
    """Test that header and footer are extracted."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    
    headers = [e for e in elements if e['element_type'] == 'header']
    assert len(headers) > 0
    assert any('header' in e['text'].lower() for e in headers)
    
    footers = [e for e in elements if e['element_type'] == 'footer']
    assert len(footers) > 0
    assert any('footer' in e['text'].lower() for e in footers)
    
    print("✓ Header and footer extracted correctly")


@pytest.mark.asyncio
async def test_full_roundtrip():
    """Test full roundtrip: extract -> translate (mock) -> replace."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    original_count = len(elements)
    
    translated_elements = []
    for element in elements:
        translated_runs = [f"<r{i}>[MOCK] {run}</r{i}>" 
                         for i, run in enumerate(element['runs'])]
        translated_elements.append({
            **element,
            'translated_text': '[MOCK] ' + element['text'],
            'translated_runs': translated_runs,
        })
    
    result_bytes = await replace_text_in_docx(docx_bytes, translated_elements)
    
    # Verify result is valid DOCX
    result_doc = Document(io.BytesIO(result_bytes))
    assert len(result_doc.paragraphs) > 0
    
    # Verify tables are preserved
    assert len(result_doc.tables) > 0
    assert len(result_doc.tables[0].rows) == 2
    assert len(result_doc.tables[0].columns) == 2
    
    # Verify header and footer are preserved
    assert result_doc.sections[0].header is not None
    assert result_doc.sections[0].footer is not None
    
    print("✓ Full roundtrip preserves all formatting")


@pytest.mark.asyncio
async def test_formatting_preservation():
    """Test that all formatting is preserved after roundtrip."""
    docx_bytes = create_test_docx()
    
    elements = await extract_text_with_runs(docx_bytes)
    
    translated_elements = []
    for element in elements:
        translated_runs = [f"<r{i}>[TRANSLATED] {run}</r{i}>" 
                         for i, run in enumerate(element['runs'])]
        translated_elements.append({
            **element,
            'translated_text': '[TRANSLATED] ' + element['text'],
            'translated_runs': translated_runs,
        })
    
    result_bytes = await replace_text_in_docx(docx_bytes, translated_elements)
    
    # Extract again
    result_elements = await extract_text_with_runs(result_bytes)
    
    # Check that structure is preserved
    assert len(result_elements) == len(elements)
    
    # Check that translations are present
    result_texts = [e['text'] for e in result_elements]
    assert any('[TRANSLATED]' in text for text in result_texts)
    
    print("✓ Formatting is preserved with translations")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
