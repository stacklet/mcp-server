"""
Tests for Platform MCP tools using FastMCP's in-memory testing pattern.
"""

import pytest

from graphql import build_schema

from .testing.mcp import MCPBearerTest, MCPTest, json_guard_parametrize


pytestmark = pytest.mark.usefixtures("mock_stacklet_credentials")


class TestGraphQLInfo(MCPTest):
    tool_name = "platform_graphql_info"

    async def test_returns_expected_documentation(self):
        """Test the platform_graphql_info tool returns expected documentation content."""
        result = await self.assert_call({})

        # Verify the content contains expected Platform GraphQL documentation
        assert "Stacklet GraphQL API Overview" in result.text
        assert "GraphQL" in result.text


class PlatformSchemaTest(MCPBearerTest):
    """Base test class for Platform tools that need a mocked GraphQL schema."""

    SCHEMA = """
        type Query {
          accounts: AccountList
        }

        type AccountList {
          accounts: [Account]
        }

        type Account {
          id: ID!
          name: String
        }"""

    @pytest.fixture(autouse=True)
    def mock_schema(self, monkeypatch):
        """Mock PlatformClient.get_schema to return our test schema."""
        schema = build_schema(self.SCHEMA)

        async def mock_get_schema(self):
            return schema

        monkeypatch.setattr(
            "stacklet.mcp.platform.graphql.PlatformClient.get_schema", mock_get_schema
        )


class TestGraphqQLGetTypes(PlatformSchemaTest):
    tool_name = "platform_graphql_get_types"

    async def test_get_existing_types(self):
        """Test getting SDL definitions for existing types."""
        result = await self.assert_call({"type_names": ["Account", "String"]})

        type_defs = result.json()
        # Should have definitions for both types
        assert "Account" in type_defs
        assert "String" in type_defs

        # Account should be an object type with fields
        account_def = type_defs["Account"]
        assert "type Account {" in account_def
        assert "id: ID!" in account_def

        # String is a scalar type
        string_def = type_defs["String"]
        assert "scalar String" in string_def

    async def test_get_nonexistent_types(self):
        """Test getting types that don't exist returns empty dict for missing ones."""
        result = await self.assert_call({"type_names": ["Acc", "count", "Account"]})

        type_defs = result.json()
        # Should only have the existing type
        assert "Account" in type_defs
        assert "Acc" not in type_defs
        assert "count" not in type_defs

    @json_guard_parametrize([["Query"], ["Account", "AccountList"]])
    async def test_type_names_json_guard(self, mangle, value):
        """Test that type_names parameter works with JSON guard."""
        result = await self.assert_call({"type_names": mangle(value)})
        assert sorted(result.json().keys()) == sorted(value)
