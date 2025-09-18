"""
Tests for Platform MCP tools using FastMCP's in-memory testing pattern.
"""

from unittest.mock import ANY

import pytest

from graphql import build_schema

from stacklet.mcp.platform.graphql import PlatformClient, has_mutations
from stacklet.mcp.platform.models import ExportParam

from .testing.http import ExpectRequest
from .testing.mcp import MCPBearerTest, MCPTest, json_guard_parametrize


class TestGraphQLInfo(MCPTest):
    tool_name = "platform_graphql_info"

    async def test_returns_expected_documentation(self):
        """Test the platform_graphql_info tool returns expected documentation content."""
        result = (await self.assert_call({})).json()

        assert result["meta"] == {
            "importance": "critical",
            "memorability": "high",
            "priority": "top",
        }
        content = result["content"]

        # Verify the content contains expected Platform GraphQL documentation
        assert "Stacklet GraphQL API Overview" in content
        assert "GraphQL" in content


class TestDatasetInfo(MCPTest):
    tool_name = "platform_dataset_info"

    async def test_returns_expected_documentation(self):
        """Test the platform_dataset_info tool returns expected documentation content."""
        result = (await self.assert_call({})).json()

        assert result["meta"] == {
            "importance": "critical",
            "memorability": "high",
            "priority": "top",
        }
        content = result["content"]

        # Verify the content contains expected Platform dataset export documentation
        assert "Stacklet Platform Dataset Export Guide" in content
        assert "Filtering" in content
        assert "Export Management" in content


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

    @json_guard_parametrize([["Query"], ["Account", "AccountList"]])
    async def test_json_guard(self, mangle, value):
        """Test that type_names parameter works with JSON guard."""
        result = await self.assert_call({"type_names": mangle(value)})
        assert result.json() == {
            "asked_for": value,
            "found_sdl": {k: ANY for k in value},
            "not_found": [],
        }

    @json_guard_parametrize([[]])
    async def test_json_guard_empty_list_error(self, mangle, value):
        """Test that empty type_names parameter is rejected."""
        await self.assert_call({"type_names": mangle(value)}, error=True)
        # Should get a validation error for empty list


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


class PlatformDatasetTest(MCPBearerTest):
    DATASET_ID = "node-123"

    @staticmethod
    def dataset_result(dataset_id, started=False, succeeded=None):
        node = {
            "id": dataset_id,
            "started": None,
            "processed": None,
            "completed": None,
            "success": succeeded,
            "message": None,
            "downloadURL": None,
            "availableUntil": None,
        }
        if started:
            node |= {"started": "2024-12-06T03:15:07+00:00", "processed": 11}
        if succeeded is not None:
            assert started, "test should make sense"
            node |= {"completed": "2024-12-06T03:15:09+00:00", "processed": 23}
            if succeeded:
                node |= {
                    "message": "yay!",
                    "downloadURL": "https://example.com/x.csv",
                    "availableUntil": "2024-12-07T03:15:09+00:00",
                }
            else:
                node |= {"message": "meh."}
        return node

    @staticmethod
    def trivial_export_columns():
        return [
            {"name": "id", "path": "id"},
        ]

    @staticmethod
    def fancy_export_columns():
        return [
            {"name": "Arbitrary Text", "path": "a.b.c"},
            {"name": "🤯", "path": "huh", "subpath": "foo.bar"},
        ]

    @staticmethod
    def trivial_export_param():
        return {"name": "id", "type": "ID!", "value": "opaque-node-id"}

    @staticmethod
    def fancy_export_param():
        return {
            "name": "filterElement",
            "type": "FilterElementInput",
            "value": {
                "multiple": {
                    "operator": "or",
                    "operands": [
                        {"single": {"name": "foo", "operator": "equals", "value": "bob"}},
                        {"single": {"name": "bar"}},
                    ],
                }
            },
        }

    def assert_result(self, result, started=False, succeeded=None):
        """Assert that result matches expected dataset state from factory args."""
        expected = {
            "dataset_id": self.DATASET_ID,
            "started": None,
            "processed_rows": None,
            "completed": None,
            "success": succeeded,
            "message": None,
            "download_url": None,
            "available_until": None,
        }
        if started:
            expected["started"] = "2024-12-06T03:15:07Z"
            expected["processed_rows"] = 11
        if succeeded is not None:
            assert started, "test should make sense"
            expected["completed"] = "2024-12-06T03:15:09Z"
            expected["processed_rows"] = 23
            if succeeded:
                expected["message"] = "yay!"
                expected["download_url"] = "https://example.com/x.csv"
                expected["available_until"] = "2024-12-07T03:15:09Z"
            else:
                expected["message"] = "meh."

        assert result.json() == expected

    def expect_start_export(self, columns, connection="someConnection", node_id=None, params=None):
        """Create expectation for the export mutation request."""
        input_ = {
            "field": connection,
            "columns": columns,
            "format": "CSV",
        }
        if params:
            input_["params"] = params
        if node_id:
            input_["node"] = node_id

        return ExpectRequest(
            "https://api.example.com/",
            method="POST",
            data={
                "query": PlatformClient.Q_START_EXPORT,
                "variables": {"input": input_},
            },
            response={"data": {"exportConnection": {"export": {"id": self.DATASET_ID}}}},
        )

    def expect_get_export(self, export):
        """Create expectation for the export polling request."""
        return ExpectRequest(
            "https://api.example.com/",
            method="POST",
            data={
                "query": PlatformClient.Q_GET_EXPORT,
                "variables": {"id": export["id"]},
            },
            response={"data": {"node": export}},
        )


