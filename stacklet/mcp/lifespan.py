from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, TypeVar, cast

from fastmcp import Context, FastMCP
from mcp.server.lowlevel.server import LifespanResultT


# an object cached in the server global state
ServerCached = TypeVar("ServerCached")


class ServerState(dict[str, Any]):
    """Server-global state.

    This is practical for local servers since there's always a single client,
    but won't work for network-based ones.

    """

    def ensure_cached(self, key: str, construct: Callable[[], ServerCached]) -> ServerCached:
        obj = self.get(key)
        if obj is None:
            obj = construct()
            self[key] = obj
        return cast(ServerCached, obj)


@asynccontextmanager
async def server_state_lifespan(server: FastMCP[LifespanResultT]) -> AsyncIterator[ServerState]:
    """Lifespan context manager for global state in the server."""
    yield ServerState()


def server_cached(ctx: Context, key: str, construct: Callable[[], ServerCached]) -> ServerCached:
    """Get or construct and cache an object in the server context state, with the provided key."""
    state = ctx.request_context.lifespan_context
    return cast(ServerCached, state.ensure_cached(key, construct))
