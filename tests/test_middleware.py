# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Tests for CredentialMiddleware and MaxBodySizeMiddleware."""

import json

import pytest

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from stacklet.mcp.middleware import CredentialMiddleware, MaxBodySizeMiddleware


ENDPOINT = "https://api.example.com"


async def _echo_credentials(request: Request) -> JSONResponse:
    """Test route that echoes back the credentials stashed on request.state."""
    creds = getattr(request.state, "credentials", None)
    if creds is None:
        return JSONResponse({"credentials": None})
    return JSONResponse(
        {
            "endpoint": creds.endpoint,
            "access_token": creds.access_token,
            "identity_token": creds.identity_token,
        }
    )


async def _health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _app_with_credential_middleware(endpoint: str = ENDPOINT) -> Starlette:
    app = Starlette(
        routes=[
            Route("/mcp", _echo_credentials),
            Route("/health", _health),
        ],
    )
    app.add_middleware(CredentialMiddleware, endpoint=endpoint)
    return app


class TestCredentialMiddleware:
    def test_reject_missing_authorization(self):
        client = TestClient(_app_with_credential_middleware())
        r = client.get("/mcp")
        assert r.status_code == 401
        assert r.json() == {"error": "missing_authorization"}

    def test_reject_missing_identity_token(self):
        client = TestClient(_app_with_credential_middleware())
        r = client.get("/mcp", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 401
        assert r.json() == {"error": "missing_identity_token"}

    def test_accepts_valid_headers(self):
        client = TestClient(_app_with_credential_middleware())
        r = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer access-xyz",
                "X-Stacklet-Identity-Token": "id-abc",
            },
        )
        assert r.status_code == 200
        assert r.json() == {
            "endpoint": ENDPOINT,
            "access_token": "access-xyz",
            "identity_token": "id-abc",
        }

    def test_endpoint_from_server_config_not_header(self):
        """The endpoint must come from server-level config, not a header.

        Otherwise a caller could aim the proxy at a malicious backend.
        """
        client = TestClient(_app_with_credential_middleware(endpoint="https://api.stacklet.io"))
        r = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer a",
                "X-Stacklet-Identity-Token": "i",
                "X-Forwarded-Host": "https://evil.example.com",
            },
        )
        assert r.json()["endpoint"] == "https://api.stacklet.io"

    @pytest.mark.parametrize(
        "header_value,expected_token",
        [
            ("Bearer tok", "tok"),
            ("bearer tok", "tok"),
            ("BEARER tok", "tok"),
            ("  Bearer   tok  ", "tok"),
        ],
    )
    def test_bearer_prefix_case_insensitive(self, header_value, expected_token):
        client = TestClient(_app_with_credential_middleware())
        r = client.get(
            "/mcp",
            headers={
                "Authorization": header_value,
                "X-Stacklet-Identity-Token": "i",
            },
        )
        assert r.status_code == 200
        assert r.json()["access_token"] == expected_token

    @pytest.mark.parametrize(
        "header_value",
        [
            "tok",  # No scheme
            "Basic tok",  # Wrong scheme
            "Bearer",  # No token
            "Bearer ",  # Empty token
            "Bearer tok1 tok2",  # Smuggling: multiple whitespace-delimited segments
        ],
    )
    def test_malformed_authorization_rejected(self, header_value):
        client = TestClient(_app_with_credential_middleware())
        r = client.get(
            "/mcp",
            headers={
                "Authorization": header_value,
                "X-Stacklet-Identity-Token": "i",
            },
        )
        assert r.status_code == 401
        assert r.json() == {"error": "missing_authorization"}

    def test_health_exempt_from_auth(self):
        client = TestClient(_app_with_credential_middleware())
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    @pytest.mark.parametrize(
        "bad_value",
        [
            "real; injected=evil",  # cookie smuggling: second cookie pair
            "real injected",  # whitespace mid-value
            "real,injected",  # comma
            "real=value",  # `=` could split a cookie name/value upstream
        ],
    )
    def test_identity_token_charset_rejected(self, bad_value):
        """Identity-token is forwarded as a cookie value to upstream. Reject
        anything outside the JWT charset so a caller can't smuggle a
        second cookie via `;` or split the cookie value upstream.
        """
        client = TestClient(_app_with_credential_middleware())
        r = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer realtoken",
                "X-Stacklet-Identity-Token": bad_value,
            },
        )
        assert r.status_code == 401
        assert r.json() == {"error": "invalid_identity_token"}

    def test_identity_token_jwt_shaped_accepted(self):
        """A standard JWT-shaped identity token must pass through."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.abc-def_xyz.123"
        client = TestClient(_app_with_credential_middleware())
        r = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer realtoken",
                "X-Stacklet-Identity-Token": jwt,
            },
        )
        assert r.status_code == 200
        assert r.json()["identity_token"] == jwt


def _app_with_body_size_limit(max_bytes: int = 64) -> Starlette:
    async def echo(request: Request) -> JSONResponse:
        body = await request.body()
        return JSONResponse({"length": len(body)})

    app = Starlette(routes=[Route("/mcp", echo, methods=["POST"])])
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_bytes)
    return app


class TestMaxBodySizeMiddleware:
    def test_accepts_under_limit(self):
        client = TestClient(_app_with_body_size_limit(max_bytes=100))
        payload = json.dumps({"ok": True})
        r = client.post("/mcp", content=payload)
        assert r.status_code == 200
        assert r.json() == {"length": len(payload)}

    def test_rejects_over_limit_by_content_length(self):
        """Fast path: declared Content-Length over the limit is rejected
        without reading any body."""
        client = TestClient(_app_with_body_size_limit(max_bytes=10))
        r = client.post("/mcp", content="x" * 100)
        assert r.status_code == 413
        assert r.json() == {"error": "payload_too_large"}

    def test_rejects_streaming_over_limit(self):
        """Streaming path: when Content-Length is unreliable (chunked),
        wrapped receive() counts bytes and rejects once the total exceeds
        the cap."""

        def gen():
            for _ in range(10):
                yield b"x" * 20

        client = TestClient(_app_with_body_size_limit(max_bytes=25))
        r = client.post("/mcp", content=gen())
        assert r.status_code == 413
        assert r.json() == {"error": "payload_too_large"}
