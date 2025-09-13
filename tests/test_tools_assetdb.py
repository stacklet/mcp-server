"""
Tests for AssetDB MCP tools using FastMCP's in-memory testing pattern.
"""

import json

from typing import Any

import pytest

from fastmcp.client.client import CallToolResult, Client

from stacklet.mcp.mcp import mcp

from . import factory
from .conftest import ExpectRequest
from .mcp_test import MCPTest, json_guard_param


pytestmark = pytest.mark.usefixtures("mock_stacklet_credentials")


@pytest.fixture
async def mcp_client(mock_stacklet_credentials):
    async with Client(mcp) as client:
        yield client


async def test_sql_info(mcp_client):
    """Test the assetdb_sql_info tool returns expected documentation content."""
    result = await mcp_client.call_tool("assetdb_sql_info", {})

    # Verify we get the expected result structure
    assert hasattr(result, "content")
    assert len(result.content) == 1
    assert hasattr(result.content[0], "text")

    content = result.content[0].text

    # Verify the content contains expected AssetDB documentation
    assert "Stacklet AssetDB SQL Overview" in content
    assert "PostgreSQL 16" in content
    assert "resources" in content
    assert "resource_revisions" in content
    assert "account_cost" in content

    # Verify it contains guidance about querying
    assert "LIMIT" in content
    assert "indexes" in content
    assert "EXPLAIN" in content


class TestQueryList(MCPTest):
    tool_name = "assetdb_query_list"

    async def test_basic(self, mock_assetdb_list_queries_response):
        with self.http.expect(
            ExpectRequest(
                "https://example.com/api/queries",
                data={"page": 1, "page_size": 25},
                response=mock_assetdb_list_queries_response,
            ),
        ):
            result = await self.assert_call({})

        # Verify tool response structure and content
        data = get_json(result)

        # Check response structure
        assert "queries" in data
        assert "pagination" in data

        # Check query data transformation
        assert len(data["queries"]) == 2
        assert data["queries"][0]["id"] == 123
        assert data["queries"][0]["name"] == "Test Query 1"
        assert data["queries"][0]["has_parameters"] is True
        assert data["queries"][1]["has_parameters"] is False

        # Check pagination
        assert data["pagination"]["total_count"] == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 25

    @json_guard_param("tags_param", ["production", "alerts"])
    async def test_tags_param(self, mock_assetdb_list_queries_response, tags_param):
        """Test the assetdb_query_list tool with search and pagination parameters."""
        with self.http.expect(
            ExpectRequest(
                "https://example.com/api/queries",
                data={
                    "page": 1,
                    "page_size": 25,
                    "q": "monitoring metrics",
                    "tags": ["production", "alerts"],
                },
                response={"results": []},
            ),
        ):
            result = await self.assert_call(
                {"search": "monitoring metrics", "tags": tags_param},
            )

        # Verify response structure is correct
        data = get_json(result)
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 25
        assert len(data["queries"]) == 0


@json_guard_param("id_param", 123)
async def test_query_get_success(mcp_client, mock_assetdb_request, id_param):
    """Test the assetdb_query_get tool with valid query ID."""
    model = factory.make_assetdb_query_dict(id=123)
    with mock_assetdb_request.expect(
        ExpectRequest("https://example.com/api/queries/123", response=model),
    ):
        result = await mcp_client.call_tool("assetdb_query_get", {"query_id": id_param})

    expect = factory.make_assetdb_query_dict(id=123)
    expect.pop("visualizations")
    assert get_json(result) == expect


async def test_query_get_not_found(mcp_client, mock_assetdb_request):
    """Test the assetdb_query_get tool with non-existent query ID."""
    with mock_assetdb_request.expect(
        ExpectRequest("https://example.com/api/queries/999", status_code=404),
    ):
        result = await mcp_client.call_tool_mcp("assetdb_query_get", {"query_id": 999})

    assert result.isError
    assert get_text(result) == "Error calling tool 'assetdb_query_get': http 404"


def get_text(result: CallToolResult) -> str:
    [content] = result.content
    return content.text  # type:ignore


def get_json(result: CallToolResult) -> Any:
    return json.loads(get_text(result))
