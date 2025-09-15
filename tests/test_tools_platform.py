"""
Tests for Platform MCP tools using FastMCP's in-memory testing pattern.
"""

from unittest.mock import ANY

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

    async def test_success(self):
        result = await self.assert_call({"type_names": ["Account", "String"]})

        response = result.json()
        # Should have requested types recorded
        assert response["asked_for"] == ["Account", "String"]
        # Should have found both types
        assert response["not_found"] == []

        type_defs = response["found_sdl"]
        assert "Account" in type_defs
        assert "String" in type_defs

        # Account should be an object type with fields
        account_def = type_defs["Account"]
        assert "type Account {" in account_def
        assert "id: ID!" in account_def

        # String is a scalar type
        string_def = type_defs["String"]
        assert "scalar String" in string_def

    async def test_nonexistent(self):
        result = await self.assert_call({"type_names": ["Acc", "count", "Account"]})

        response = result.json()
        # Should have requested types recorded
        assert response["asked_for"] == ["Acc", "count", "Account"]
        # Should have found only Account, missing Acc and count
        assert response["not_found"] == ["Acc", "count"]

        type_defs = response["found_sdl"]
        # Should only have the existing type
        assert "Account" in type_defs
        assert "Acc" not in type_defs
        assert "count" not in type_defs

    @json_guard_parametrize([[], ["Query"], ["Account", "AccountList"]])
    async def test_json_guard(self, mangle, value):
        """Test that type_names parameter works with JSON guard."""
        result = await self.assert_call({"type_names": mangle(value)})
        assert result.json() == {
            "asked_for": value,
            "found_sdl": {k: ANY for k in value},
            "not_found": [],
        }


class TestGraphQLListTypes(PlatformSchemaTest):
    tool_name = "platform_graphql_list_types"

    async def test_all_types(self):
        """Test listing all available types."""
        result = await self.assert_call({})

        response = result.json()
        assert response["searched_for"] is None
        # Should include built-in GraphQL types and our custom types
        assert {
            "String",
            "ID",
            "Query",
            "Account",
            "AccountList",
        }.issubset(response["found_types"])

    async def test_filter(self):
        """Test filtering types with exact match."""
        result = await self.assert_call({"match": "Account"})
        assert result.json() == {
            "searched_for": "Account",
            "found_types": ["Account", "AccountList"],
        }

    async def test_filter_types_exact_match(self):
        """Test filtering types with exact match."""
        result = await self.assert_call({"match": "^Account$"})
        assert result.json() == {
            "searched_for": "^Account$",
            "found_types": ["Account"],
        }

    async def test_filter_types_no_matches(self):
        """Test filtering with pattern that matches nothing."""
        result = await self.assert_call({"match": "NonExistent"})
        assert result.json() == {
            "searched_for": "NonExistent",
            "found_types": [],
        }
