# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, TypeVar, cast

from fastmcp import Context, FastMCP
from fastmcp.utilities.logging import get_logger
from mcp.server.lowlevel.server import LifespanResultT

from .settings import SETTINGS


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
async def lifespan(server: FastMCP[LifespanResultT]) -> AsyncIterator[ServerState]:
    """Server lifespan context manager."""
    logger = get_logger("stacklet")

    # startup logging
    logger.info(f"Server settings: {SETTINGS.model_dump()}")

    # return shared state
    yield ServerState()


def server_cached(ctx: Context, key: str, construct: Callable[[], ServerCached]) -> ServerCached:
    """Get or construct and cache an object in the server context state, with the provided key."""
    state = ctx.request_context.lifespan_context
    return cast(ServerCached, state.ensure_cached(key, construct))
