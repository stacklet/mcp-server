# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Starlette ASGI middleware for the streamable-http transport.

Two middlewares live here:

1. `CredentialMiddleware` extracts the per-request `Authorization` bearer and
   `X-Stacklet-Identity-Token` cookie, wraps them into `StackletCredentials`,
   and stashes the credentials on `request.state.credentials` for tools to
   read via `current_credentials(ctx)`. `/health` is exempt; anything else
   without both headers is rejected with a 401.

2. `MaxBodySizeMiddleware` rejects oversize requests. `Content-Length` over
   the limit is refused up front (413). For chunked/no-`Content-Length`
   requests, `receive()` is wrapped to count bytes; once the running total
   exceeds the cap the middleware sends the 413 and raises
   `ClientDisconnect` so the inner app unwinds cleanly.

The credential endpoint is the server-level `STACKLET_ENDPOINT`, not a value
taken from the request — that closes the SSRF-style path where a caller
would aim the proxy at a malicious backend.
"""

import re

from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .stacklet_auth import StackletCredentials


BEARER_PREFIX = "bearer "
IDENTITY_TOKEN_HEADER = "x-stacklet-identity-token"
HEALTH_PATH = "/health"

DEFAULT_MAX_BYTES = 4 * 1024 * 1024  # 4 MiB

# Stacklet identity tokens are JWTs (`base64url . base64url . base64url`).
# Refusing anything outside this charset blocks header-smuggling tricks like
# `tok; injected=foo` (which would forward a second cookie to upstream) or
# `tok,injected` (cookie list smuggling).
_IDENTITY_TOKEN_RE = re.compile(r"\A[A-Za-z0-9_\-\.]+\Z")


class CredentialMiddleware:
    """Extract per-request Stacklet credentials and stash on request.state.

    Rejects any non-`/health` request missing `Authorization: Bearer ...` or
    `X-Stacklet-Identity-Token` with a 401.
    """

    def __init__(self, app: ASGIApp, endpoint: str) -> None:
        self.app = app
        self.endpoint = endpoint

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path", "") == HEALTH_PATH:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        access_token = _parse_bearer(request.headers.get("authorization"))
        if access_token is None:
            await _reject(scope, receive, send, 401, "missing_authorization")
            return

        identity_token = request.headers.get(IDENTITY_TOKEN_HEADER)
        if not identity_token:
            await _reject(scope, receive, send, 401, "missing_identity_token")
            return
        if not _IDENTITY_TOKEN_RE.match(identity_token):
            await _reject(scope, receive, send, 401, "invalid_identity_token")
            return

        scope.setdefault("state", {})
        request.state.credentials = StackletCredentials(
            endpoint=self.endpoint,
            access_token=access_token,
            identity_token=identity_token,
        )
        await self.app(scope, receive, send)


class MaxBodySizeMiddleware:
    """Reject requests whose body exceeds `max_bytes`.

    Both the fast path (Content-Length header check) and the streaming path
    (wrapped `receive()`) must be in place; a malicious client can omit or
    under-declare Content-Length with chunked transfer encoding.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: if Content-Length is present and over the limit, reject
        # without reading a single byte of body.
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > self.max_bytes:
                    await _reject(scope, receive, send, 413, "payload_too_large")
                    return
                break

        # Streaming path: chunked or missing-Content-Length requests must be
        # counted as they arrive.
        total = 0
        limit = self.max_bytes
        limit_hit = False

        async def guarded_send(message: Message) -> None:
            # After our own 413, drop inner-app messages — we own the wire.
            if limit_hit:
                return
            await send(message)

        async def counted_receive() -> Message:
            nonlocal total, limit_hit
            msg = await receive()
            if limit_hit:
                return {"type": "http.disconnect"}
            if msg["type"] == "http.request":
                body = msg.get("body", b"")
                if body:
                    total += len(body)
                    if total > limit:
                        await _reject(scope, receive, send, 413, "payload_too_large")
                        limit_hit = True
                        return {"type": "http.disconnect"}
            return msg

        try:
            await self.app(scope, counted_receive, guarded_send)
        except ClientDisconnect:
            if not limit_hit:
                raise


def _parse_bearer(value: str | None) -> str | None:
    """Return the bearer token from an Authorization header, or None.

    Accepts case-insensitive `bearer` prefix. Rejects any whitespace within
    the token itself — this is *stricter* than RFC 6750 (which permits
    token68-compatible characters including none of whitespace anyway) and
    is deliberate: a well-formed Stacklet access token never contains
    whitespace, and rejecting it here defends against header-smuggling
    attempts that wedge a second token after a space.
    """
    if not value:
        return None
    stripped = value.strip()
    if not stripped[: len(BEARER_PREFIX)].lower() == BEARER_PREFIX:
        return None
    token = stripped[len(BEARER_PREFIX) :].strip()
    if not token or any(ch.isspace() for ch in token):
        return None
    return token


async def _reject(scope: Scope, receive: Receive, send: Send, status: int, code: str) -> None:
    response = JSONResponse({"error": code}, status_code=status)
    await response(scope, receive, send)
