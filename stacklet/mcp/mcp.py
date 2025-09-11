from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from .assetdb_redash import AssetDBClient
from .docs_handler import list_documentation_files, read_documentation_file
from .models import DocContent, DocsList
from .stacklet_auth import load_stacklet_auth
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
  - "assetdb_query_list" and "assetdb_query_get" for saved query management
""",
)


class AuthInitMiddleware(Middleware):
    """Initialize AssetDB and Platform clients once per session."""

    async def on_message(self, context: MiddlewareContext, call_next: Any) -> Any:
        if context.fastmcp_context and not context.fastmcp_context.get_state("clients_initialized"):
            credentials = load_stacklet_auth()

            # Initialize both clients
            assetdb_client = AssetDBClient(credentials)
            platform_client = PlatformClient(credentials)

            # Store in session context
            context.fastmcp_context.set_state("assetdb_client", assetdb_client)
            context.fastmcp_context.set_state("platform_client", platform_client)
            context.fastmcp_context.set_state("clients_initialized", True)

        return await call_next(context)


mcp.add_middleware(AuthInitMiddleware())


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
    client: PlatformClient = ctx.get_state("platform_client")
    return await client.list_types(match)


@mcp.tool()
async def platform_graphql_get_types(ctx: Context, type_names: list[str]) -> dict[str, str]:
    """
    Retrieve information about types in the Stacklet Platform GraphQL API.

    Args:
        type_names: Names of requested types.

    Returns:
        JSON string mapping valid type names to GraphQL SDL definitions.
    """
    client: PlatformClient = ctx.get_state("platform_client")
    return await client.get_types(type_names)


@mcp.tool()
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
    client: PlatformClient = ctx.get_state("platform_client")
    return await client.query(query, variables or {})


@mcp.tool()
def assetdb_sql_info() -> str:
    """
    Key information for LLMs using the assetdb_sql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the AssetDB SQL toolset.
    """
    return get_package_file("docs/assetdb_info.md").read_text()


@mcp.tool()
async def assetdb_sql_query(ctx: Context, query: str, timeout: int = 60) -> dict[str, Any]:
    """
    Execute an ad-hoc SQL query against AssetDB.

    Only call this tool when you understand the principles outlined in the
    assetdb_sql_info tool. Always explore the schema first and use appropriate
    filters to scope your queries.

    Args:
        query: The SQL query string to execute
        timeout: Query timeout in seconds (default 60, max 300)

    Returns:
        Complete query result data
    """
    if timeout > 300:
        timeout = 300  # Cap at 5 minutes

    client: AssetDBClient = ctx.get_state("assetdb_client")
    return await client.execute_adhoc_query(query, timeout=timeout)


@mcp.tool()
async def assetdb_query_list(
    ctx: Context,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    List and search saved queries using Redash's built-in capabilities.

    Args:
        page: Page number (1-based)
        page_size: Queries per page (max 100)
        search: Search query names, descriptions, and SQL content
        tags: Match only queries with these tags

    Returns:
        List of queries with pagination metadata
    """
    client: AssetDBClient = ctx.get_state("assetdb_client")

    result = await client.list_queries(
        page=page,
        page_size=min(page_size, 100),  # Cap at reasonable limit
        search=search,
        tags=tags,
    )

    # Clean up the response for LLM consumption
    queries = []
    for q in result.get("results", []):
        queries.append(
            {
                "id": q["id"],
                "name": q["name"],
                "description": q.get("description", ""),
                "tags": q.get("tags", []),
                "user": q["user"],
                "is_archived": q.get("is_archived", False),
                "is_draft": q.get("is_draft", False),
                "data_source_id": q["data_source_id"],
                "has_parameters": bool(q.get("options", {}).get("parameters")),
            }
        )

    return {
        "queries": queries,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": result.get("count", 0),
            "has_next": page * page_size < result.get("count", 0),
        },
    }


@mcp.tool()
async def assetdb_query_get(ctx: Context, query_id: int) -> dict[str, Any]:
    """
    Get detailed information about a specific saved query.

    Args:
        query_id: ID of the query to retrieve

    Returns:
        Complete query object with SQL and parameters
    """
    client: AssetDBClient = ctx.get_state("assetdb_client")
    result = await client.get_query(query_id)
    result.pop("visualizations", None)  # sometimes large, not currently relevant
    return result


def main() -> None:
    """Main entry point for the MCP server"""
    mcp.run()
