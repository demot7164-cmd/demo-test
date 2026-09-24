"""
Activities for DOCX translation workflow.
Handles DOCX file manipulation with real Mistral API calls.
Preserves ALL formatting by only replacing w:t text content.
"""

import io
import logging
import os
import re
from typing import Any, Dict, List
import zipfile

from lxml import etree

import mistralai.workflows as workflows

logger = logging.getLogger(__name__)

# XML Namespaces
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W_NS}


@workflows.activity(
    name="download_file",
    retry_policy_max_attempts=3,
)
async def download_file(url: str) -> bytes:
    """Download file from URL."""
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


@workflows.activity(
    name="extract_text_with_runs",
    retry_policy_max_attempts=3,
)
async def extract_text_with_runs(docx_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract all text elements from DOCX with run information.
    Returns list of elements with: text, runs (list of run texts), element_type, path, xpath
    """
    all_elements = []
    
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        if 'word/document.xml' not in z.namelist():
            raise ValueError("Not a valid DOCX file")
        
        # Process main document
        if 'word/document.xml' in z.namelist():
            with z.open('word/document.xml') as f:
                xml_content = f.read()
                root = etree.fromstring(xml_content)
                body = root.find('.//w:body', NS)
                
                if body is not None:
                    # Extract paragraphs
                    for p in body.findall('.//w:p', NS):
                        text_parts, runs, run_index = [], [], 0
                        for r in p.findall('.//w:r', NS):
                            t = r.find('.//w:t', NS)
                            if t is not None and t.text:
                                text_parts.append(t.text)
                                runs.append(f"<r{run_index}>{t.text}</r{run_index}>")
                                run_index += 1
                        if text_parts:
                            all_elements.append({
                                'text': ''.join(text_parts),
                                'runs': runs,
                                'element_type': 'paragraph',
                                'path': 'word/document.xml',
                            })
                    
                    # Extract tables
                    for table in body.findall('.//w:tbl', NS):
                        for row in table.findall('.//w:tr', NS):
                            for cell in row.findall('.//w:tc', NS):
                                for p in cell.findall('.//w:p', NS):
                                    text_parts, runs, run_index = [], [], 0
                                    for r in p.findall('.//w:r', NS):
                                        t = r.find('.//w:t', NS)
                                        if t is not None and t.text:
                                            text_parts.append(t.text)
                                            runs.append(f"<r{run_index}>{t.text}</r{run_index}>")
                                            run_index += 1
                                    if text_parts:
                                        all_elements.append({
                                            'text': ''.join(text_parts),
                                            'runs': runs,
                                            'element_type': 'table_cell',
                                            'path': 'word/document.xml',
                                        })
        
        # Process headers
        for header_file in ['word/header1.xml', 'word/header2.xml', 'word/header3.xml']:
            if header_file in z.namelist():
                with z.open(header_file) as f:
                    xml_content = f.read()
                    root = etree.fromstring(xml_content)
                    for p in root.findall('.//w:p', NS):
                        text_parts, runs, run_index = [], [], 0
                        for r in p.findall('.//w:r', NS):
                            t = r.find('.//w:t', NS)
                            if t is not None and t.text:
                                text_parts.append(t.text)
                                runs.append(f"<r{run_index}>{t.text}</r{run_index}>")
                                run_index += 1
                        if text_parts:
                            all_elements.append({
                                'text': ''.join(text_parts),
                                'runs': runs,
                                'element_type': 'header',
                                'path': header_file,
                            })
        
        # Process footers
        for footer_file in ['word/footer1.xml', 'word/footer2.xml', 'word/footer3.xml']:
            if footer_file in z.namelist():
                with z.open(footer_file) as f:
                    xml_content = f.read()
                    root = etree.fromstring(xml_content)
                    for p in root.findall('.//w:p', NS):
                        text_parts, runs, run_index = [], [], 0
                        for r in p.findall('.//w:r', NS):
                            t = r.find('.//w:t', NS)
                            if t is not None and t.text:
                                text_parts.append(t.text)
                                runs.append(f"<r{run_index}>{t.text}</r{run_index}>")
                                run_index += 1
                        if text_parts:
                            all_elements.append({
                                'text': ''.join(text_parts),
                                'runs': runs,
                                'element_type': 'footer',
                                'path': footer_file,
                            })
        
        # Process footnotes
        if 'word/footnotes.xml' in z.namelist():
            with z.open('word/footnotes.xml') as f:
                xml_content = f.read()
                root = etree.fromstring(xml_content)
                for footnote in root.findall('.//w:footnote', NS):
                    for p in footnote.findall('.//w:p', NS):
                        text_parts, runs, run_index = [], [], 0
                        for r in p.findall('.//w:r', NS):
                            t = r.find('.//w:t', NS)
                            if t is not None and t.text:
                                text_parts.append(t.text)
                                runs.append(f"<r{run_index}>{t.text}</r{run_index}>")
                                run_index += 1
                        if text_parts:
                            all_elements.append({
                                'text': ''.join(text_parts),
                                'runs': runs,
                                'element_type': 'footnote',
                                'path': 'word/footnotes.xml',
                            })
    
    return all_elements


@workflows.activity(
    name="translate_with_mistral",
    retry_policy_max_attempts=5,
    retry_policy_backoff_coefficient=2.0,
)
async def translate_with_mistral(
    elements: List[Dict[str, Any]],
    target_language: str,
) -> List[Dict[str, Any]]:
    """
    Translate elements using Mistral API (mistral-medium-latest).
    Groups elements by file and sends in batches.
    """
    api_key = os.getenv('MISTRAL_API_KEY')
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable is required")
    
    # Group elements by file for better batching
    file_groups = {}
    for element in elements:
        file_path = element['path']
        if file_path not in file_groups:
            file_groups[file_path] = []
        file_groups[file_path].append(element)
    
    translated_elements = []
    
    import httpx
    async with httpx.AsyncClient(timeout=120.0) as client:
        for file_path, file_elements in file_groups.items():
            # Prepare batches for this file
            batches = []
            current_batch = []
            current_batch_tokens = 0
            
            for element in file_elements:
                word_count = len(element['text'].split())
                element_tokens = word_count * 4
                
                if current_batch and current_batch_tokens + element_tokens > 30000:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_tokens = 0
                
                current_batch.append(element)
                current_batch_tokens += element_tokens
            
            if current_batch:
                batches.append(current_batch)
            
            # Translate each batch
            for batch in batches:
                prompt_parts = []
                for i, element in enumerate(batch):
                    runs_str = ''.join(element['runs'])
                    prompt_parts.append(f"[{i}] Original: {runs_str}")
                
                prompt = "\n".join(prompt_parts)
                prompt += f"\n\nTranslate all above to {target_language}. Keep the <r*> tags exactly as they are. Only translate the text inside the tags."
                
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "mistral-medium-latest",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 4000,
                    },
                )
                response.raise_for_status()
                
                result = response.json()
                translated_text = result['choices'][0]['message']['content']
                
                # Parse translated text
                tag_pattern = r'<r\d+>(.*?)</r\d+>'
                all_translated_runs = re.findall(tag_pattern, translated_text)
                
                # Distribute translated runs to elements
                run_index = 0
                for element in batch:
                    num_runs = len(element['runs'])
                    element_translated_runs = all_translated_runs[run_index:run_index + num_runs]
                    run_index += num_runs
                    
                    if element_translated_runs:
                        element['translated_text'] = ''.join(element_translated_runs)
                        element['translated_runs'] = [
                            f"<r{i}>{run}</r{i}>" 
                            for i, run in enumerate(element_translated_runs)
                        ]
                    else:
                        element['translated_text'] = translated_text
                        element['translated_runs'] = element['runs']
                    
                    translated_elements.append(element)
    
    return translated_elements


@workflows.activity(
    name="replace_text_in_docx",
    retry_policy_max_attempts=3,
)
async def replace_text_in_docx(
    docx_bytes: bytes,
    translated_elements: List[Dict[str, Any]],
) -> bytes:
    """
    Replace text in DOCX by modifying w:t elements only.
    Preserves ALL formatting (styles, colors, tables, etc.).
    """
    # Group translated elements by file
    file_groups = {}
    for element in translated_elements:
        file_path = element['path']
        if file_path not in file_groups:
            file_groups[file_path] = []
        file_groups[file_path].append(element)
    
    output_buffer = io.BytesIO()
    
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z_in:
        with zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED) as z_out:
            for item in z_in.infolist():
                data = z_in.read(item.filename)
                
                if item.filename in file_groups:
                    try:
                        root = etree.fromstring(data)
                        t_elements = list(root.findall('.//w:t', NS))
                        file_elements = file_groups[item.filename]
                        
                        # Replace text in t elements
                        t_index = 0
                        for element in file_elements:
                            translated_runs = element.get('translated_runs', [])
                            if translated_runs and t_index < len(t_elements):
                                tag_pattern = r'<r\d+>(.*?)</r\d+>'
                                matches = re.findall(tag_pattern, translated_runs[0])
                                if matches:
                                    t_elements[t_index].text = matches[0]
                                    t_index += 1
                        
                        modified_xml = etree.tostring(root, encoding='utf-8', xml_declaration=True)
                        z_out.writestr(item, modified_xml)
                    except Exception as e:
                        logger.error(f"Error processing {item.filename}: {e}")
                        z_out.writestr(item, data)
                else:
                    z_out.writestr(item, data)
    
    output_buffer.seek(0)
    return output_buffer.read()


@workflows.activity(
    name="upload_file",
    retry_policy_max_attempts=3,
)
async def upload_file(client: Any, file_bytes: bytes, filename: str) -> str:
    """Upload file to Mistral and return file ID."""
    import base64
    file_b64 = base64.b64encode(file_bytes).decode('utf-8')
    response = await client.files.upload(content=file_b64, filename=filename)
    return response.id


@workflows.activity(
    name="get_signed_url",
    retry_policy_max_attempts=3,
)
async def get_signed_url(client: Any, file_id: str) -> str:
    """Get signed URL for file download."""
    response = await client.files.get_signed_url(file_id=file_id, expiry=24)
    return response.url
