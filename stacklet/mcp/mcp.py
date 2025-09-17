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
            The Stacklet MCP server has 3 main toolsets:

            - "docs_list" and "docs_read" give access to Stacklet documentation
              * reading documentation will help you understand the concepts
            - "platform_*" tools give access to the Platform GraphQL API
              * the "platform_graphql_info" tool is a great place to start
            - "assetdb_*" tools give access to your cloud asset inventory
              * "assetdb_sql_info" and "assetdb_sql_query" for direct SQL access
              * "assetdb_query_list", "assetdb_query_get", "assetdb_query_save"
                and "assetdb_query_results" for saved query management
            """
        ),
        tools=tools,
        lifespan=lifespan,
    )


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = make_server()
    mcp.run(show_banner=False)
