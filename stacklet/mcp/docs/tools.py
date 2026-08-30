# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from typing import Annotated

from fastmcp import Context
from fastmcp.tools import Tool
from pydantic import Field

from ..utils.tool import make_tool
from .client import DocsClient
from .models import DocContent, DocsList


def tools() -> list[Tool]:
    """List of available Documentation tools."""
    return [
        make_tool(docs_list, read_only=True),
        make_tool(docs_read, read_only=True),
    ]


async def docs_list(ctx: Context) -> DocsList:
    """
    Browse the complete library of Stacklet documentation files.

    Returns all available documentation including user guides, API references,
    tutorials, and troubleshooting resources. Each file has a path and descriptive title.

    Start with "index_llms.md" - it's specifically designed as an LLM-friendly overview
    of all documentation and provides the best entry point for understanding Stacklet's
    features and capabilities. The glossary is also extremely valuable in understanding
    the most important concepts and their relationships.

    Use docs_read() with any of the returned file paths to get the actual content.
    """
    client = DocsClient.get(ctx)
    index = await client.get_index()
    return DocsList(
        base_url=client.docs_url,
        available_document_files=index,
        note="Use docs_read with any of these file paths to read the content",
    )


async def docs_read(
    ctx: Context,
    file_path: Annotated[
        str,
        Field(
            min_length=1,
            description="Relative path to the documentation file to read (e.g., 'index_llms.md')",
        ),
    ],
) -> DocContent:
    """
    Read Stacklet documentation files for detailed guidance and reference information.

    Provides access to the complete Stacklet knowledge base including setup guides,
    feature explanations, API documentation, best practices, and troubleshooting help.

    Recommended reading order:
    1. Start with "index_llms.md" for the big picture overview
    2. Follow links to specific topics you need
    3. Check troubleshooting guides for common issues

    All documentation is written in Markdown format and regularly updated to reflect
    the latest Stacklet features and best practices.
    """
    client = DocsClient.get(ctx)
    return await client.get_doc_file(file_path)
