from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from .assetdb.tools import (
    assetdb_query_get,
    assetdb_query_list,
    assetdb_query_results,
    assetdb_query_save,
    assetdb_sql_info,
    assetdb_sql_query,
)
from .docs_handler import list_documentation_files, read_documentation_file
from .mcp_util import json_guard
from .models import DocContent, DocsList
from .stacklet_platform import PlatformClient
from .utils import get_package_file


mcp = FastMCP(
    "Stacklet",
    """
The Stacklet MCP server has 3 main toolsets:

- "docs_list" and "docs_read" give access to Stacklet documentation
  - reading documentation will help you understand the concepts
- "platform_*" tools give access to the Platform GraphQL API
  - the "platform_graphql_info" tool is a great place to start
- "assetdb_*" tools give access to your cloud asset inventory
  - "assetdb_sql_info" and "assetdb_sql_query" for direct SQL access
  - "assetdb_query_list", "assetdb_query_get", "assetdb_query_save" and
  "assetdb_query_results" for saved query management
""",
    tools=[
        assetdb_sql_info,
        assetdb_sql_query,
        assetdb_query_list,
        assetdb_query_get,
        assetdb_query_results,
        assetdb_query_save,
    ],
)


class Error(ToolError):
    """An error from the tool."""

    def __init__(self, message: str, suggestion: str | None = None):
        if suggestion:
            message += f". *Suggestion*: {suggestion}."
        super().__init__(message)


@mcp.tool()
def docs_list() -> DocsList:
    """
    List all available Stacklet user documentation files.

    Returns:
        Available documentation files

    Note:
        This information is most valuable when "index_llms.md" has already been
        seen via the docs_read tool.
    """
    return DocsList(
        available_files=list_documentation_files(),
        note="Use docs_read with any of these file paths to read the content",
    )


@mcp.tool()
def docs_read(file_path: Path) -> DocContent:
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
    content = read_documentation_file(file_path)
    if content is None:
        raise Error(
            f"File '{file_path}' not found or not accessible",
            suggestion="Try 'index_llms.md' as a starting point, or check docs_list",
        )

    return DocContent(file_path=file_path, content=content)


@mcp.tool()
def platform_graphql_info() -> str:
    """
    Key information for LLMs using the platform_graphql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the toolset.
    """
    return get_package_file("docs/graphql_info.md").read_text()


@mcp.tool()
async def platform_graphql_list_types(ctx: Context, match: str | None = None) -> list[str]:
    """
    List the types available in the Stacklet Platform GraphQL API.

    Args:
        match: Optional regular expression filter

    Returns:
        List of type names
    """
    client = PlatformClient.get(ctx)
    return await client.list_types(match)


@mcp.tool()
@json_guard
async def platform_graphql_get_types(ctx: Context, type_names: list[str]) -> dict[str, str]:
    """
    Retrieve information about types in the Stacklet Platform GraphQL API.

    Args:
        type_names: Names of requested types.

    Returns:
        JSON string mapping valid type names to GraphQL SDL definitions.
    """
    client = PlatformClient.get(ctx)
    return await client.get_types(type_names)


@mcp.tool()
@json_guard
async def platform_graphql_query(
    ctx: Context, query: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Execute a GraphQL query against the Stacklet API.

    Only call this tool when you understand the principles outlined in the
    platform_graphql_info tool. Always remember to check input and output
    types before you use them.

    Args:
        query: The GraphQL query string
        variables: Variables dict for the query

    Returns:
        Complete GraphQL query result
    """
    client = PlatformClient.get(ctx)
    return await client.query(query, variables or {})


def main() -> None:
    """Main entry point for the MCP server"""
    mcp.run()
