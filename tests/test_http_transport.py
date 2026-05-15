# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""End-to-end transport tests for streamable-http.

The critical test here is `TestConcurrencyIsolation.test_interleaved_requests`:
two concurrent requests carry different credentials, we rendezvous them mid-
handler via asyncio.Event, and verify each request sees its own credentials
through the await. If `request.state.credentials` were somehow shared or
leaked across requests this test would fail.
"""

import asyncio
import logging
import subprocess

from pathlib import Path

import httpx
import pytest

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from stacklet.mcp.middleware import CredentialMiddleware
from stacklet.mcp.request_credentials import STDIO, STREAMABLE_HTTP, set_transport_mode
from stacklet.mcp.upstream_errors import sanitize_error_body


ENDPOINT = "https://api.example.com"


class _Barrier:
    """Two-party rendezvous using asyncio.Event pairs.

    Both parties call `meet()`; neither returns until both have arrived.
    Deterministic — no asyncio.sleep tuning required.
    """

    def __init__(self) -> None:
        self.arrived_a = asyncio.Event()
        self.arrived_b = asyncio.Event()
        self._seen = 0

    async def meet(self) -> None:
        self._seen += 1
        if self._seen == 1:
            self.arrived_a.set()
            await self.arrived_b.wait()
        else:
            self.arrived_b.set()
            await self.arrived_a.wait()


@pytest.fixture
def barrier():
    return _Barrier()


@pytest.fixture
def test_app(barrier):
    """ASGI app with a single /echo route that reads request.state.credentials
    through an asyncio.Event rendezvous. The rendezvous forces both in-flight
    requests to be suspended at the same instant, so if `request.state` leaked
    across requests we'd see it as one request reading the other's creds.
    """

    async def echo(request: Request) -> JSONResponse:
        # Capture credentials BEFORE the rendezvous.
        pre = request.state.credentials
        # Force a scheduling hop that would reveal any cross-request state.
        await barrier.meet()
        # Re-read AFTER the rendezvous — must still be this request's creds.
        post = request.state.credentials
        return JSONResponse(
            {
                "pre_access_token": pre.access_token,
                "post_access_token": post.access_token,
                "identity_token": post.identity_token,
            }
        )

    app = Starlette(routes=[Route("/echo", echo)])
    app.add_middleware(CredentialMiddleware, endpoint=ENDPOINT)
    return app


class TestConcurrencyIsolation:
    async def test_interleaved_requests(self, test_app, barrier):
        """Two concurrent requests with distinct tokens must each see their
        own credentials through the rendezvous. This is the make-or-break
        test for the per-request credential design.
        """
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            responses = await asyncio.gather(
                client.get(
                    "/echo",
                    headers={
                        "Authorization": "Bearer token-alice",
                        "X-Stacklet-Identity-Token": "id-alice",
                    },
                ),
                client.get(
                    "/echo",
                    headers={
                        "Authorization": "Bearer token-bob",
                        "X-Stacklet-Identity-Token": "id-bob",
                    },
                ),
            )

        assert all(r.status_code == 200 for r in responses)
        bodies = [r.json() for r in responses]
        seen_access = sorted(b["post_access_token"] for b in bodies)
        seen_id = sorted(b["identity_token"] for b in bodies)
        assert seen_access == ["token-alice", "token-bob"]
        assert seen_id == ["id-alice", "id-bob"]

        # Crucial: pre-rendezvous creds must match post-rendezvous creds
        # within the same request — no swap across the await.
        for body in bodies:
            assert body["pre_access_token"] == body["post_access_token"]


class TestTokenLogScrubbing:
    SENTINEL_ACCESS = "SENTINEL-ACCESS-TOKEN-zzz"
    SENTINEL_IDENTITY = "SENTINEL-IDENTITY-TOKEN-zzz"

    async def _request(self, headers):
        async def ok(request: Request) -> JSONResponse:
            # Touch the credentials so the middleware path runs end-to-end.
            _ = request.state.credentials
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/echo", ok)])
        app.add_middleware(CredentialMiddleware, endpoint=ENDPOINT)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/echo", headers=headers)

    async def test_tokens_not_logged_on_happy_path(self, caplog):
        caplog.set_level(logging.DEBUG)
        await self._request(
            {
                "Authorization": f"Bearer {self.SENTINEL_ACCESS}",
                "X-Stacklet-Identity-Token": self.SENTINEL_IDENTITY,
            }
        )
        combined = "\n".join(rec.getMessage() for rec in caplog.records)
        assert self.SENTINEL_ACCESS not in combined
        assert self.SENTINEL_IDENTITY not in combined

    async def test_tokens_not_in_error_body_passthrough(self):
        """Sanitizer must scrub any Bearer token or identity-token cookie
        that might land in an upstream error body we pass through."""
        body_with_token = (
            f'{{"error": "upstream misbehaved", "echoed": "Bearer {self.SENTINEL_ACCESS}"}}\n'
            f"Set-Cookie: stacklet-auth={self.SENTINEL_IDENTITY}"
        )
        sanitized = sanitize_error_body(body_with_token)
        assert self.SENTINEL_ACCESS not in sanitized
        assert self.SENTINEL_IDENTITY not in sanitized
        assert "redacted" in sanitized


class TestTransportModeSet:
    def test_stdio_is_default(self):
        # After any other test that set a non-stdio mode, restore stdio.
        set_transport_mode(STDIO)
        from stacklet.mcp.request_credentials import current_transport_mode

        assert current_transport_mode() == STDIO

    def test_streamable_http_round_trip(self):
        set_transport_mode(STREAMABLE_HTTP)
        from stacklet.mcp.request_credentials import current_transport_mode

        assert current_transport_mode() == STREAMABLE_HTTP
        set_transport_mode(STDIO)  # reset


class TestToolsLintInvariant:
    """Tools must not spawn create_task / ensure_future on Stacklet client
    calls — credentials are scoped to the in-flight request, not to tasks
    that outlive it. Enforced as a grep over the whole stacklet/mcp/ tree
    (not just tools.py) because a helper in utils/ could evade a
    tools-only check.
    """

    def test_no_create_task_in_stacklet_package(self):
        # Anchor on this test file's location so the check works regardless
        # of pytest's cwd. A path-based test that silently passes from the
        # wrong cwd is worse than no test — false confidence.
        root = Path(__file__).resolve().parents[1] / "stacklet" / "mcp"
        assert root.is_dir(), f"expected {root} to exist"

        # Catch the common shapes. Not exhaustive — `asyncio.Task(...)` and
        # `functools.partial(asyncio.create_task, ...)` can evade this via
        # indirection. A targeted AST check would be more robust, but this
        # tripwire is good enough for the common accidental pattern.
        forbidden = (
            r"create_task\b",
            r"ensure_future\b",
            r"asyncio\.Task\(",
        )
        result = subprocess.run(
            [
                "grep",
                "-r",
                "-E",
                "|".join(forbidden),
                "-l",
                "--include=*.py",
                str(root),
            ],
            capture_output=True,
            text=True,
        )
        offenders = result.stdout.strip()
        assert not offenders, (
            f"Files using create_task/ensure_future/asyncio.Task in stacklet/mcp:\n"
            f"{offenders}\n"
            "Any such call risks reading request.state.credentials after the "
            "request has returned. If legitimately needed, add an allowlist."
        )


class TestSharedTransportInvariants:
    """Each client keeps a shared AsyncHTTPTransport for connection pool reuse
    but must construct a fresh AsyncClient per call so cookie jars and
    default-header mutations stay isolated to a single request.
    """

    def test_platform_client_has_shared_transport(self):
        from stacklet.mcp.platform.graphql import PlatformClient

        client = PlatformClient()
        # Two calls to `_async_client()` produce fresh AsyncClient instances
        # but bound to the same transport object.
        c1 = client._async_client()
        c2 = client._async_client()
        assert c1 is not c2
        assert c1._transport is c2._transport
        assert c1._transport is client._transport

    def test_assetdb_client_has_shared_transport(self):
        from stacklet.mcp.assetdb.redash import AssetDBClient

        client = AssetDBClient()
        c1 = client._async_client()
        c2 = client._async_client()
        assert c1 is not c2
        assert c1._transport is c2._transport
        assert c1._transport is client._transport

    def test_docs_client_has_shared_transport(self):
        from stacklet.mcp.docs.client import DocsClient

        client = DocsClient()
        c1 = client._async_client()
        c2 = client._async_client()
        assert c1 is not c2
        assert c1._transport is c2._transport
        assert c1._transport is client._transport

    def test_clients_have_no_credential_attributes(self):
        import re

        from stacklet.mcp.assetdb.redash import AssetDBClient
        from stacklet.mcp.docs.client import DocsClient
        from stacklet.mcp.platform.graphql import PlatformClient

        pattern = re.compile(r"credential|token|auth", re.IGNORECASE)
        for client in (PlatformClient(), AssetDBClient(), DocsClient()):
            for attr in vars(client):
                assert not pattern.search(attr), (
                    f"{type(client).__name__}.{attr} looks credential-like; "
                    "the client must not hold per-user state on its instance."
                )
