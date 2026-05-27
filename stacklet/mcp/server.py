# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from itertools import chain
from typing import Any, Callable, Protocol

from fastmcp import Context, FastMCP
from fastmcp.tools import Tool

from . import __version__
from .assetdb.tools import tools as assetdb_tools
from .auth import LocalAuthProvider
from .docs.tools import tools as docs_tools
from .lifespan import ServerStateProtocol, make_lifespan
from .platform.tools import tools as platform_tools
from .stacklet_auth import StackletCredentials
from .utils.text import get_file_text


class AuthProvider(Protocol):
    """Protocol for MCP server authentication.

    Implementations supply credentials for a given request context.
    The local implementation loads from disk/environment; a hosted
    implementation extracts credentials forwarded in HTTP request headers.
    """

    def get_credentials(self, ctx: Context) -> StackletCredentials:
        """Return Stacklet credentials for the current request."""
        ...


def make_server(
    auth_provider: AuthProvider | None = None,
    state_factory: Callable[[Any], ServerStateProtocol] | None = None,
) -> FastMCP:
    """Create an MCP server.

    Args:
        auth_provider: Auth provider to use. Defaults to LocalAuthProvider, which
            loads credentials from ~/.stacklet/ files or environment variables.
            Pass a custom implementation to support alternative auth schemes
            (e.g. forwarded credentials in a hosted deployment).
        state_factory: Factory for per-lifespan server state. Defaults to
            ServerState (process-lifetime cache, correct for local stdio use).
            A hosted deployment can pass an implementation that creates
            per-request state, e.g. to avoid sharing cached clients across users.
    """
    provider = auth_provider or LocalAuthProvider()

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
        lifespan=make_lifespan(provider, state_factory),
    )
