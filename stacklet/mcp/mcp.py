from pathlib import Path

from fastmcp import FastMCP
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
from .models import DocContent, DocsList
from .platform.tools import (
    platform_graphql_get_types,
    platform_graphql_info,
    platform_graphql_list_types,
    platform_graphql_query,
)


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
        platform_graphql_info,
        platform_graphql_list_types,
        platform_graphql_get_types,
        platform_graphql_query,
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


def main() -> None:
    """Main entry point for the MCP server"""
    mcp.run()
