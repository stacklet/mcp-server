"""
Tests for AssetDB MCP tools using FastMCP's in-memory testing pattern.
"""

import json

import pytest

from fastmcp import Client

from stacklet.mcp.mcp import mcp

from .conftest import ExpectRequest


@pytest.fixture(autouse=True)
def mock_credentials(mock_stacklet_credentials):
    """Auto-apply mock credentials for all tests in this file."""
    return mock_stacklet_credentials


@pytest.fixture
async def mcp_client(mock_credentials):
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


async def test_query_list_basic(
    mcp_client, mock_assetdb_request, mock_assetdb_list_queries_response
):
    """Test the assetdb_query_list tool with default parameters."""
    with mock_assetdb_request.expect(
        ExpectRequest(
            url="https://example.com/api/queries",
            data={"page": 1, "page_size": 25},
            response=mock_assetdb_list_queries_response,
        ),
    ):
        result = await mcp_client.call_tool("assetdb_query_list", {})

    # Verify tool response structure and content
    assert hasattr(result, "content")
    assert len(result.content) == 1
    data = json.loads(result.content[0].text)

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


async def test_query_list_with_parameters(
    mcp_client, mock_assetdb_request, mock_assetdb_list_queries_response
):
    """Test the assetdb_query_list tool with search and pagination parameters."""
    with mock_assetdb_request.expect(
        ExpectRequest(
            url="https://example.com/api/queries",
            data={
                "page": 1,
                "page_size": 25,
                "q": "monitoring metrics",
                "tags": ["production", "alerts"],
            },
            response={"results": []},
        ),
    ):
        result = await mcp_client.call_tool(
            "assetdb_query_list",
            {
                "search": "monitoring metrics",
                "tags": ["production", "alerts"],
            },
        )

    # Verify response structure is correct
    data = json.loads(result.content[0].text)
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["page_size"] == 25
    assert len(data["queries"]) == 0
