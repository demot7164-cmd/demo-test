"""
Worker for DOCX translation workflow.
"""

import asyncio

import mistralai.workflows as workflows

from src.workflows.translation_workflow import DocxTranslation


async def main():
    """Run the worker."""
    await workflows.run_worker([DocxTranslation])


if __name__ == "__main__":
    asyncio.run(main())
