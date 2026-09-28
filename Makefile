# Makefile for DOCX Translation Workflow

.PHONY: help install dev-install lint test test-workflow start-worker execute clean

# Environment
PYTHON ?= python
UV ?= uv
MAKE ?= make

# Project
PROJECT_NAME ?= docx-translation-workflow
WORKFLOW_NAME ?= docx-translation
SIMPLE_WORKFLOW_NAME ?= docx-translation-simple

# API Configuration
MISTRAL_API_KEY ?= $(shell echo $$MISTRAL_API_KEY)
MISTRAL_MODEL ?= mistral-large-latest
WORKFLOW_TIMEOUT ?= 600
MAX_RETRIES ?= 3

help: ## Show this help message
	@echo "DOCX Translation Workflow - Makefile Commands"
	@echo "==============================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

install: ## Install production dependencies
	$(UV) sync --frozen

dev-install: ## Install development dependencies
	$(UV) sync --all-extras --dev

lint: ## Run linting
	$(UV) run ruff check src/
	$(UV) run mypy src/

test: ## Run tests
	$(UV) run pytest tests/ -v

test-workflow: ## Test the workflow locally (with mock translation)
	@echo "Testing DOCX translation workflow with mock..."
	@echo "Set MISTRAL_API_KEY to test with real API"
	MISTRAL_API_KEY=$(MISTRAL_API_KEY) $(UV) run python -c ""
import asyncio
import base64
import os
os.environ['MISTRAL_API_KEY'] = os.getenv('MISTRAL_API_KEY', 'test-key')
from src.workflows.translation_workflow import SimpleDOCXTranslationWorkflow

async def test():
    # Create a simple DOCX for testing
    from docx import Document
    import io
    
    doc = Document()
    doc.add_heading('Test Document', 0)
    doc.add_paragraph('This is a test paragraph.')
    doc.add_paragraph('This is another paragraph with some bold text.', style='Strong')
    
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
    
    # Save result
    with open('/tmp/translated_test.docx', 'wb') as f:
        f.write(result)
    
    print('\u2713 Workflow test passed!')
    print(f'\u2713 Translated DOCX saved to /tmp/translated_test.docx')

asyncio.run(test())
""

start-worker: ## Start the workflow worker
	@echo "Starting DOCX translation worker..."
	@echo "Using model: $(MISTRAL_MODEL)"
	@echo "Timeout: $(WORKFLOW_TIMEOUT)s, Max retries: $(MAX_RETRIES)"
	MISTRAL_API_KEY=$(MISTRAL_API_KEY) MISTRAL_MODEL=$(MISTRAL_MODEL) WORKFLOW_TIMEOUT=$(WORKFLOW_TIMEOUT) MAX_RETRIES=$(MAX_RETRIES) $(UV) run python -m mistralai.workflows.worker --workflow $(WORKFLOW_NAME) --skill docx-translator

start-worker-all: ## Start worker with all workflows and skills
	@echo "Starting all workers..."
	@echo "Using model: $(MISTRAL_MODEL)"
	MISTRAL_API_KEY=$(MISTRAL_API_KEY) MISTRAL_MODEL=$(MISTRAL_MODEL) WORKFLOW_TIMEOUT=$(WORKFLOW_TIMEOUT) MAX_RETRIES=$(MAX_RETRIES) $(UV) run python -m mistralai.workflows.worker --workflow $(WORKFLOW_NAME) --workflow $(SIMPLE_WORKFLOW_NAME) --skill docx-translator --skill docx-translator-simple

execute: workflow=$(WORKFLOW_NAME) input='{"docx_bytes": "", "target_language": "fr"}' ## Execute a workflow
	@echo "Executing workflow: $(workflow)"
	@echo "Input: $(input)"
	$(UV) run python -c ""
import asyncio
import mistralai.workflows as workflows

async def execute():
    client = workflows.client()
    result = await client.workflows.execute(
        workflow_name='$(workflow)',
        input=$(input)
    )
    print(f'Result: {result}')

asyncio.run(execute())
""

clean: ## Clean build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
