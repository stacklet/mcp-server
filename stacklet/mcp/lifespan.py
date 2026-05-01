# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, TypeVar, cast

from fastmcp import Context, FastMCP
from fastmcp.utilities.logging import get_logger

from mcp.server.lowlevel.server import LifespanResultT

from .settings import SETTINGS


# an object cached in the server global state
ServerSingleton = TypeVar("ServerSingleton")


class ServerState(dict[str, Any]):
    """Server-global state.

    Values stored here MUST be identical for every caller. No per-user state, ever.
    In a multi-user HTTP deployment this dict is shared across all requests, so any
    value cached here is seen by every caller; credentials, per-user caches, and
    anything derived from a specific request must live on the request instead.
    """

    def ensure_cached(self, key: str, construct: Callable[[], ServerSingleton]) -> ServerSingleton:
        obj = self.get(key)
        if obj is None:
            obj = construct()
            self[key] = obj
        return cast(ServerSingleton, obj)


@asynccontextmanager
async def lifespan(server: FastMCP[LifespanResultT]) -> AsyncIterator[ServerState]:
    """Server lifespan context manager."""
    logger = get_logger("stacklet")

    # startup logging
    logger.info(f"Server settings: {SETTINGS.model_dump()}")

    # return shared state
    yield ServerState()


def server_singleton(
    ctx: Context, key: str, construct: Callable[[], ServerSingleton]
) -> ServerSingleton:
    """Get or construct a server-wide singleton.

    The value is shared across every request handled by this server process and
    MUST be credential-free (no access tokens, identity tokens, per-user caches,
    etc.). Per-request state belongs on the request, not here.
    """
    assert ctx.request_context is not None, (
        "server_singleton must be called within a request context"
    )
    state = ctx.request_context.lifespan_context
    return cast(ServerSingleton, state.ensure_cached(key, construct))
