# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import os

from dataclasses import dataclass
from itertools import chain
from typing import Any, Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .assetdb.tools import tools as assetdb_tools
from .docs.tools import tools as docs_tools
from .lifespan import lifespan
from .middleware import DEFAULT_MAX_BYTES, CredentialMiddleware, MaxBodySizeMiddleware
from .platform.tools import tools as platform_tools
from .request_credentials import STREAMABLE_HTTP, set_transport_mode
from .utils.text import get_file_text


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080

# Graceful-shutdown window. Needs to exceed the AssetDB 300s poll ceiling
# plus a small grace for the response to flush.
DEFAULT_TIMEOUT_GRACEFUL_SHUTDOWN = 305


@dataclass(frozen=True, slots=True)
class HttpTransportOptions:
    """Network options for streamable-http transport.

    Held together so `run_streamable_http` takes one shape, not a long
    kwargs list. Constructed by `RunCommand` from individual CLI flags.
    """

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    forwarded_allow_ips: str | None = None
    timeout_graceful_shutdown: int = DEFAULT_TIMEOUT_GRACEFUL_SHUTDOWN
    max_bytes: int = DEFAULT_MAX_BYTES


def make_server() -> FastMCP:
    """Create an MCP server."""
    tool_sets = [
        assetdb_tools,
        docs_tools,
        platform_tools,
    ]
    tools: list[Tool | Callable[..., Any]] = list(chain(*(tool_set() for tool_set in tool_sets)))

    mcp: FastMCP = FastMCP(
        name="Stacklet",
        version=__version__,
        instructions=get_file_text("mcp_info.md"),
        tools=tools,
        lifespan=lifespan,
    )

    @mcp.custom_route("/health", methods=["GET", "HEAD"])
    async def health(request: Request) -> JSONResponse:
        """Liveness probe for ALB target groups.

        Must never touch upstream services: the day that changes, transient
        upstream failures will flap the target group and pull healthy tasks
        out of service.
        """
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "git_sha": os.environ.get("GIT_SHA", "unknown"),
            }
        )

    return mcp


def http_middleware(endpoint: str, max_bytes: int = DEFAULT_MAX_BYTES) -> list[Middleware]:
    """Build the ASGI middleware stack for streamable-http mode.

    Outermost → innermost:
      1. MaxBodySizeMiddleware  — reject oversize requests before any work.
      2. CredentialMiddleware   — extract per-request auth into
         request.state.credentials (except on /health).
      3. FastMCP app (innermost).

    Proxy-header handling is configured on uvicorn directly via
    `run_streamable_http`'s `forwarded_allow_ips` argument, which threads
    through to `uvicorn.Config.forwarded_allow_ips`. uvicorn's own
    ProxyHeadersMiddleware then rewrites `scope['client']` from trusted
    `X-Forwarded-*` before either of our middlewares sees the request.
    Wiring a second ProxyHeadersMiddleware here would either conflict with
    or duplicate that layer.
    """
    return [
        Middleware(MaxBodySizeMiddleware, max_bytes=max_bytes),
        Middleware(CredentialMiddleware, endpoint=endpoint),
    ]


def run_streamable_http(options: HttpTransportOptions) -> None:
    """Start the MCP server in streamable-http transport.

    `STACKLET_ENDPOINT` comes from the process environment, not headers —
    closing the SSRF path where a caller could aim the proxy at a malicious
    backend.

    After building the middleware stack, verify the credential middleware
    is present before starting. Belt-and-suspenders against an accidental
    future refactor that drops it and silently serves server-level
    credentials to every caller.
    """
    endpoint = os.environ.get("STACKLET_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "STACKLET_ENDPOINT must be set in the environment for streamable-http mode."
        )

    middleware = http_middleware(endpoint, max_bytes=options.max_bytes)
    _assert_credential_middleware_present(middleware)

    uvicorn_config: dict[str, Any] = {
        "timeout_graceful_shutdown": options.timeout_graceful_shutdown,
    }
    if options.forwarded_allow_ips is not None:
        uvicorn_config["forwarded_allow_ips"] = options.forwarded_allow_ips

    set_transport_mode(STREAMABLE_HTTP)
    mcp = make_server()
    mcp.run(
        transport="streamable-http",
        host=options.host,
        port=options.port,
        middleware=middleware,
        uvicorn_config=uvicorn_config,
        show_banner=False,
    )


def _assert_credential_middleware_present(stack: list[Middleware]) -> None:
    # Starlette types `item.cls` as `_MiddlewareFactory[P]` which mypy can't
    # identity-check against a concrete class, but the runtime values are
    # the classes we registered.
    if not any(item.cls is CredentialMiddleware for item in stack):  # type: ignore[comparison-overlap]
        raise RuntimeError(
            "streamable-http refuses to start: credential middleware is not wired. "
            "This would silently serve server-level credentials to every caller."
        )
