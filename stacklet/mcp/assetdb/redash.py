# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
AssetDB client using Redash API with Stacklet authentication.
"""

import asyncio
import time

from typing import Any, Self, cast
from urllib.parse import urljoin

import httpx

from fastmcp import Context

from ..lifespan import server_singleton
from ..request_credentials import current_credentials
from ..settings import SETTINGS
from ..upstream_errors import check_response, sanitize_error_body
from ..utils.error import AnnotatedError
from ..utils.http import PerCallClient
from .models import ExportFormat, Job, Query, QueryListResponse, QueryResult, QueryUpsert


class AssetDBClient(PerCallClient):
    """Client for AssetDB interface via Redash API using Stacklet authentication.

    Auth is NOT held on the instance — each HTTP call reads per-request
    credentials via `current_credentials(ctx)` and passes the identity-token
    cookie per-call. The shared-transport/per-call-AsyncClient pattern lives
    on `PerCallClient`.
    """

    # Redash jobs poll on top of this.
    TIMEOUT_SECONDS = 60.0

    def __init__(self, data_source_id: int = 1) -> None:
        """
        Initialize the AssetDB client.

        Args:
            data_source_id: ID of the Redash data source (default 1 for main AssetDB)
        """
        super().__init__()
        self.data_source_id = data_source_id

    @classmethod
    def get(cls, ctx: Context) -> Self:
        def construct() -> AssetDBClient:
            return cls(SETTINGS.assetdb_datasource)

        return cast(Self, server_singleton(ctx, "ASSETDB_CLIENT", construct))

    async def _make_request(self, ctx: Context, method: str, endpoint: str, **kwargs: Any) -> Any:
        """
        Make a request to the Redash API with Stacklet authentication.

        Args:
            ctx: FastMCP request context (used to read per-request credentials).
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for httpx

        Returns:
            Decoded response JSON
        """
        response = await self._raw_request(ctx, method, endpoint, **kwargs)
        check_response(response)
        return response.json()

    async def _raw_request(
        self, ctx: Context, method: str, endpoint: str, **kwargs: Any
    ) -> httpx.Response:
        """Issue an authenticated Redash request and return the raw response.

        Use this (not `_make_request`) when a caller needs to inspect the
        status code before the generic error mapper runs — e.g. to surface
        a more specific message for an expected 4xx.
        """
        creds = current_credentials(ctx)
        url = urljoin(creds.service_endpoint("redash"), endpoint)
        async with self._async_client() as session:
            return await session.request(
                method,
                url,
                cookies={"stacklet-auth": creds.identity_token},
                **kwargs,
            )

    async def list_queries(
        self,
        ctx: Context,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> QueryListResponse:
        """
        Get list of queries with search and sorting support.

        Args:
            page: Page number (1-based)
            page_size: Number of queries per page
            search: Search query names, descriptions, and SQL content
            tags: Filter out queries not matching all tags

        Returns:
            Structured response with queries and pagination metadata
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}

        if search:
            params["q"] = search
        if tags:
            params["tags"] = tags

        response = await self._raw_request(ctx, "GET", "api/queries", params=params)
        if response.status_code == 400:
            raise AnnotatedError(
                problem="Backend rejected request",
                likely_cause="the page parameter was out of bounds",
                next_steps="check page 1, or try a simpler search",
                original_error=f"HTTP 400: {sanitize_error_body(response.text)}",
            )
        check_response(response)
        return QueryListResponse(**response.json())

    async def get_query(self, ctx: Context, query_id: int) -> Query:
        """
        Get detailed information about a specific saved query.

        Args:
            ctx: FastMCP request context.
            query_id: ID of the query to retrieve

        Returns:
            Complete query object with SQL and parameters
        """
        result = await self._make_request(ctx, "GET", f"api/queries/{query_id}")
        return Query(**result)

    async def execute_saved_query(
        self,
        ctx: Context,
        query_id: int,
        parameters: dict[str, Any] | None,
        max_age: int,
        timeout: int,
    ) -> QueryResult:
        """
        Execute a saved query by ID, with caching control.

        Args:
            ctx: FastMCP request context.
            query_id: ID of the query
            parameters: Optional parameters for the query
            max_age: Maximum age of cached results in seconds (-1=any cached result, 0=always fresh)
            timeout: Timeout in seconds for query execution (if not cached)

        Returns:
            Complete query result with data, columns, and metadata
        """
        payload = {"max_age": max_age, "parameters": parameters or {}}
        return await self._execute_results(ctx, f"api/queries/{query_id}/results", payload, timeout)

    async def execute_adhoc_query(
        self, ctx: Context, query: str, max_age: int, timeout: int
    ) -> QueryResult:
        """
        Execute an ad-hoc SQL query without saving it.

        Args:
            ctx: FastMCP request context.
            query: SQL query string to execute
            timeout: Timeout in seconds for query execution

        Returns:
            Complete query result with data, columns, and metadata
        """
        payload = {
            "query": query,
            "data_source_id": self.data_source_id,
            "max_age": max_age,
            "parameters": {},
            "apply_auto_limit": True,
        }
        return await self._execute_results(ctx, "api/query_results", payload, timeout)

    async def _execute_results(
        self, ctx: Context, endpoint: str, payload: dict[str, Any], timeout: int
    ) -> QueryResult:
        """
        Execute query request and handle both sync and async results.

        Args:
            ctx: FastMCP request context.
            endpoint: API endpoint to POST the query to
            payload: Query parameters and options
            timeout: Maximum time to wait for async job completion

        Returns:
            Complete query result with data, columns, and metadata
        """
        # This will contain either a "job" or a full "query_result". Since we're
        # sometimes stuck grabbing a whole result set any way, we may as well do
        # it every time; this also lets us always return a preview of the result
        # data even when it's large.
        response = await self._make_request(ctx, "POST", endpoint, json=payload)
        if "query_result" in response:
            return QueryResult(**response["query_result"])

        job = Job(**response["job"])
        result_id = await self._poll_job(ctx, job, timeout)
        qr_response = await self._make_request(ctx, "GET", f"api/query_results/{result_id}")
        return QueryResult(**qr_response["query_result"])

    async def _poll_job(self, ctx: Context, job: Job, timeout: int) -> int:
        """
        Poll an async job until completion using exponential backoff.

        Args:
            ctx: FastMCP request context.
            job: Initial job object from query execution
            timeout: Maximum time to wait before timing out

        Returns:
            Query result ID when job completes successfully

        Notes:
            `CancelledError` (e.g. from uvicorn's graceful-shutdown window
            elapsing during ECS task replacement) is deliberately NOT caught
            here. It inherits from `BaseException` specifically so callers
            don't swallow it; catching-and-re-raising would break
            cancellation contracts (including `asyncio.TaskGroup` in 3.11+).
            The MCP client sees a cleanly cancelled connection and retries.
        """
        cutoff = time.monotonic() + timeout
        interval_s = 2
        while True:
            job_result = await self._make_request(ctx, "GET", f"api/jobs/{job.id}")
            job = Job(**job_result["job"])
            if job.query_result_id:
                return job.query_result_id
            elif job.status.is_terminal:
                raise AnnotatedError(
                    problem=f"Query execution error: {job.error or '(unknown)'}",
                    likely_cause="the query SQL or parameters were invalid",
                    next_steps="investigate the errors, or try a simpler query and build up",
                )

            remaining_s = cutoff - time.monotonic()
            if remaining_s <= 0:
                raise AnnotatedError(
                    problem=f"Timed out after {timeout} seconds",
                    likely_cause="the query is still executing",
                    next_steps=("request cached results (with max_age=-1), or try a simpler query"),
                )
            await asyncio.sleep(min(interval_s, remaining_s))
            interval_s *= 2

    def get_query_result_urls(
        self, ctx: Context, query: Query, query_result: QueryResult
    ) -> dict[ExportFormat, str]:
        """
        Return download URLs for a query result.

        Args:
            ctx: FastMCP request context (used to derive the redash URL).
            query: Query the result refers to.
            query_result: Result to produce download URLs for.

        Returns:
            Dictionary mapping download formats to their URLs
        """
        redash_url = current_credentials(ctx).service_endpoint("redash")
        return {
            fmt: urljoin(
                redash_url,
                f"api/queries/{query.id}/results/{query_result.id}.{fmt}?api_key={query.api_key}",
            )
            for fmt in ExportFormat
        }

    async def create_query(self, ctx: Context, upsert: QueryUpsert) -> Query:
        """
        Create a new saved query.

        Args:
            ctx: FastMCP request context.
            upsert: QueryUpsert object with query data

        Returns:
            Complete query object with ID, timestamps, and metadata
        """
        payload = upsert.payload(data_source_id=self.data_source_id)
        result = await self._make_request(ctx, "POST", "api/queries", json=payload)
        return Query(**result)

    async def update_query(self, ctx: Context, query_id: int, upsert: QueryUpsert) -> Query:
        """
        Update an existing saved query.

        Args:
            ctx: FastMCP request context.
            query_id: ID of the query to update
            upsert: QueryUpsert object with query data to update

        Returns:
            Complete updated query object with ID, timestamps, and metadata
        """
        payload = upsert.payload()
        result = await self._make_request(ctx, "POST", f"api/queries/{query_id}", json=payload)
        return Query(**result)

    async def delete_query(self, ctx: Context, query_id: int) -> None:
        """
        Archive a saved query.

        This sets the query's is_archived flag to True and removes associated
        visualizations and alerts, but preserves the query in the database.

        Args:
            ctx: FastMCP request context.
            query_id: ID of the query to archive
        """
        await self._make_request(ctx, "DELETE", f"api/queries/{query_id}")
