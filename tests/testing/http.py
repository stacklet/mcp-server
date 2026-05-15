# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""Fixtured for mocking HTTP(x) requests."""

import json

from typing import Any

import httpx
import pytest


class MockHTTPXResponse:
    """Mock httpx response object."""

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    @property
    def content(self):
        return self._data.encode()

    @property
    def text(self):
        return self._data

    def json(self):
        return json.loads(self._data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"mocked http {self.status_code}",
                request=None,  # type:ignore
                response=self,  # type:ignore
            )


class ExpectRequest:
    def __init__(self, url, *, method="GET", data=None, status_code=200, response: Any = ""):
        self.expect_url = url
        self.expect_method = method
        self.expect_data = data
        self.status_code = status_code
        self.response = response if isinstance(response, str) else json.dumps(response)

    def respond(self, method, url, **kwargs):
        assert url == self.expect_url, url
        assert method == self.expect_method, method
        data = kwargs.get("params" if method == "GET" else "json")
        assert data == self.expect_data, data
        return MockHTTPXResponse(self.response, self.status_code)


class ExpectationContext:
    def __init__(self, expected_requests: list[ExpectRequest]):
        self.expected_requests = expected_requests

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            return

        if self.expected_requests:
            remaining = [x.expect_url for x in self.expected_requests]
            self.expected_requests.clear()
            raise AssertionError(f"Expected requests not made: {remaining}")


class ExpectedRequestsController:
    def __init__(self):
        self.expected_requests = []

    def next_request(self) -> ExpectRequest:
        """Return the next request."""
        assert self.expected_requests
        return self.expected_requests.pop(0)

    def expect(self, *requests: ExpectRequest) -> ExpectationContext:
        """Return a Context manager that sets up expectations and verifies completion."""
        self.expected_requests = list(requests)  # track the shared state
        return ExpectationContext(self.expected_requests)


def _per_call(kwargs: dict, kind: str, key: str) -> str | None:
    """Return kwargs[kind][key] if present (for session-level auth absence)."""
    mapping = kwargs.get(kind) or {}
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None


def _mock_http_request_with_auth_check(monkeypatch, mock_stacklet_credentials, auth_check_func):
    """Shared implementation for HTTP mocking with different auth checks."""

    controller = ExpectedRequestsController()

    async def mock_request(self, method, url, **kwargs):
        auth_check_func(kwargs, mock_stacklet_credentials)
        return controller.next_request().respond(method, url, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient.request", mock_request)
    return controller


@pytest.fixture
def mock_http_cookie(monkeypatch, mock_stacklet_credentials):
    """Mock httpx.AsyncClient.request with cookie-based auth expectations.

    Auth must be passed per-call via `cookies=`; session-level cookie jars
    are a regression.
    """

    def check_cookie_auth(kwargs, credentials):
        cookie = _per_call(kwargs, "cookies", "stacklet-auth")
        assert cookie == credentials.identity_token, (
            "expected stacklet-auth cookie on per-call kwargs; clients must "
            "pass auth per-call, not via session defaults"
        )

    return _mock_http_request_with_auth_check(
        monkeypatch, mock_stacklet_credentials, check_cookie_auth
    )


@pytest.fixture
def mock_http_bearer(monkeypatch, mock_stacklet_credentials):
    """Mock httpx.AsyncClient.request with bearer-token auth expectations.

    Auth must be passed per-call via `headers=`; session-level defaults
    are a regression.
    """

    def check_bearer_auth(kwargs, credentials):
        expected = f"Bearer {credentials.access_token}"
        actual = _per_call(kwargs, "headers", "Authorization")
        assert actual == expected, (
            "expected Authorization header on per-call kwargs; clients must "
            "pass auth per-call, not via session defaults"
        )

    return _mock_http_request_with_auth_check(
        monkeypatch, mock_stacklet_credentials, check_bearer_auth
    )
