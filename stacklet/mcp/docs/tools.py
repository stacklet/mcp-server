import httpx

from fastmcp import Context
from fastmcp.exceptions import ToolError

from .client import DocsClient
from .models import DocContent, DocsList


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
    try:
        return await client.get_doc_file(file_path)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == httpx.codes.NOT_FOUND:
            raise ToolError(
                f"File '{file_path}' not found, "
                "Check docs_list or try 'index_llms.md' as a starting point",
            )
        raise
