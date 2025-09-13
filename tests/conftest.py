"""
Common test fixtures and configuration.
"""

import json

from typing import Any

import httpx
import pytest

from stacklet.mcp.stacklet_auth import StackletCredentials


@pytest.fixture
def mock_stacklet_credentials(monkeypatch):
    """Mock load_stacklet_auth to return fake test credentials."""
    fake_credentials = StackletCredentials(
        endpoint="https://example.com/",
        access_token="fake-access-token",
        identity_token="fake-identity-token",
    )

    monkeypatch.setattr("stacklet.mcp.mcp.load_stacklet_auth", lambda: fake_credentials)
    return fake_credentials


class MockHTTPXResponse:
    """Mock httpx response object."""

    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return json.loads(self._data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"http {self.status_code}", request=None, response=self)  # type:ignore


class ExpectRequest:
    def __init__(self, url, *, method="GET", data=None, status_code=200, response: Any = ""):
        self.expect_url = url
        self.expect_method = method
        self.expect_data = data
        self.status_code = status_code
        self.response = response if isinstance(response, str) else json.dumps(response)

    def respond(self, method, url, **kwargs):
        assert url == self.expect_url
        assert method == self.expect_method
        data = kwargs.get("params" if method == "GET" else "json")
        assert data == self.expect_data
        return MockHTTPXResponse(self.response, self.status_code)


@pytest.fixture
def mock_assetdb_request(monkeypatch, mock_stacklet_credentials):
    """Mock httpx.AsyncClient.request with ordered expectations."""

    # Funky shared state with ExpectationContext
    expected_requests: list[ExpectRequest] = []

    async def mock_request(self, method, url, **kwargs):
        assert expected_requests
        assert self.cookies["stacklet-auth"] == mock_stacklet_credentials.identity_token
        return expected_requests.pop(0).respond(method, url, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient.request", mock_request)

    # Return controller object
    class MockController:
        def expect(self, *requests: ExpectRequest):
            """Context manager that sets up expectations and verifies completion."""

            class ExpectationContext:
                def __enter__(self):
                    # Add all expectations to the queue
                    expected_requests.extend(requests)
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    if expected_requests:
                        remaining = [x.expect_url for x in expected_requests]
                        expected_requests.clear()  # Clean up
                        raise AssertionError(f"Expected requests not made: {remaining}")

            return ExpectationContext()

    return MockController()


@pytest.fixture
def mock_assetdb_list_queries_response():
    """Sample response from Redash queries list API."""
    from .factory import make_assetdb_query_dict, make_assetdb_query_list_response

    queries = [
        make_assetdb_query_dict(
            id=123,
            name="Test Query 1",
            description="A sample query",
            tags=["production", "monitoring"],
            user_name="Test User",
            parameters=[{"name": "limit", "type": "number"}],
            include_visualizations=False,
        ),
        make_assetdb_query_dict(
            id=456,
            name="Test Query 2",
            description="",
            tags=[],
            user_name="Another User",
            is_draft=True,
            parameters=[],
            include_visualizations=False,
        ),
    ]

    return make_assetdb_query_list_response(queries, total_count=2)


@pytest.fixture
def mock_assetdb_query_detail_response():
    """Sample response from Redash query detail API (with visualizations that get removed)."""
    from .factory import make_assetdb_query_dict

    return make_assetdb_query_dict(
        id=123,
        name="Test Query Detail",
        description="A detailed sample query",
        query="SELECT id, name FROM resources WHERE created_at > '2024-01-01' LIMIT {{limit}}",
        tags=["production", "monitoring", "resources"],
        user_name="Test User",
        user_email="test@example.com",
        parameters=[{"name": "limit", "type": "number", "value": 10}],
        visualizations=[
            {
                "id": 1,
                "type": "TABLE",
                "name": "Table",
                "description": "",
                "options": {},
                "updated_at": "2024-01-01T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ],
        include_visualizations=True,
    )
