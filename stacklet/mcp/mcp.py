import json

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


mcp = FastMCP("Stacklet")


class AuthInitMiddleware(Middleware):
    """Initialize AssetDB and Platform clients once per session."""

    async def on_message(self, context: MiddlewareContext, call_next):
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
    client = ctx.get_state("platform_client")
    return await client.list_types(match)


@mcp.tool()
async def platform_graphql_get_types(ctx: Context, type_names: list[str]) -> str:
    """
    Retrieve information about types in the Stacklet Platform GraphQL API.

    Args:
        type_names: Names of requested types.

    Returns:
        JSON string mapping valid type names to GraphQL SDL definitions.
    """
    client = ctx.get_state("platform_client")
    found = await client.get_types(type_names)
    return json.dumps(found)


@mcp.tool()
async def platform_graphql_query(
    ctx: Context, query: str, variables: dict[str, Any] | None = None
) -> str:
    """
    Execute a GraphQL query against the Stacklet API.

    Only call this tool when you understand the principles outlined in the
    platform_graphql_info tool. Always remember to check input and output
    types before you use them.

    Args:
        query: The GraphQL query string
        variables: Variables dict for the query

    Returns:
        JSON string of the query result
    """
    client = ctx.get_state("platform_client")
    result = await client.query(query, variables or {})
    return json.dumps(result, indent=2)


@mcp.tool()
def assetdb_sql_info() -> str:
    """
    Key information for LLMs using the assetdb_sql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the AssetDB SQL toolset.
    """
    return """
## **Stacklet AssetDB SQL Overview**

The AssetDB is Stacklet's centralized data warehouse containing all cloud resource data,
relationships, and metadata. It's designed for efficient querying and analysis of your
cloud estate at scale.

### **Database Structure**

The AssetDB follows a structured schema with these key principles:
- Resources are normalized across cloud providers
- Historical data is maintained for change tracking
- Relationships between resources are preserved
- Metadata includes tags, configurations, and compliance state

Always explore the schema first using the data source schema APIs to understand
available tables and columns before writing queries.

### **SQL Usage Principles**

**Query Efficiently:**
- Use LIMIT clauses for exploratory queries to avoid overwhelming results
- Index on commonly filtered columns (account_id, resource_type, region)
- Use time-based filters when analyzing historical data

**Common Patterns:**
- Filter by account_id to scope queries to specific accounts
- Use resource_type to focus on specific AWS/Azure/GCP services
- Join tables carefully - the schema preserves relationships but joins can be expensive
- Aggregate data when looking for trends or summaries

**Schema Exploration:**
- Start with DESCRIBE or SHOW TABLES to understand structure
- Use INFORMATION_SCHEMA queries to explore column metadata
- Look for tables with prefixes indicating data types (e.g., aws_, azure_, gcp_)

**Performance Tips:**
- Use specific column lists instead of SELECT *
- Apply filters early in WHERE clauses
- Consider using CTEs for complex multi-step analysis
- Be mindful of query timeout limits (typically 60 seconds)

### **Common Use Cases**

**Resource Inventory:**
- Count resources by type, account, or region
- Find resources with specific tags or configurations
- Identify orphaned or unused resources

**Compliance Analysis:**
- Query resource configurations against policy requirements
- Find resources missing required tags or settings
- Track compliance trends over time

**Cost Analysis:**
- Aggregate resource costs by various dimensions
- Identify cost anomalies or optimization opportunities
- Track spending trends and patterns

**Change Tracking:**
- Query historical data to understand resource lifecycle
- Find recently created, modified, or deleted resources
- Analyze configuration drift over time

### **Security Considerations**

The AssetDB contains sensitive information about your cloud infrastructure.
Queries should be:
- Purposeful and scoped appropriately
- Mindful of data sensitivity in results
- Used only for legitimate analysis and governance needs

### **Getting Help**

- Use the schema exploration tools to understand available data
- Start with simple queries and build complexity incrementally
- Consider the Stacklet documentation for data model explanations
- Remember that GraphQL tools may provide complementary analysis capabilities
"""


@mcp.tool()
async def assetdb_sql_query(ctx: Context, query: str, timeout: int = 60) -> str:
    """
    Execute an ad-hoc SQL query against the AssetDB.

    Only call this tool when you understand the principles outlined in the
    assetdb_sql_info tool. Always explore the schema first and use appropriate
    filters to scope your queries.

    Args:
        query: The SQL query string to execute
        timeout: Query timeout in seconds (default 60, max 300)

    Returns:
        JSON string containing query results with data, columns, and metadata
    """
    if timeout > 300:
        timeout = 300  # Cap at 5 minutes

    client = ctx.get_state("assetdb_client")

    try:
        result = await client.execute_adhoc_query(query, timeout=timeout)
        return json.dumps(result, indent=2)
    except Exception as e:
        raise Error(
            f"SQL query execution failed: {str(e)}",
            suggestion="Check query syntax, verify table/column names, or reduce query complexity",
        )


def main():
    """Main entry point for the MCP server"""
    mcp.run()
