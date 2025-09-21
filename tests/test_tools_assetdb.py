"""
Tests for AssetDB MCP tools using FastMCP's in-memory testing pattern.
"""

import json

from copy import deepcopy
from typing import Any

import pytest

from stacklet.mcp.assetdb.models import JobStatus, Query
from stacklet.mcp.assetdb.tools import assetdb_query_archive, assetdb_query_save, tools

from . import factory
from .testing.http import ExpectRequest
from .testing.mcp import MCPCookieTest, MCPTest, json_guard_parametrize


pytestmark = pytest.mark.usefixtures("mock_stacklet_credentials")


@pytest.mark.parametrize("allow_save", [True, False])
def test_tools_save(override_setting, allow_save: bool):
    override_setting("assetdb_allow_save", allow_save)
    assert (assetdb_query_save in tools()) == allow_save


@pytest.mark.parametrize("allow_archive", [True, False])
def test_tools_archive(override_setting, allow_archive: bool):
    override_setting("assetdb_allow_archive", allow_archive)
    assert (assetdb_query_archive in tools()) == allow_archive


class TestSQLInfo(MCPTest):
    tool_name = "assetdb_sql_info"

    async def test_returns_expected_documentation(self):
        """Test the assetdb_sql_info tool returns expected documentation content."""
        result = (await self.assert_call({})).json()

        assert result["meta"] == {
            "importance": "critical",
            "memorability": "high",
            "priority": "top",
        }
        content = result["content"]

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


class TestQueryList(MCPCookieTest):
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


class TestQueryGet(MCPCookieTest):
    tool_name = "assetdb_query_get"

    @json_guard_parametrize([123])
    async def test_success(self, mangle, value):
        """Test the assetdb_query_get tool with valid query ID."""
        with self.http.expect(
            ExpectRequest("https://redash.example.com/api/queries/123", response=q123()),
        ):
            result = await self.assert_call({"query_id": mangle(value)})

        # NOTE that this is a fair amount more fields than seen in query_list.
        # The Query model filters and transforms the raw response
        expect = Query(**q123()).model_dump(mode="json")
        assert result.json() == expect

    async def test_not_found(self):
        """Test the assetdb_query_get tool with non-existent query ID."""
        with self.http.expect(
            ExpectRequest("https://redash.example.com/api/queries/999", status_code=404),
        ):
            result = await self.assert_call({"query_id": 999}, error=True)

        # XXX better errors might be nice, "query 999 does not exist"
        assert result.text == "Error calling tool 'assetdb_query_get': mocked http 404"


class TestQuerySave(MCPCookieTest):
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
        raw_data = deepcopy(response)

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

        # Transform raw response to match Query model output
        expect = Query(**raw_data).model_dump(mode="json")
        assert result.json() == expect

    async def test_other_data_source_id(self, override_setting):
        override_setting("assetdb_datasource", 123)

        response = factory.redash_query(
            id=789,
            name="Untitled LLM Query",
            query="",
            description=None,
            is_draft=True,
        )
        raw_data = deepcopy(response)

        with self.http.expect(
            self.r(
                {
                    "name": "Untitled LLM Query",
                    "query": "",
                    "data_source_id": 123,
                },
                response=response,
            ),
        ):
            result = await self.assert_call({})

        # Transform raw response to match Query model output
        expect = Query(**raw_data).model_dump(mode="json")
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
        raw_data = deepcopy(response)

        with self.http.expect(
            self.r({"description": "Updated description"}, update=value, response=response),
        ):
            result = await self.assert_call(
                {"query_id": mangle(value), "description": "Updated description"}
            )

        # Transform raw response to match Query model output
        expect = Query(**raw_data).model_dump(mode="json")
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


class TestQueryArchive(MCPCookieTest):
    tool_name = "assetdb_query_archive"

    @json_guard_parametrize([123])
    async def test_archive_success(self, mangle, value):
        with self.http.expect(
            ExpectRequest(
                f"https://redash.example.com/api/queries/{value}",
                method="DELETE",
                status_code=200,
                response={},  # Redash returns empty response on successful archive
            ),
        ):
            result = await self.assert_call({"query_id": mangle(value)})

        assert result.json() == {
            "success": True,
            "message": f"Query {value} has been successfully archived",
            "query_id": value,
        }


