# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
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

from ..lifespan import server_cached
from ..settings import SETTINGS
from ..stacklet_auth import StackletCredentials
from ..utils.error import annotated_error
from .models import ExportFormat, Job, Query, QueryListResponse, QueryResult, QueryUpsert


class AssetDBClient:
    """Client for AssetDB interface via Redash API using Stacklet authentication."""

    def __init__(self, credentials: StackletCredentials, data_source_id: int = 1) -> None:
        """
        Initialize AssetDB client with Stacklet credentials.

        Args:
            credentials: StackletCredentials object containing endpoint and id_token
            data_source_id: ID of the Redash data source (default 1 for main AssetDB)
        """
        self.credentials = credentials
        self.data_source_id = data_source_id

        self.redash_url = self.credentials.service_endpoint("redash")
        self.session = httpx.AsyncClient(
            cookies={"stacklet-auth": credentials.identity_token}, timeout=60.0
        )

    @classmethod
    def get(cls, ctx: Context) -> Self:
        def construct() -> AssetDBClient:
            return cls(StackletCredentials.get(ctx), SETTINGS.assetdb_datasource)

        return cast(Self, server_cached(ctx, "ASSETDB_CLIENT", construct))

    async def _make_request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """
        Make a request to the Redash API with Stacklet authentication.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for httpx

        Returns:
            Decoded response JSON
        """
        url = urljoin(self.redash_url, endpoint)
        response = await self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def list_queries(
        self,
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

        try:
            result = await self._make_request("GET", "api/queries", params=params)
            return QueryListResponse(**result)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 400:
                raise annotated_error(
                    problem="Backend rejected request",
                    likely_cause="the page parameter was out of bounds",
                    next_steps="check page 1, or try a simpler search",
                    original_error=str(err),
                )
            raise

    async def get_query(self, query_id: int) -> Query:
        """
        Get detailed information about a specific saved query.

        Args:
            query_id: ID of the query to retrieve

        Returns:
            Complete query object with SQL and parameters
        """
        result = await self._make_request("GET", f"api/queries/{query_id}")
        return Query(**result)

    async def execute_saved_query(
        self,
        query_id: int,
        parameters: dict[str, Any] | None,
        max_age: int,
        timeout: int,
    ) -> QueryResult:
        """
        Execute a saved query by ID, with caching control.

        Args:
            query_id: ID of the query
            parameters: Optional parameters for the query
            max_age: Maximum age of cached results in seconds (-1=any cached result, 0=always fresh)
            timeout: Timeout in seconds for query execution (if not cached)

        Returns:
            Complete query result with data, columns, and metadata
        """
        payload = {"max_age": max_age, "parameters": parameters or {}}
        return await self._execute_results(f"api/queries/{query_id}/results", payload, timeout)

    async def execute_adhoc_query(self, query: str, max_age: int, timeout: int) -> QueryResult:
        """
        Execute an ad-hoc SQL query without saving it.

        Args:
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
        return await self._execute_results("api/query_results", payload, timeout)

    async def _execute_results(
        self, endpoint: str, payload: dict[str, Any], timeout: int
    ) -> QueryResult:
        """
        Execute query request and handle both sync and async results.

        Args:
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
        response = await self._make_request("POST", endpoint, json=payload)
        if "query_result" in response:
            return QueryResult(**response["query_result"])

        job = Job(**response["job"])
        result_id = await self._poll_job(job, timeout)
        qr_response = await self._make_request("GET", f"api/query_results/{result_id}")
        return QueryResult(**qr_response["query_result"])

    async def _poll_job(self, job: Job, timeout: int) -> int:
        """
        Poll an async job until completion using exponential backoff.

        Args:
            job: Initial job object from query execution
            timeout: Maximum time to wait before timing out

        Returns:
            Query result ID when job completes successfully
        """
        cutoff = time.monotonic() + timeout
        interval_s = 2
        while True:
            job_result = await self._make_request("GET", f"api/jobs/{job.id}")
            job = Job(**job_result["job"])
            if job.query_result_id:
                return job.query_result_id
            elif job.status.is_terminal:
                raise annotated_error(
                    problem=f"Query execution error: {job.error or '(unknown)'}",
                    likely_cause="the query SQL or parameters were invalid",
                    next_steps="investigate the errors, or try a simpler query and build up",
                )

            remaining_s = cutoff - time.monotonic()
            if remaining_s <= 0:
                raise annotated_error(
                    problem=f"Timed out after {timeout} seconds",
                    likely_cause="the query is still executing",
                    next_steps="request cached results (with max_age=-1), or try a simpler query",
                )
            await asyncio.sleep(min(interval_s, remaining_s))
            interval_s *= 2

    def get_query_result_urls(
        self, query: Query, query_result: QueryResult
    ) -> dict[ExportFormat, str]:
        """
        Return download URLs for a query result.

        Args:
            query_id: ID of the query the result refers to
            result_id: ID of the query result to get downloads urls for
            api_key: the API key for the query.

        Returns:
            Dictionary mapping download formats to their URLs
        """
        return {
            fmt: urljoin(
                self.redash_url,
                f"api/queries/{query.id}/results/{query_result.id}.{fmt}?api_key={query.api_key}",
            )
            for fmt in ExportFormat
        }

    async def create_query(self, upsert: QueryUpsert) -> Query:
        """
        Create a new saved query.

        Args:
            upsert: QueryUpsert object with query data

        Returns:
            Complete query object with ID, timestamps, and metadata
        """
        payload = upsert.payload(data_source_id=self.data_source_id)
        result = await self._make_request("POST", "api/queries", json=payload)
        return Query(**result)

    async def update_query(self, query_id: int, upsert: QueryUpsert) -> Query:
        """
        Update an existing saved query.

        Args:
            query_id: ID of the query to update
            upsert: QueryUpsert object with query data to update

        Returns:
            Complete updated query object with ID, timestamps, and metadata
        """
        payload = upsert.payload()
        result = await self._make_request("POST", f"api/queries/{query_id}", json=payload)
        return Query(**result)

    async def delete_query(self, query_id: int) -> None:
        """
        Archive a saved query.

        This sets the query's is_archived flag to True and removes associated
        visualizations and alerts, but preserves the query in the database.

        Args:
            query_id: ID of the query to archive
        """
        await self._make_request("DELETE", f"api/queries/{query_id}")