class TestPlatformDatasetExport(PlatformDatasetTest):
    tool_name = "platform_dataset_export"

    @json_guard_parametrize(
        [
            PlatformDatasetTest.trivial_export_columns(),
            PlatformDatasetTest.fancy_export_columns(),
        ]
    )
    async def test_columns(self, mangle, value):
        dataset = self.dataset_result(self.DATASET_ID)
        with self.http.expect(
            self.expect_start_export(value),
            self.expect_get_export(dataset),
        ):
            await self.assert_call({"connection_field": "someConnection", "columns": mangle(value)})

    @json_guard_parametrize(
        [
            PlatformDatasetTest.trivial_export_param(),
            PlatformDatasetTest.fancy_export_param(),
        ]
    )
    async def test_params(self, mangle, value):
        # params goes through an extra layer of deliberate mangling
        expect = [ExportParam(**value).for_graphql()]

        dataset = self.dataset_result(self.DATASET_ID)
        columns = self.trivial_export_columns()
        with self.http.expect(
            self.expect_start_export(columns, params=expect),
            self.expect_get_export(dataset),
        ):
            await self.assert_call(
                {
                    "connection_field": "someConnection",
                    "columns": columns,
                    "params": mangle([value]),
                }
            )

    async def test_node_id(self):
        dataset = self.dataset_result(self.DATASET_ID)
        columns = self.trivial_export_columns()
        with self.http.expect(
            self.expect_start_export(columns, node_id="some-value"),
            self.expect_get_export(dataset),
        ):
            await self.assert_call(
                {
                    "connection_field": "someConnection",
                    "columns": columns,
                    "node_id": "some-value",
                }
            )

    async def test_response_unstarted(self):
        columns = self.trivial_export_columns()
        dataset = self.dataset_result(self.DATASET_ID)

        with self.http.expect(
            self.expect_start_export(columns),
            self.expect_get_export(dataset),
        ):
            result = await self.assert_call(
                {
                    "connection_field": "someConnection",
                    "columns": columns,
                }
            )

        self.assert_result(result, started=False, succeeded=None)

    async def test_response_complete(self):
        dataset = self.dataset_result(self.DATASET_ID, started=True, succeeded=True)
        columns = self.trivial_export_columns()

        with self.http.expect(
            self.expect_start_export(columns),
            self.expect_get_export(dataset),
        ):
            result = await self.assert_call(
                {
                    "connection_field": "someConnection",
                    "columns": columns,
                }
            )

        self.assert_result(result, started=True, succeeded=True)

    @json_guard_parametrize([1, 2])
    async def test_timeout_minimal(self, mangle, value, async_sleeps):
        # We'll hit more cases in TestDatasetLookup
        columns = self.trivial_export_columns()
        dataset = self.dataset_result(self.DATASET_ID)

        with self.http.expect(
            self.expect_start_export(columns),
            self.expect_get_export(dataset),
            self.expect_get_export(dataset),
        ):
            result = await self.assert_call(
                {
                    "connection_field": "someConnection",
                    "columns": columns,
                    "timeout": mangle(value),
                }
            )

        assert async_sleeps == [value]
        self.assert_result(result, started=False, succeeded=None)


