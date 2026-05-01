# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Tests for DocsClient redirect handling.

Same-host redirects are followed (docs services occasionally canonicalize
paths — e.g. `/guide` → `/guide/`). Cross-host redirects are rejected, since
silently following them would forward the identity-token cookie off the
configured docs host.
"""

import pytest

from stacklet.mcp.docs.client import DocsClient
from stacklet.mcp.stacklet_auth import StackletCredentials


class _FakeResponse:
    def __init__(self, status_code: int, url: str, location: str | None = None) -> None:
        self.status_code = status_code
        self.url = url
        self.headers = {"location": location} if location else {}


class _FakeSession:
    """httpx.AsyncClient stand-in that returns canned responses keyed by URL."""

    def __init__(self, responses: list[tuple[str, _FakeResponse]]) -> None:
        self._responses = dict(responses)
        self.gets: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def get(self, url, cookies, follow_redirects):
        assert not follow_redirects, "DocsClient should always pass follow_redirects=False"
        self.gets.append((url, cookies))
        if url not in self._responses:
            raise AssertionError(f"no canned response for {url}")
        return self._responses[url]


@pytest.fixture
def ctx_stub(monkeypatch):
    creds = StackletCredentials(
        endpoint="https://api.example.com",
        access_token="at",
        identity_token="id-TOK",
    )
    monkeypatch.setattr("stacklet.mcp.docs.client.current_credentials", lambda ctx: creds)
    return object()


class TestSameHostRedirect:
    async def test_follows_same_host(self, ctx_stub, monkeypatch):
        """Trailing-slash canonicalization (same host) is harmless; follow it."""
        final = _FakeResponse(200, "https://docs.example.com/guide/")
        fake = _FakeSession(
            [
                (
                    "https://docs.example.com/guide",
                    _FakeResponse(301, "https://docs.example.com/guide", "/guide/"),
                ),
                ("https://docs.example.com/guide/", final),
            ]
        )
        client = DocsClient()
        monkeypatch.setattr(client, "_async_client", lambda: fake)

        response = await client._get(ctx_stub, "https://docs.example.com/guide")
        assert response is final
        assert len(fake.gets) == 2


class TestCrossHostRedirect:
    async def test_rejects_cross_host(self, ctx_stub, monkeypatch):
        """A redirect to a different host must be refused so the identity
        token cookie never leaves the configured docs host.
        """
        fake = _FakeSession(
            [
                (
                    "https://docs.example.com/doc",
                    _FakeResponse(
                        302,
                        "https://docs.example.com/doc",
                        "https://evil.example.com/steal",
                    ),
                ),
            ]
        )
        client = DocsClient()
        monkeypatch.setattr(client, "_async_client", lambda: fake)

        with pytest.raises(RuntimeError, match="cross-host redirect"):
            await client._get(ctx_stub, "https://docs.example.com/doc")

        # Only the first request should have been made — we must NOT have
        # followed the cross-host redirect (which would have forwarded the
        # cookie).
        assert [u for u, _ in fake.gets] == ["https://docs.example.com/doc"]

    async def test_rejects_scheme_downgrade(self, ctx_stub, monkeypatch):
        """A redirect with the same hostname but downgraded scheme (https → http)
        would forward the identity-token cookie over plaintext on the next
        hop. Refuse it.
        """
        fake = _FakeSession(
            [
                (
                    "https://docs.example.com/doc",
                    _FakeResponse(
                        301,
                        "https://docs.example.com/doc",
                        "http://docs.example.com/doc",
                    ),
                ),
            ]
        )
        client = DocsClient()
        monkeypatch.setattr(client, "_async_client", lambda: fake)

        with pytest.raises(RuntimeError, match="cross-host redirect"):
            await client._get(ctx_stub, "https://docs.example.com/doc")

        # Cookie must not have been forwarded over the http hop.
        assert [u for u, _ in fake.gets] == ["https://docs.example.com/doc"]

    async def test_rejects_port_hop(self, ctx_stub, monkeypatch):
        """A redirect to the same hostname but a different port could land
        the identity-token cookie on a co-tenanted service. Refuse it.
        """
        fake = _FakeSession(
            [
                (
                    "https://docs.example.com/doc",
                    _FakeResponse(
                        301,
                        "https://docs.example.com/doc",
                        "https://docs.example.com:8081/doc",
                    ),
                ),
            ]
        )
        client = DocsClient()
        monkeypatch.setattr(client, "_async_client", lambda: fake)

        with pytest.raises(RuntimeError, match="cross-host redirect"):
            await client._get(ctx_stub, "https://docs.example.com/doc")

        assert [u for u, _ in fake.gets] == ["https://docs.example.com/doc"]

    async def test_redirect_cap(self, ctx_stub, monkeypatch):
        """A service that loops redirects back to the same URL must hit the
        cap rather than spinning forever.
        """

        class _LoopingSession:
            """Returns a same-host 301 on every GET."""

            def __init__(self) -> None:
                self.call_count = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            async def get(self, url, cookies, follow_redirects):
                self.call_count += 1
                return _FakeResponse(301, url, "https://docs.example.com/x")

        session = _LoopingSession()
        client = DocsClient()
        monkeypatch.setattr(client, "_async_client", lambda: session)

        with pytest.raises(RuntimeError, match="exceeded .* redirects"):
            await client._get(ctx_stub, "https://docs.example.com/x")