class QueryResultTest(MCPCookieTest):
    QUERY_ID = None
    JOB_ID = "job-456"
    RESULT_ID = 789

    def expect_post(self, data, response):
        url = (
            f"https://redash.example.com/api/queries/{self.QUERY_ID}/results"
            if self.QUERY_ID
            else "https://redash.example.com/api/query_results"
        )
        return ExpectRequest(url, method="POST", data=data, response=response)

    def expect_get_job(self, response):
        return ExpectRequest(
            f"https://redash.example.com/api/jobs/{self.JOB_ID}",
            response=response,
        )

    def expect_get_result(self, response):
        return ExpectRequest(
            f"https://redash.example.com/api/query_results/{self.RESULT_ID}",
            response=response,
        )

    def expect_get_query(self, response):
        assert self.QUERY_ID
        return ExpectRequest(
            f"https://redash.example.com/api/queries/{self.QUERY_ID}",
            response=response,
        )

    def job_response(self, status):
        error = "Oh no borken" if status == JobStatus.FAILED else ""
        result_id = self.RESULT_ID if status == JobStatus.FINISHED else None
        return factory.redash_job_response(
            self.JOB_ID, status, error=error, query_result_id=result_id
        )

    def result_response(self):
        return factory.redash_query_result_response(self.RESULT_ID)

    async def assert_tool_call(self, params, *expect_http, expect_error=None):
        with self.http.expect(*expect_http):
            result = await self.assert_call(params, error=bool(expect_error))

        if expect_error:
            assert result.text == f"Error calling tool '{self.tool_name}': " + expect_error
        else:
            self.assert_tool_query_result(result)

    def assert_tool_query_result(self, result):
        actual = result.json()
        assert actual["result_id"] == self.RESULT_ID
        assert actual["query_id"] == self.QUERY_ID

        with open(actual["full_results_saved_to"]) as f:
            original = json.load(f)

        assert actual["query_text"] == original["query"]
        assert actual["query_runtime"] == original["runtime"]
        assert actual["columns"] == original["data"]["columns"]
        assert actual["some_rows"] == original["data"]["rows"][:20]
        assert actual["row_count"] == len(original["data"]["rows"])

        links = actual["alternate_formats"]
        if not self.QUERY_ID:
            assert links is None
        else:
            prefix = (
                f"https://redash.example.com/api/queries/{self.QUERY_ID}/results/{self.RESULT_ID}"
            )
            assert actual["alternate_formats"] == [
                {"format": "csv", "download_from": f"{prefix}.csv?api_key=test-api-key"},
                {"format": "json", "download_from": f"{prefix}.json?api_key=test-api-key"},
                {"format": "tsv", "download_from": f"{prefix}.tsv?api_key=test-api-key"},
                {"format": "xlsx", "download_from": f"{prefix}.xlsx?api_key=test-api-key"},
            ]


class TestQueryResult(QueryResultTest):
    tool_name = "assetdb_query_result"
    QUERY_ID = 123

    def post_data(self, **override):
        return {
            "max_age": -1,
            "parameters": {},
        } | override

    @json_guard_parametrize([QUERY_ID])
    async def test_query_id(self, mangle, value):
        await self.assert_tool_call(
            {"query_id": mangle(value)},
            self.expect_post(self.post_data(), self.result_response()),
            self.expect_get_query(q123()),
        )

    @json_guard_parametrize([-1, 0, 3600, 3600 * 24 * 365])
    async def test_max_age(self, mangle, value):
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID, "max_age": mangle(value)},
            self.expect_post(self.post_data(max_age=value), self.result_response()),
            self.expect_get_query(q123()),
        )

    @json_guard_parametrize([None, {}, {"arbitrary": {"nested": "values"}}])
    async def test_parameters(self, mangle, value):
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID, "parameters": mangle(value)},
            self.expect_post(self.post_data(parameters=value or {}), self.result_response()),
            self.expect_get_query(q123()),
        )

    # The tests from here down are _very similar_ but not quite all
    # identical to those in TestSQLQuery.

    @json_guard_parametrize([30, 120])
    async def test_instant_result(self, mangle, value):
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID, "timeout": mangle(value)},
            self.expect_post(self.post_data(), self.result_response()),
            self.expect_get_query(q123()),
        )

    async def test_job_immediate_success(self, async_sleeps):
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.FINISHED)),
            self.expect_get_result(self.result_response()),
            self.expect_get_query(q123()),
        )
        assert async_sleeps == []

    async def test_job_multi_status_transition(self, async_sleeps):
        """Test async job progressing through QUEUED → STARTED → FINISHED."""
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.FINISHED)),
            self.expect_get_result(self.result_response()),
            self.expect_get_query(q123()),
        )
        assert async_sleeps == [2, 4]

    @json_guard_parametrize([60])
    async def test_job_timeout(self, mangle, value, async_sleeps):
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID, "timeout": mangle(value)},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            expect_error="Query execution timed out after 60 seconds",
        )
        assert async_sleeps == [2, 4, 8, 16, 30]

    async def test_job_failure(self):
        """Test async job that fails (QUEUED → FAILED)."""
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.FAILED)),
            expect_error="Query execution failed: Oh no borken",
        )

    async def test_job_cancellation(self):
        """Test async job that gets canceled (QUEUED → CANCELED)."""
        # This _should_ in fact never happen but it serves to test the terminal-
        # state-with-no-error-message behaviour.
        await self.assert_tool_call(
            {"query_id": self.QUERY_ID},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.CANCELED)),
            expect_error="Query execution failed: Unknown error.",
        )