class TestPlatformDatasetLookup(PlatformDatasetTest):
    tool_name = "platform_dataset_lookup"

    @pytest.mark.parametrize("started", [True, False])
    async def test_incomplete(self, started):
        # Test looking up a dataset that hasn't started yet
        incomplete = self.dataset_result(self.DATASET_ID, started=started)

        with self.http.expect(self.expect_get_export(incomplete)):
            result = await self.assert_call({"dataset_id": self.DATASET_ID})

        self.assert_result(result, started=started)

    @pytest.mark.parametrize("started", [True, False])
    @json_guard_parametrize([1, 2])
    async def test_incomplete_timeout(self, started, mangle, value, async_sleeps):
        # Test looking up a non-started dataset with a timeout - should poll and timeout
        incomplete = self.dataset_result(self.DATASET_ID, started=started)

        with self.http.expect(
            self.expect_get_export(incomplete),
            self.expect_get_export(incomplete),
        ):
            result = await self.assert_call(
                {"dataset_id": self.DATASET_ID, "timeout": mangle(value)}
            )

        assert async_sleeps == [value]
        self.assert_result(result, started=started, succeeded=None)

    @json_guard_parametrize([60])
    async def test_incomplete_long_timeout(self, mangle, value, async_sleeps):
        # Test looking up a non-started dataset with long timeout - should use exponential backoff
        incomplete = self.dataset_result(self.DATASET_ID, started=False)
        complete = self.dataset_result(self.DATASET_ID, started=True)

        with self.http.expect(
            *[self.expect_get_export(incomplete)] * 2,
            *[self.expect_get_export(complete)] * 4,
        ):
            result = await self.assert_call(
                {"dataset_id": self.DATASET_ID, "timeout": mangle(value)}
            )

        assert async_sleeps == [2, 4, 8, 16, 30]
        self.assert_result(result, started=True, succeeded=None)

    @pytest.mark.parametrize("succeeded", [True, False])
    @json_guard_parametrize([60])
    async def test_complete_timeout_immediate(self, succeeded, mangle, value, async_sleeps):
        # Test successful dataset on first call - should return immediately
        complete = self.dataset_result(self.DATASET_ID, started=True, succeeded=succeeded)

        with self.http.expect(
            self.expect_get_export(complete),
        ):
            result = await self.assert_call(
                {"dataset_id": self.DATASET_ID, "timeout": mangle(value)}
            )

        assert async_sleeps == []
        self.assert_result(result, started=True, succeeded=succeeded)

    @pytest.mark.parametrize("succeeded", [True, False])
    @json_guard_parametrize([60])
    async def test_complete_timeout_delayed(self, succeeded, mangle, value, async_sleeps):
        # Test successful dataset on 3rd call - should sleep [2, 4] then succeed
        incomplete = self.dataset_result(self.DATASET_ID, started=False)
        complete = self.dataset_result(self.DATASET_ID, started=True, succeeded=succeeded)

        with self.http.expect(
            self.expect_get_export(incomplete),
            self.expect_get_export(incomplete),
            self.expect_get_export(complete),
        ):
            result = await self.assert_call(
                {"dataset_id": self.DATASET_ID, "timeout": mangle(value)}
            )

        assert async_sleeps == [2, 4]
        self.assert_result(result, started=True, succeeded=succeeded)


class TestHasMutations:
    @pytest.mark.parametrize(
        "query", ["query { foo bar }", "query Baz { foo bar }", "query { foo } query { bar }"]
    )
    def test_no_mutations(self, query: str):
        assert not has_mutations(query)

    @pytest.mark.parametrize(
        "query",
        [
            "mutation { foo(x: Number) { foo bar } }",
            "mutation Baz { foo(x: Number) { foo bar } }",
            "mutation { foo(x: Int) { bar } baz(y: Boolean) { bza } }",
            "mutation { foo(x: Int) { bar } } mutation { baz(y: Boolean) { bza } }",
            "query { foo } mutation { bar(x: Boolean) { baz } }",
        ],
    )
    def test_with_mutations(self, query: str):
        assert has_mutations(query)
