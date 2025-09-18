from itertools import chain
from textwrap import dedent
from typing import Any, Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool

from . import __version__
from .assetdb.tools import tools as assetdb_tools
from .docs.tools import tools as docs_tools
from .lifespan import lifespan
from .platform.tools import tools as platform_tools


def make_server() -> FastMCP:
    """Create an MCP server.."""
    tool_sets = [
        assetdb_tools,
        docs_tools,
        platform_tools,
    ]
    tools: list[Tool | Callable[..., Any]] = list(chain(*(tool_set() for tool_set in tool_sets)))

    return FastMCP(
        name="Stacklet",
        version=__version__,
        instructions=dedent(
            """
            The Stacklet MCP server provides sophisticated cloud governance tooling through 3
            specialized toolsets:

            ## Critical: Always Start with Info Tools
            Each toolset has an "*_info" tool containing essential guidance - call these first:
            - "assetdb_sql_info"
            - "platform_graphql_info"
            - "platform_dataset_info"

            ## Documentation Tools
            - "docs_list" - Browse available Stacklet documentation files
            - "docs_read" - Access live documentation content (start with 'index_llms.md')

            ## AssetDB Tools - Cloud Asset Analytics
            PostgreSQL warehouse with resource data, costs, and relationships:
            - "assetdb_sql_query" - Direct SQL access (ALWAYS use LIMIT with large tables)
            - "assetdb_query_*" - Saved query management (list, get, results, save)

            Scale awareness critical: Use provider-specific tables (aws_ec2, aws_s3, etc) over raw
            JSON (resources._raw)

            ## Platform GraphQL Tools - Governance Operations
            Full platform API access with intelligent export capabilities:
            - "platform_graphql_query" - Direct GraphQL access (always include 'problems' field)
            - "platform_graphql_list_types", "platform_graphql_get_types" - Schema exploration
            - "platform_dataset_export", "platform_dataset_lookup" - Large dataset CSV exports

            Workflow:
            1. Small queries for exploration
            2. dataset exports for analysis
            3. AssetDB for massive scale

            ## Performance Guidelines
            - AssetDB: Check table sizes first, use filters, prefer typed tables
            - Platform: Small pages (5-10 items) for connections, export for large datasets
            - Never export all resources - use AssetDB SQL for operations > 10K records

            The info tools contain the most valuable patterns and will load your context with
            platform-specific best practices.
            """
        ),
        tools=tools,
        lifespan=lifespan,
    )


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = make_server()
    mcp.run(show_banner=False)
