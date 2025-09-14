"""
Tests for AssetDB MCP tools using FastMCP's in-memory testing pattern.
"""

import json

from copy import deepcopy
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


class TestSQLInfo(MCPTest):
    tool_name = "assetdb_sql_info"

    async def test_returns_expected_documentation(self):
        """Test the assetdb_sql_info tool returns expected documentation content."""
        result = await self.assert_call({})
        content = get_text(result)

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

    def r(self, *, data={}, status_code=200, response: Any = "") -> ExpectRequest:
        return ExpectRequest(
            "https://example.com/api/queries",
            data={"page": 1, "page_size": 25} | data,
            status_code=status_code,
            response=response,
        )

    async def test_queries(self):
        with self.http.expect(
            self.r(response=factory.redash_query_list([q123(), q456()], (1, 25, 2))),
        ):
            result = await self.assert_call({})

        assert get_json(result) == {
            "pagination": {
                "page": 1,
                "page_size": 25,
                "has_next_page": False,
                "total_count": 2,
            },
            "queries": [
                {
                    "id": 123,
                    "name": "Test Query 1",
                    "description": "The first one",
                    "has_parameters": True,
                    "data_source_id": 1,
                    "is_archived": False,
                    "is_draft": False,
                    "is_favorite": True,
                    "tags": ["production", "monitoring"],
                    "user": {
                        "email": "test@example.com",
                        "id": 1,
                        "name": "Test User",
                    },
                },
                {
                    "id": 456,
                    "name": "Test Query 2",
                    "description": "A sample query",
                    "has_parameters": False,
                    "data_source_id": 1,
                    "is_archived": False,
                    "is_draft": True,
                    "is_favorite": False,
                    "tags": [],
                    "user": {
                        "email": "test@example.com",
                        "id": 1,
                        "name": "Test User",
                    },
                },
            ],
        }

    @json_guard_param("page_param", 3)
    async def test_page(self, page_param):
        with self.http.expect(
            self.r(
                data={"page": 3, "page_size": 1},
                response=factory.redash_query_list([q123()], (3, 1, 7)),
            ),
        ):
            result = await self.assert_call({"page_size": 1, "page": page_param})

        data = get_json(result)
        assert data["queries"][0]["id"] == 123
        assert data["pagination"] == {
            "page": 3,
            "page_size": 1,
            "has_next_page": True,
            "total_count": 7,
        }

    async def test_page_missing(self):
        with self.http.expect(
            self.r(data={"page": 999}, status_code=400),
        ):
            result = await self.assert_call({"page": 999}, error=True)

        # XXX better errors might be nice, "page 999 out of range" is… likely?
        assert get_text(result) == "Error calling tool 'assetdb_query_list': http 400"

    @json_guard_param("page_size_param", 10)
    async def test_page_size(self, page_size_param):
        with self.http.expect(
            self.r(
                data={"page_size": 10},
                response=factory.redash_query_list([], (1, 10, 0)),
            ),
        ):
            result = await self.assert_call({"page_size": page_size_param})

        assert get_json(result) == self.empty_result_json(page_size=10)

    @json_guard_param("tags_param", ["production", "alerts"])
    async def test_tags(self, tags_param):
        with self.http.expect(
            self.r(
                data={"tags": ["production", "alerts"]},
                response=factory.redash_query_list([], (1, 25, 0)),
            ),
        ):
            result = await self.assert_call({"tags": tags_param})

        assert get_json(result) == self.empty_result_json()

    async def test_search(self):
        with self.http.expect(
            self.r(
                data={"q": "lol whatever"},
                response=factory.redash_query_list([], (1, 25, 0)),
            ),
        ):
            result = await self.assert_call({"search": "lol whatever"})

        assert get_json(result) == self.empty_result_json()

    def empty_result_json(self, page_size=25):
        return {
            "queries": [],
            "pagination": {
                "page": 1,
                "page_size": page_size,
                "has_next_page": False,
                "total_count": 0,
            },
        }


class TestQueryGet(MCPTest):
    tool_name = "assetdb_query_get"

    @json_guard_param("id_param", 123)
    async def test_success(self, id_param):
        """Test the assetdb_query_get tool with valid query ID."""
        with self.http.expect(
            ExpectRequest("https://example.com/api/queries/123", response=q123()),
        ):
            result = await self.assert_call({"query_id": id_param})

        # NOTE that this is a fair amount more data than seen in query_list.
        expect = q123()
        expect.pop("visualizations")
        assert get_json(result) == expect

    async def test_not_found(self):
        """Test the assetdb_query_get tool with non-existent query ID."""
        with self.http.expect(
            ExpectRequest("https://example.com/api/queries/999", status_code=404),
        ):
            result = await self.assert_call({"query_id": 999}, error=True)

        # XXX better errors might be nice, "query 999 does not exist"
        assert get_text(result) == "Error calling tool 'assetdb_query_get': http 404"


