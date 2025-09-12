from fastmcp import FastMCP

from .assetdb.tools import (
    assetdb_query_get,
    assetdb_query_list,
    assetdb_query_results,
    assetdb_query_save,
    assetdb_sql_info,
    assetdb_sql_query,
)
from .docs.tools import (
    docs_list,
    docs_read,
)
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
        docs_list,
        docs_read,
        platform_graphql_info,
        platform_graphql_list_types,
        platform_graphql_get_types,
        platform_graphql_query,
    ],
)


def main() -> None:
    """Main entry point for the MCP server"""
    mcp.run()
