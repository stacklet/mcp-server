# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Tests for stacklet/mcp/server.py: /health route and HTTP-mode wiring."""

import pytest

from starlette.middleware import Middleware
from starlette.testclient import TestClient

from stacklet.mcp.middleware import CredentialMiddleware, MaxBodySizeMiddleware
from stacklet.mcp.server import (
    HttpTransportOptions,
    _assert_credential_middleware_present,
    http_middleware,
    make_server,
    run_streamable_http,
)


class TestHttpMiddlewareStack:
    def test_body_size_first(self):
        stack = http_middleware("https://api.example.com")
        assert stack[0].cls is MaxBodySizeMiddleware

    def test_credential_last(self):
        stack = http_middleware("https://api.example.com")
        assert stack[-1].cls is CredentialMiddleware

    def test_endpoint_passed_to_credential_middleware(self):
        stack = http_middleware("https://api.foo.example/")
        creds_item = next(m for m in stack if m.cls is CredentialMiddleware)
        assert creds_item.kwargs == {"endpoint": "https://api.foo.example/"}

    def test_max_bytes_passed_to_body_size_middleware(self):
        stack = http_middleware("https://api.example.com", max_bytes=123)
        body = next(m for m in stack if m.cls is MaxBodySizeMiddleware)
        assert body.kwargs == {"max_bytes": 123}

    def test_no_explicit_proxy_headers_middleware(self):
        """Proxy-header handling belongs to uvicorn's outer middleware,
        configured via uvicorn.Config.forwarded_allow_ips. A second inner
        layer would either conflict or duplicate.
        """
        class_names = [item.cls.__name__ for item in http_middleware("https://api.example.com")]
        assert "ProxyHeadersMiddleware" not in class_names


class TestStartupInvariant:
    def test_raises_without_credential_middleware(self):
        stack = [Middleware(MaxBodySizeMiddleware)]
        with pytest.raises(RuntimeError, match="credential middleware is not wired"):
            _assert_credential_middleware_present(stack)

    def test_passes_with_credential_middleware(self):
        stack = http_middleware("https://api.example.com")
        # Must not raise.
        _assert_credential_middleware_present(stack)


@pytest.fixture
def restore_transport_mode():
    """Reset the process-level transport mode after a test mutates it.

    `run_streamable_http` flips `_TRANSPORT_MODE` to 'streamable-http'; if a
    test runs it and doesn't restore, subsequent stdio tests hit the HTTP
    path of `current_credentials` and fail.
    """
    from stacklet.mcp.request_credentials import STDIO, set_transport_mode

    yield
    set_transport_mode(STDIO)


class TestHttpTransportOptions:
    def test_frozen(self):
        """frozen=True is the safety story — pass options around and they
        can't be mutated out from under `run_streamable_http`."""
        from dataclasses import FrozenInstanceError

        options = HttpTransportOptions()
        with pytest.raises(FrozenInstanceError):
            options.host = "evil.example.com"  # type: ignore[misc]


class TestRunStreamableHttp:
    def test_raises_without_stacklet_endpoint(self, monkeypatch):
        monkeypatch.delenv("STACKLET_ENDPOINT", raising=False)
        with pytest.raises(RuntimeError, match="STACKLET_ENDPOINT must be set"):
            run_streamable_http(HttpTransportOptions())

    def test_uvicorn_config_threaded_through(self, monkeypatch, restore_transport_mode):
        """uvicorn.Config must receive timeout_graceful_shutdown and
        forwarded_allow_ips from run_streamable_http. Without this, the
        README's hosting guide is unreachable.
        """
        monkeypatch.setenv("STACKLET_ENDPOINT", "https://api.example.com")

        captured_kwargs: dict = {}

        def capture_run(self, **kwargs):
            captured_kwargs.update(kwargs)

        monkeypatch.setattr("fastmcp.FastMCP.run", capture_run)

        run_streamable_http(
            HttpTransportOptions(
                forwarded_allow_ips="10.0.0.0/8",
                timeout_graceful_shutdown=400,
            )
        )

        uvicorn_config = captured_kwargs["uvicorn_config"]
        assert uvicorn_config["timeout_graceful_shutdown"] == 400
        assert uvicorn_config["forwarded_allow_ips"] == "10.0.0.0/8"

    def test_forwarded_allow_ips_omitted_when_none(self, monkeypatch, restore_transport_mode):
        """When the operator doesn't set forwarded_allow_ips, let uvicorn
        apply its own default (127.0.0.1) rather than forcing an override.
        """
        monkeypatch.setenv("STACKLET_ENDPOINT", "https://api.example.com")

        captured_kwargs: dict = {}

        def capture_run(self, **kwargs):
            captured_kwargs.update(kwargs)

        monkeypatch.setattr("fastmcp.FastMCP.run", capture_run)

        run_streamable_http(HttpTransportOptions())

        uvicorn_config = captured_kwargs["uvicorn_config"]
        assert "forwarded_allow_ips" not in uvicorn_config
        assert uvicorn_config["timeout_graceful_shutdown"] == 305


class TestHealthRoute:
    """/health must be reachable without auth and must not touch upstream."""

    def test_returns_ok(self):
        mcp = make_server()
        client = TestClient(mcp.http_app(transport="streamable-http"))
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    def test_accepts_head(self):
        mcp = make_server()
        client = TestClient(mcp.http_app(transport="streamable-http"))
        r = client.head("/health")
        assert r.status_code == 200
