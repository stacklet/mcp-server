# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Per-request credential resolution for tool handlers.

In stdio mode there is one caller per process, so `load_stacklet_auth()` is
read once from env/filesystem and cached on server-wide state. In
`streamable-http` mode each request carries its own credentials in headers,
and middleware stashes them on `request.state.credentials`; this module
reads them back out inside a tool.
"""

from enum import StrEnum

from fastmcp import Context
from fastmcp.server.dependencies import get_http_request

from . import stacklet_auth
from .stacklet_auth import StackletCredentials


class TransportMode(StrEnum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"


# Aliases: call sites typically `from .request_credentials import STREAMABLE_HTTP`.
STDIO = TransportMode.STDIO
STREAMABLE_HTTP = TransportMode.STREAMABLE_HTTP


_TRANSPORT_MODE: TransportMode = TransportMode.STDIO


# Lives outside ServerState deliberately: ServerState is shared across every
# HTTP request in streamable-http mode, so credentials cached there would be a
# cross-user leak. This variable is used only when the transport mode is stdio
# (one user per process); the HTTP path refuses to read from it.
_stdio_credentials: StackletCredentials | None = None


def set_transport_mode(mode: TransportMode) -> None:
    """Record the process-level transport mode at server startup."""
    global _TRANSPORT_MODE
    _TRANSPORT_MODE = TransportMode(mode)


def current_transport_mode() -> TransportMode:
    """Return the process-level transport mode."""
    return _TRANSPORT_MODE


def reset_stdio_credentials() -> None:
    """Drop any cached stdio credentials. Called by test fixtures so each
    test's monkeypatched `load_stacklet_auth` actually runs."""
    global _stdio_credentials
    _stdio_credentials = None


def current_credentials(ctx: Context) -> StackletCredentials:
    """Return the credentials for the in-flight request.

    In `streamable-http` mode, read from `request.state.credentials` where
    the credential middleware stashed them. Missing state is a middleware
    wiring bug and must be loud — silently falling back to
    `load_stacklet_auth()` would serve the container's `~/.stacklet/` (or
    STACKLET_* env vars) to every caller.

    In stdio mode, cache `load_stacklet_auth()` at module level.
    """
    if current_transport_mode() is TransportMode.STREAMABLE_HTTP:
        request = get_http_request()
        creds = getattr(request.state, "credentials", None)
        if creds is None:
            raise RuntimeError(
                "No credentials on request.state — credential middleware is not wired. "
                "Refusing to fall back to server-level credentials in HTTP mode."
            )
        if not isinstance(creds, StackletCredentials):
            # Running under `python -O` strips asserts, so use a real raise.
            # Belt-and-suspenders: the only writer is CredentialMiddleware,
            # but a future middleware that mis-types this attribute must
            # fail loudly rather than smuggle a non-credential through.
            raise RuntimeError(
                f"request.state.credentials is not a StackletCredentials: {type(creds).__name__}"
            )
        return creds

    global _stdio_credentials
    if _stdio_credentials is None:
        _stdio_credentials = stacklet_auth.load_stacklet_auth()
    return _stdio_credentials