class TestQuerySave(MCPTest):
    tool_name = "assetdb_query_save"

    def r(self, data, *, update=None, status_code=200, response: Any = ""):
        return ExpectRequest(
            "https://example.com/api/queries" + (f"/{update}" if update else ""),
            method="POST",
            data=data,
            status_code=status_code,
            response=response,
        )

    async def test_create_result(self):
        response = factory.redash_query(
            id=789,
            name="New Test Query",
            description="",
            query="SELECT * FROM platform.account",
            is_draft=True,
        )
        expect = deepcopy(response)
        expect.pop("visualizations")

        with self.http.expect(
            self.r(
                {
                    "name": "New Test Query",
                    "query": "SELECT * FROM platform.account",
                    "data_source_id": 1,
                    "is_draft": True,
                },
                response=response,
            ),
        ):
            result = await self.assert_call(
                {"name": "New Test Query", "query": "SELECT * FROM platform.account"}
            )

        assert get_json(result) == expect

    @json_guard_param("null_value", None)
    async def test_create_nulls(self, null_value):
        with self.http.expect(
            self.r(
                {
                    "name": "New Test Query",
                    "query": "SELECT * FROM platform.account",
                    "data_source_id": 1,
                    "is_draft": True,
                }
                | (
                    # all the null_values are ignored EXCEPT description, which
                    # is a str | None already, and not json_guard-ed, so it's
                    # passed through unimpeded when it's a string.
                    {"description": null_value} if null_value is not None else {}
                ),
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call(
                {
                    "query_id": null_value,
                    "name": "New Test Query",
                    "query": "SELECT * FROM platform.account",
                    "description": null_value,
                    "tags": null_value,
                    "options": null_value,
                    "is_draft": null_value,
                }
            )

    @json_guard_param("query_id_param", 123)
    async def test_update_result(self, query_id_param):
        response = factory.redash_query(
            id=123,
            description="Updated description",
        )
        expect = deepcopy(response)
        expect.pop("visualizations")

        with self.http.expect(
            self.r(
                {"description": "Updated description"},
                update=123,
                response=response,
            ),
        ):
            result = await self.assert_call(
                {"query_id": query_id_param, "description": "Updated description"}
            )

        assert get_json(result) == expect

    @json_guard_param("tags_param", ["ping", "pong"])
    async def test_tags(self, tags_param):
        with self.http.expect(
            self.r(
                {"tags": ["ping", "pong"]},
                update=123,
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call({"query_id": 123, "tags": tags_param})

    @json_guard_param(
        "options_param", {"parameters": [{"name": "region", "type": "text", "value": "us-east-1"}]}
    )
    async def test_options(self, options_param):
        with self.http.expect(
            self.r(
                {
                    "options": {
                        "parameters": [{"name": "region", "type": "text", "value": "us-east-1"}]
                    },
                },
                update=123,
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call(
                {
                    "query_id": 123,
                    "options": options_param,
                }
            )

    @json_guard_param("is_draft_param", True)
    async def test_is_draft_update_true(self, is_draft_param):
        with self.http.expect(
            self.r(
                {"is_draft": True},
                update=123,
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call({"query_id": 123, "is_draft": is_draft_param})

    @json_guard_param("is_draft_param", False)
    async def test_is_draft_update_false(self, is_draft_param):
        with self.http.expect(
            self.r(
                {"is_draft": False},
                update=123,
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call({"query_id": 123, "is_draft": is_draft_param})

    @json_guard_param("is_draft_param", None)
    async def test_is_draft_update_null(self, is_draft_param):
        with self.http.expect(
            self.r(
                {"name": "x"},  # is_draft stripped
                update=123,
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call({"query_id": 123, "name": "x", "is_draft": is_draft_param})

    # Both truthy and noney values create as draft.
    @json_guard_param("is_draft_param", True, None)
    async def test_is_draft_create_true(self, is_draft_param):
        with self.http.expect(
            self.r(
                {"name": "q", "query": "select 1", "data_source_id": 1, "is_draft": True},
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call({"name": "q", "query": "select 1", "is_draft": is_draft_param})

    @json_guard_param("is_draft_param", False)
    async def test_is_draft_create_false(self, is_draft_param):
        with self.http.expect(
            self.r(
                {"name": "x", "query": "select 1", "data_source_id": 1, "is_draft": False},
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call({"name": "x", "query": "select 1", "is_draft": is_draft_param})


def get_text(result: CallToolResult) -> str:
    [content] = result.content
    return content.text  # type:ignore


def get_json(result: CallToolResult) -> Any:
    return json.loads(get_text(result))


def q123():
    return factory.redash_query(
        id=123,
        name="Test Query 1",
        description="The first one",
        tags=["production", "monitoring"],
        parameters=[{"name": "limit", "type": "number"}],
        is_favorite=True,
    )


def q456():
    return factory.redash_query(
        id=456,
        name="Test Query 2",
        is_draft=True,
    )
