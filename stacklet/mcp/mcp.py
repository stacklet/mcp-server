from itertools import chain
from typing import Any, Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool

from . import __version__
from .assetdb.tools import tools as assetdb_tools
from .docs.tools import tools as docs_tools
from .lifespan import lifespan
from .platform.tools import tools as platform_tools
from .utils import get_file_text


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
        instructions=get_file_text("mcp_info.md"),
        tools=tools,
        lifespan=lifespan,
    )


def main() -> None:
    """Main entry point for the MCP server."""
    mcp = make_server()
    mcp.run(show_banner=False)