class TestSQLQuery(QueryResultTest):
    tool_name = "assetdb_sql_query"

    def post_data(self, **override):
        return {
            "query": "SELECT 1",
            "data_source_id": 1,
            "max_age": 3600,
            "parameters": {},
            "apply_auto_limit": True,
        } | override

    async def test_query(self):
        await self.assert_tool_call(
            {"query": "SELECT 'whatever'"},
            self.expect_post(self.post_data(query="SELECT 'whatever'"), self.result_response()),
        )

    @json_guard_parametrize([-1, 0, 3600, 3600 * 24 * 365])
    async def test_max_age(self, mangle, value):
        await self.assert_tool_call(
            {"query": "SELECT 1", "max_age": mangle(value)},
            self.expect_post(self.post_data(max_age=value), self.result_response()),
        )

    # The tests from here down are _very similar_ but not quite all
    # identical to those in TestQueryResult.

    @json_guard_parametrize([30, 120])
    async def test_instant_result(self, mangle, value):
        await self.assert_tool_call(
            {"query": "SELECT 1", "timeout": mangle(value)},
            self.expect_post(self.post_data(), self.result_response()),
        )

    async def test_job_immediate_success(self, async_sleeps):
        await self.assert_tool_call(
            {"query": "SELECT 1"},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.FINISHED)),
            self.expect_get_result(self.result_response()),
        )
        assert async_sleeps == []

    async def test_job_multi_status_transition(self, async_sleeps):
        """Test async job progressing through QUEUED → STARTED → FINISHED."""
        await self.assert_tool_call(
            {"query": "SELECT 1"},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.FINISHED)),
            self.expect_get_result(self.result_response()),
        )
        assert async_sleeps == [2, 4]

    @json_guard_parametrize([60])
    async def test_job_timeout(self, mangle, value, async_sleeps):
        await self.assert_tool_call(
            {"query": "SELECT 1", "timeout": mangle(value)},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            self.expect_get_job(self.job_response(JobStatus.STARTED)),
            expect_error="Query execution timed out after 60 seconds",
        )
        assert async_sleeps == [2, 4, 8, 16, 30]

    async def test_job_failure(self):
        """Test async job that fails (QUEUED → FAILED)."""
        await self.assert_tool_call(
            {"query": "SELECT 1"},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.FAILED)),
            expect_error="Query execution failed: Oh no borken",
        )

    async def test_job_cancellation(self):
        """Test async job that gets canceled (QUEUED → CANCELED)."""
        # This _should_ in fact never happen but it serves to test the terminal-
        # state-with-no-error-message behaviour.
        await self.assert_tool_call(
            {"query": "SELECT 1"},
            self.expect_post(self.post_data(), self.job_response(JobStatus.QUEUED)),
            self.expect_get_job(self.job_response(JobStatus.CANCELED)),
            expect_error="Query execution failed: Unknown error.",
        )


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
