# DOCX Translation Workflow

A Mistral Workflow for translating DOCX files to one of the top 10 most spoken languages while preserving all formatting including tables, headers, footers, styles, and images.

## Features

- **Full Formatting Preservation**: Maintains all original DOCX formatting including:
  - Paragraph styles (bold, italic, fonts, colors, etc.)
  - Table structures and cell formatting
  - Headers and footers
  - Images and their positioning
  - Section properties (margins, page size, etc.)
  - Line spacing, indentation, alignment

- **Top 10 Languages**: Supports translation to:
  - English (en)
  - Mandarin Chinese (zh)
  - Hindi (hi)
  - Spanish (es)
  - French (fr)
  - Arabic (ar)
  - Bengali (bn)
  - Russian (ru)
  - Portuguese (pt)
  - Indonesian (id)

- **Callable from Vibe Work**: Includes a skill interface for easy integration

- **Durable Execution**: Built on Mistral Workflows for fault-tolerant, long-running processes

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCX Translation Workflow                    │
├─────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Extract      │───▶│  Translate   │───▶│  Rebuild     │   │
│  │  Content      │    │  Chunks      │    │  DOCX        │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Skill Interface                         ││
│  │  - docx-translator: Full translation with all options     ││
│  │  - docx-translator-simple: Simplified version for testing  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- uv package manager
- Mistral API key

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd docx-translation-workflow

# Install dependencies
make install

# Or for development
make dev-install
```

### Running the Worker

```bash
# Set your Mistral API key
export MISTRAL_API_KEY=your-api-key

# Start the worker
make start-worker
```

### Testing

```bash
# Run the test workflow
make test-workflow

# Run all tests
make test

# Lint the code
make lint
```

## Usage

### From Mistral API

```python
import mistralai.workflows as workflows

async def translate_docx():
    client = workflows.client()
    
    with open("document.docx", "rb") as f:
        docx_bytes = f.read()
    
    result = await client.workflows.execute(
        workflow_name="docx-translation",
        input={
            "docx_bytes": docx_bytes,
            "target_language": "fr",
            "preserve_formatting": True,
            "translate_headers_footers": True,
            "translate_table_text": True,
        }
    )
    
    with open("translated.docx", "wb") as f:
        f.write(result["translated_docx_bytes"])
```

### From Vibe Work (via Skill)

```python
import base64
import mistralai.workflows as workflows

async def translate_via_skill():
    client = workflows.client()
    
    with open("document.docx", "rb") as f:
        docx_base64 = base64.b64encode(f.read()).decode("utf-8")
    
    result = await client.skills.execute(
        skill_name="docx-translator",
        input={
            "docx_base64": docx_base64,
            "target_language": "fr",
            "preserve_formatting": True,
        }
    )
    
    translated_docx = base64.b64decode(result["translated_docx_base64"])
    with open("translated.docx", "wb") as f:
        f.write(translated_docx)
```

## Project Structure

```
docx-translation-workflow/
├── src/
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── translation_workflow.py  # Main workflow
│   │   └── activities.py             # Activities (extract, translate, rebuild)
│   ├── skills/
│   │   ├── __init__.py
│   │   └── docx_translator_skill.py  # Skill interface
│   └── models/
│       ├── __init__.py
│       └── schemas.py                # Pydantic schemas
├── pyproject.toml                   # Dependencies
├── Makefile                         # Commands
└── README.md                        # This file
```

## Configuration

### Environment Variables

- `MISTRAL_API_KEY`: Your Mistral API key for translation
- `WORKFLOW_TIMEOUT`: Maximum execution time (default: 600 seconds)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)

### Customization

You can customize the workflow by modifying:

1. **Supported Languages**: Edit `Language` enum in `src/models/schemas.py`
2. **Translation API**: Modify `_translate_text` in `src/workflows/activities.py`
3. **Formatting Preservation**: Adjust extraction/rebuilding logic in activities

## Development

### Adding New Features

1. Create a new activity in `activities.py`
2. Add it to the workflow in `translation_workflow.py`
3. Update the skill interface if needed

### Testing

```bash
# Run specific test
pytest tests/test_activities.py -v

# Run with coverage
pytest --cov=src tests/ -v
```

## Deployment

### To Mistral Studio

1. Build the package:
   ```bash
   uv build
   ```

2. Deploy to your Mistral environment

3. Register the workflow in Studio

### Docker Deployment

Create a Dockerfile:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN uv sync --frozen

CMD ["uv", "run", "python", "-m", "mistralai.workflows.worker"]
```

## Troubleshooting

### Common Issues

1. **Dependency Errors**: Run `make dev-install` to install all dependencies
2. **API Key Issues**: Ensure `MISTRAL_API_KEY` is set correctly
3. **Worker Connection**: Check network connectivity to Mistral API
4. **Formatting Issues**: Verify DOCX file structure with `python-docx`

### Debugging

```bash
# Run with debug logging
UV_LOG_LEVEL=debug make start-worker

# Test with a specific file
python -c ""
from src.workflows.translation_workflow import SimpleDOCXTranslationWorkflow
import asyncio

async def test():
    workflow = SimpleDOCXTranslationWorkflow()
    with open('test.docx', 'rb') as f:
        result = await workflow.run(f.read(), 'fr')
    with open('output.docx', 'wb') as f:
        f.write(result)

asyncio.run(test())
"
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make lint` and `make test`
5. Submit a pull request

## Acknowledgments

- Built with [Mistral Workflows](https://docs.mistral.ai/studio/workflows)
- Uses [python-docx](https://python-docx.readthedocs.io/) for DOCX manipulation
- Inspired by the need for format-preserving document translation
