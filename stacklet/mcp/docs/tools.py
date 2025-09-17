from typing import Any, Callable

from fastmcp import Context

from ..settings import Settings
from .client import DocsClient
from .models import DocContent, DocsList


def tools(settings: Settings) -> list[Callable[..., Any]]:
    """List of available Documentation tools."""
    return [
        docs_list,
        docs_read,
    ]


async def docs_list(ctx: Context) -> DocsList:
    """
    List all available Stacklet user documentation files.

    Returns:
        Available documentation files

    Note:
        This information is most valuable when "index_llms.md" has already been
        seen via the docs_read tool.
    """
    client = DocsClient.get(ctx)
    index = await client.get_index()
    return DocsList(
        base_url=client.docs_url,
        available_document_files=index,
        note="Use docs_read with any of these file paths to read the content",
    )


async def docs_read(ctx: Context, file_path: str) -> DocContent:
    """
    Read a Stacklet documentation file.

    Args:
        file_path: Relative path to the documentation file (e.g., "index_llms.md")

    Returns:
        The content of the file

    Note:
        The best starting point is "index_llms.md" which provides an overview
        of all available documentation.
    """
    client = DocsClient.get(ctx)
    return await client.get_doc_file(file_path)
