# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import asyncio

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol, TypeVar, cast

from fastmcp import Context, FastMCP
from fastmcp.server.server import LifespanCallable
from fastmcp.utilities.logging import get_logger

from mcp.server.lowlevel.server import LifespanResultT

from .settings import SETTINGS


ServerCached = TypeVar("ServerCached")


class ServerStateProtocol(Protocol):
    """Protocol for server-wide request state.

    The local implementation caches objects for the process lifetime (safe for
    single-user stdio servers). A hosted implementation can key caches per user
    or skip caching entirely so each request gets a fresh client constructed
    from that request's forwarded credentials.
    """

    @property
    def auth_provider(self) -> Any:
        """Auth provider for this server instance."""
        ...

    def ensure_cached(self, key: str, construct: Callable[[], ServerCached]) -> ServerCached:
        """Return the cached object for key, constructing it if not present."""
        ...

    async def ensure_cached_async(
        self, key: str, construct: Callable[[], Awaitable[ServerCached]]
    ) -> ServerCached:
        """Async variant of ensure_cached for objects that require async construction."""
        ...

    async def aclose(self) -> None:
        """Release any resources held by this state instance."""
        ...


class ServerState(dict[str, Any]):
    """Local server state — caches objects for the process lifetime."""

    def __init__(self, auth_provider: Any) -> None:
        super().__init__()
        self._auth_provider = auth_provider
        self._async_locks: dict[str, asyncio.Lock] = {}

    @property
    def auth_provider(self) -> Any:
        return self._auth_provider

    def ensure_cached(self, key: str, construct: Callable[[], ServerCached]) -> ServerCached:
        obj = self.get(key)
        if obj is None:
            obj = construct()
            self[key] = obj
        return cast(ServerCached, obj)

    async def ensure_cached_async(
        self, key: str, construct: Callable[[], Awaitable[ServerCached]]
    ) -> ServerCached:
        obj = self.get(key)
        if obj is not None:
            return cast(ServerCached, obj)
        lock = self._async_locks.setdefault(key, asyncio.Lock())
        async with lock:
            obj = self.get(key)
            if obj is None:
                obj = await construct()
                self[key] = obj
            return cast(ServerCached, obj)

    async def aclose(self) -> None:
        for value in self.values():
            if hasattr(value, "aclose"):
                await value.aclose()


def make_lifespan(
    auth_provider: Any,
    state_factory: Callable[[Any], ServerStateProtocol] | None = None,
) -> LifespanCallable[Any]:
    """Return a lifespan context manager parameterized with the given auth provider.

    Args:
        auth_provider: Auth provider passed to the state factory.
        state_factory: Callable that takes an auth provider and returns a
            ServerStateProtocol. Defaults to ServerState (local, cached).
            A hosted deployment can pass an implementation that creates
            per-request state instead.
    """
    factory: Callable[[Any], ServerStateProtocol] = state_factory or ServerState

    @asynccontextmanager
    async def _lifespan(_server: FastMCP[LifespanResultT]) -> AsyncIterator[ServerStateProtocol]:
        logger = get_logger("stacklet")
        logger.info(f"Server settings: {SETTINGS.model_dump()}")
        state = factory(auth_provider)
        try:
            yield state
        finally:
            await state.aclose()

    return _lifespan


def server_cached(ctx: Context, key: str, construct: Callable[[], ServerCached]) -> ServerCached:
    """Get or construct and cache an object in the server context state, with the provided key."""
    assert ctx.request_context is not None, "server_cached must be called within a request context"
    state = ctx.request_context.lifespan_context
    return cast(ServerCached, state.ensure_cached(key, construct))
