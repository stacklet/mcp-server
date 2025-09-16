"""
Tests for AssetDB MCP tools using FastMCP's in-memory testing pattern.
"""

from copy import deepcopy
from typing import Any

import pytest

from stacklet.mcp.assetdb.tools import assetdb_query_save, tools
from stacklet.mcp.settings import Settings

from . import factory
from .testing.http import ExpectRequest
from .testing.mcp import MCPTest, json_guard_parametrize


pytestmark = pytest.mark.usefixtures("mock_stacklet_credentials")


@pytest.mark.parametrize("save", [True, False])
def test_tools_save(save: bool):
    settings = Settings(assetdb_save=save)
    assert (assetdb_query_save in tools(settings)) == save


class TestSQLInfo(MCPTest):
    tool_name = "assetdb_sql_info"

    async def test_returns_expected_documentation(self):
        """Test the assetdb_sql_info tool returns expected documentation content."""
        result = await self.assert_call({})

        # Verify the content contains expected AssetDB documentation
        assert "Stacklet AssetDB SQL Overview" in result.text
        assert "PostgreSQL 16" in result.text
        assert "resources" in result.text
        assert "resource_revisions" in result.text
        assert "account_cost" in result.text

        # Verify it contains guidance about querying
        assert "LIMIT" in result.text
        assert "indexes" in result.text
        assert "EXPLAIN" in result.text


class TestQueryList(MCPTest):
    tool_name = "assetdb_query_list"

    def r(self, *, data={}, status_code=200, response: Any = "") -> ExpectRequest:
        return ExpectRequest(
            "https://redash.example.com/api/queries",
            data={"page": 1, "page_size": 25} | data,
            status_code=status_code,
            response=response,
        )

    async def test_queries(self):
        with self.http.expect(
            self.r(response=factory.redash_query_list([q123(), q456()], (1, 25, 2))),
        ):
            result = await self.assert_call({})

        assert result.json() == {
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
                    "description": None,
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

    @json_guard_parametrize([3, 5])
    async def test_page(self, mangle, value):
        with self.http.expect(
            self.r(
                data={"page": value, "page_size": 1},
                response=factory.redash_query_list([q123()], (value, 1, 7)),
            ),
        ):
            result = await self.assert_call({"page_size": 1, "page": mangle(value)})

        data = result.json()
        assert data["queries"][0]["id"] == 123
        assert data["pagination"] == {
            "page": value,
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
        assert result.text == "Error calling tool 'assetdb_query_list': mocked http 400"

    @json_guard_parametrize([5, 10])
    async def test_page_size(self, mangle, value):
        with self.http.expect(
            self.r(
                data={"page_size": value},
                response=factory.redash_query_list([], (1, value, 0)),
            ),
        ):
            result = await self.assert_call({"page_size": mangle(value)})

        assert result.json() == self.empty_result_json(page_size=value)

    @json_guard_parametrize([[], ["production", "alerts"]])
    async def test_tags(self, mangle, value):
        with self.http.expect(
            self.r(
                data={"tags": value} if value else {},  # http query arg list
                response=factory.redash_query_list([], (1, 25, 0)),
            ),
        ):
            result = await self.assert_call({"tags": mangle(value)})

        assert result.json() == self.empty_result_json()

    async def test_search(self):
        with self.http.expect(
            self.r(
                data={"q": "lol whatever"},
                response=factory.redash_query_list([], (1, 25, 0)),
            ),
        ):
            result = await self.assert_call({"search": "lol whatever"})

        assert result.json() == self.empty_result_json()

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

    @json_guard_parametrize([123])
    async def test_success(self, mangle, value):
        """Test the assetdb_query_get tool with valid query ID."""
        with self.http.expect(
            ExpectRequest("https://redash.example.com/api/queries/123", response=q123()),
        ):
            result = await self.assert_call({"query_id": mangle(value)})

        # NOTE that this is a fair amount more fields than seen in query_list.
        expect = q123()
        expect.pop("visualizations")
        assert result.json() == expect

    async def test_not_found(self):
        """Test the assetdb_query_get tool with non-existent query ID."""
        with self.http.expect(
            ExpectRequest("https://redash.example.com/api/queries/999", status_code=404),
        ):
            result = await self.assert_call({"query_id": 999}, error=True)

        # XXX better errors might be nice, "query 999 does not exist"
        assert result.text == "Error calling tool 'assetdb_query_get': mocked http 404"


class TestQuerySave(MCPTest):
    tool_name = "assetdb_query_save"

    def r(self, data, *, update=None, status_code=200, response: Any = ""):
        return ExpectRequest(
            "https://redash.example.com/api/queries" + (f"/{update}" if update else ""),
            method="POST",
            data=data,
            status_code=status_code,
            response=response,
        )

    async def test_create_result(self):
        response = factory.redash_query(
            id=789,
            name="Untitled LLM Query",
            query="",
            description=None,
            is_draft=True,
        )
        expect = deepcopy(response)
        expect.pop("visualizations")

        with self.http.expect(
            self.r(
                {
                    "name": "Untitled LLM Query",
                    "query": "",
                    "data_source_id": 1,
                },
                response=response,
            ),
        ):
            result = await self.assert_call({})

        assert result.json() == expect

    @pytest.mark.parametrize("null_value", [None, "null", ""])
    async def test_create_nulls(self, null_value):
        params = {
            "query_id": null_value,  # this should force "create"
            "name": "New Test Query",
            "query": "SELECT * FROM platform.account",
            "description": null_value,
            "tags": null_value,
            "options": null_value,
            "is_draft": null_value,
        }

        with self.http.expect(
            self.r(
                {
                    "name": "New Test Query",
                    "query": "SELECT * FROM platform.account",
                    "data_source_id": 1,
                }
                | (
                    # all the null_values are ignored EXCEPT description, which
                    # is a str | None already, and not json_guard-ed, so it's
                    # passed through unimpeded when it's a string; but when it's
                    # None, it's stripped like all the other fields.
                    {"description": null_value} if null_value is not None else {}
                ),
                response=factory.redash_query(),
            ),
        ):
            await self.assert_call(params)

    @json_guard_parametrize([123])
    async def test_update_result(self, mangle, value):
        response = factory.redash_query(
            id=value,
            description="Updated description",
        )
        expect = deepcopy(response)
        expect.pop("visualizations")

        with self.http.expect(
            self.r({"description": "Updated description"}, update=value, response=response),
        ):
            result = await self.assert_call(
                {"query_id": mangle(value), "description": "Updated description"}
            )

        assert result.json() == expect

    @json_guard_parametrize([[], ["ping", "pong"]])
    async def test_tags(self, mangle, value):
        with self.http.expect(
            self.r({"tags": value}, update=123, response=factory.redash_query()),
        ):
            await self.assert_call({"query_id": 123, "tags": mangle(value)})

    @json_guard_parametrize(
        [
            {},
            {"what": "ever"},
            {"parameters": [{"name": "region", "type": "text", "value": "us-east-1"}]},
        ]
    )
    async def test_options(self, mangle, value):
        with self.http.expect(
            self.r({"options": value}, update=123, response=factory.redash_query()),
        ):
            await self.assert_call({"query_id": 123, "options": mangle(value)})

    @json_guard_parametrize([True, False])
    async def test_is_draft(self, mangle, value):
        with self.http.expect(
            self.r({"is_draft": value}, update=123, response=factory.redash_query()),
        ):
            await self.assert_call({"query_id": 123, "is_draft": mangle(value)})


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
