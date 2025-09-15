"""
Tests for Platform MCP tools using FastMCP's in-memory testing pattern.
"""

from unittest.mock import ANY

import pytest

from graphql import build_schema

from .conftest import ExpectRequest
from .testing.mcp import MCPBearerTest, MCPTest, json_guard_parametrize


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


class TestGraphQLQuery(MCPBearerTest):
    tool_name = "platform_graphql_query"

    def r(
        self, query: str, variables: dict | None = None, *, response, status_code=200
    ) -> ExpectRequest:
        """Helper to create GraphQL request expectations."""
        return ExpectRequest(
            "https://api.example.com/",
            method="POST",
            data={"query": query, "variables": variables or {}},
            response=response,
            status_code=status_code,
        )

    async def test_successful_query(self):
        """Test a successful GraphQL query."""
        query = "{ accounts { accounts { id name } } }"
        variables = {"limit": 10}
        data = {"accounts": {"accounts": [{"id": "123", "name": "Test Account"}]}}

        with self.http.expect(self.r(query, variables, response=graphql_success_response(data))):
            result = await self.assert_call({"query": query, "variables": variables})

        assert result.json() == {
            "query": query,
            "variables": variables,
            "data": data,
            "errors": None,
        }

    async def test_query_with_errors(self):
        """Test a GraphQL query that returns errors."""
        query = "{ invalidField }"
        error = graphql_field_error(
            "Cannot query field 'invalidField' on type 'Query'.",
            ["invalidField", 0],  # 0 is not accurate, just testing int path segments work
        )

        with self.http.expect(self.r(query, response=graphql_error_response([error]))):
            result = await self.assert_call({"query": query})

        assert result.json() == {
            "query": query,
            "variables": {},
            "data": None,
            "errors": [error | {"extensions": None}],  # Add extensions field for our model
        }

    async def test_query_minimal(self):
        """Test a minimal GraphQL query without variables."""
        query = "{ __typename }"
        data = {"__typename": "Query"}

        with self.http.expect(self.r(query, response=graphql_success_response(data))):
            result = await self.assert_call({"query": query})

        assert result.json() == {
            "query": query,
            "variables": {},
            "data": data,
            "errors": None,
        }

    @json_guard_parametrize(
        [
            {},
            {"limit": 10},
            {"userId": "123", "active": True},
            {"filters": {"region": "us-east-1", "tags": ["prod", "api"]}},
        ]
    )
    async def test_json_guard_variables(self, mangle, value):
        """Test that variables parameter works with JSON guard."""
        query = "{ accounts }"
        data = {"accounts": []}

        with self.http.expect(self.r(query, value, response=graphql_success_response(data))):
            result = await self.assert_call({"query": query, "variables": mangle(value)})

        # Verify that the variables were passed through correctly
        assert result.json()["variables"] == value

    @pytest.mark.parametrize("status_code", [400, 403, 500, 502])
    async def test_http_error_with_valid_graphql(self, status_code):
        """Test HTTP 4xx/5xx status but with valid GraphQL response - should parse GraphQL."""
        query = "{ platform { version } }"
        data = {"platform": {"version": "test-version"}}

        # Backend erroneously returns error status but with valid GraphQL data
        with self.http.expect(
            self.r(query, response=graphql_success_response(data), status_code=status_code)
        ):
            result = await self.assert_call({"query": query})

        # Should parse the GraphQL data despite HTTP error status
        assert result.json() == {
            "query": query,
            "variables": {},
            "data": data,
            "errors": None,
        }

    @pytest.mark.parametrize("status_code", [200, 400, 403, 500, 502])
    @pytest.mark.parametrize(
        "response_content",
        [
            "invalid json content",  # Invalid JSON
            '{"unexpected": "format"}',  # Valid JSON but not GraphQL structure
            '{"data": "not an object"}',  # GraphQL-like but invalid data type
        ],
    )
    async def test_http_codes_with_invalid_response(self, status_code, response_content):
        """Test HTTP 4xx/5xx with invalid JSON or unexpected format - should raise HTTP error."""
        query = "{ platform { version } }"

        with self.http.expect(self.r(query, response=response_content, status_code=status_code)):
            # Should raise an error due to invalid response content
            result = await self.assert_call({"query": query}, error=True)
            # The error should contain the original response content
            assert response_content in result.text


def graphql_success_response(data):
    """Factory for successful GraphQL responses."""
    return {"data": data}


def graphql_error_response(errors):
    """Factory for GraphQL error responses."""
    return {"data": None, "errors": errors}


def graphql_field_error(message: str, field_path: list, line: int = 1, column: int = 3):
    """Factory for GraphQL field errors with extensions."""
    return {
        "message": message,
        "locations": [{"line": line, "column": column}],
        "path": field_path,
    }
