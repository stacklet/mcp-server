"""
Tests for AssetDB MCP tools using FastMCP's in-memory testing pattern.
"""

import pytest

from fastmcp import Client

from stacklet.mcp.mcp import mcp


@pytest.fixture(autouse=True)
def mock_credentials(mock_stacklet_credentials):
    """Auto-apply mock credentials for all tests in this file."""
    return mock_stacklet_credentials


async def test_sql_info():
    """Test the assetdb_sql_info tool returns expected documentation content."""
    async with Client(mcp) as client:
        result = await client.call_tool("assetdb_sql_info", {})

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
