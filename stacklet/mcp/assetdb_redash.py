"""
AssetDB client using Redash API with Stacklet authentication.
"""

import asyncio
import tempfile
import time

from enum import IntEnum
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

import httpx

from .stacklet_auth import StackletCredentials


class JobStatus(IntEnum):
    QUEUED = 1
    STARTED = 2
    FINISHED = 3
    FAILED = 4
    CANCELED = 5
    DEFERRED = 6
    SCHEDULED = 7


class AssetDBClient:
    """Client for AssetDB interface via Redash API using Stacklet authentication."""

    def __init__(self, credentials: StackletCredentials):
        """
        Initialize AssetDB client with Stacklet credentials.

        Args:
            credentials: StackletCredentials object containing endpoint and id_token
        """
        self.credentials = credentials

        # Replace api. with redash. in the endpoint
        self.redash_url = credentials.endpoint.replace("api.", "redash.", 1)
        if not self.redash_url.endswith("/"):
            self.redash_url += "/"

        self.session = httpx.AsyncClient(
            cookies={"stacklet-auth": credentials.identity_token}, timeout=60.0
        )

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
    ) -> dict[str, Any]:
        """
        Get list of queries with search and sorting support.

        Args:
            page: Page number (1-based)
            page_size: Number of queries per page
            search: Search query names, descriptions, and SQL content
            tags: Filter out queries not matching all tags

        Returns:
            Full API response including queries and pagination metadata
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}

        if search:
            params["q"] = search
        if tags:
            params["tags"] = tags

        result = await self._make_request("GET", "api/queries", params=params)
        return cast(dict[str, Any], result)

    async def get_query(self, query_id: int) -> dict[str, Any]:
        """
        Get detailed information about a specific saved query.

        Args:
            query_id: ID of the query to retrieve

        Returns:
            Complete query object with SQL and parameters
        """
        result = await self._make_request("GET", f"api/queries/{query_id}")
        return cast(dict[str, Any], result)

    async def execute_saved_query(
        self,
        query_id: int,
        parameters: dict[str, Any] | None = None,
        max_age: int = -1,
        timeout: int = 60,
    ) -> int:
        """
        Execute a saved query by ID, with caching control.

        Args:
            query_id: ID of the query
            parameters: Optional parameters for the query
            max_age: Maximum age of cached results in seconds (-1=any cached result, 0=always fresh)
            timeout: Timeout in seconds for query execution (if not cached)

        Returns:
            Query result ID
        """
        payload: dict[str, Any] = {"max_age": max_age}
        if parameters:
            payload["parameters"] = parameters

        result = await self._make_request("POST", f"api/queries/{query_id}/results", json=payload)
        return await self._get_query_result_id(result, timeout)

    async def execute_adhoc_query(
        self, query: str, data_source_id: int = 1, timeout: int = 60
    ) -> int:
        """
        Execute an ad-hoc SQL query without saving it.

        Args:
            query: SQL query string to execute
            data_source_id: ID of the data source (default 1 for main AssetDB)
            timeout: Timeout in seconds for query execution

        Returns:
            Query result ID
        """
        payload = {
            "query": query,
            "data_source_id": data_source_id,
            "max_age": 0,  # Force fresh results
            "apply_auto_limit": True,
            "parameters": {},
        }

        result = await self._make_request("POST", "api/query_results", json=payload)
        return await self._get_query_result_id(result, timeout)

    async def _get_query_result_id(self, result: dict[str, Any], timeout: int = 60) -> int:
        """
        Extract query result ID from execution response, handling both sync and async results.

        Args:
            result: API response from query execution
            timeout: Timeout in seconds for async job polling

        Returns:
            Query result ID
        """
        # If query is async, poll for results
        if "job" in result:
            result = await self._poll_job_results(result["job"]["id"], timeout)
        return int(result["query_result"]["id"])

    async def _poll_job_results(
        self, job_id: str, timeout: int = 60, interval: float = 1.0
    ) -> dict[str, Any]:
        """
        Poll for async query results.

        Args:
            job_id: Job ID to poll
            timeout: Timeout in seconds
            interval: Polling interval in seconds

        Returns:
            Query results when complete
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            job_result = await self._make_request("GET", f"api/jobs/{job_id}")
            job_status = job_result.get("job", {}).get("status")

            match job_status:
                case (
                    JobStatus.QUEUED | JobStatus.STARTED | JobStatus.DEFERRED | JobStatus.SCHEDULED
                ):
                    await asyncio.sleep(interval)
                    continue
                case JobStatus.FINISHED:
                    job_data = job_result.get("job", {})
                    if "query_result_id" in job_data:
                        return await self.get_query_result_data(job_data["query_result_id"])
                    else:
                        # Return result directly
                        return cast(dict[str, Any], job_data.get("result", {}))

                case JobStatus.FAILED:
                    error = job_result.get("job", {}).get("error", "Unknown error")
                    raise RuntimeError(f"Query execution failed: {error}")
                case JobStatus.CANCELED:
                    raise RuntimeError("Query execution cancelled")

            raise RuntimeError(f"Unhandled query execution status: {job_status}")
        raise RuntimeError(f"Query execution timed out after {timeout} seconds")

    async def get_query_result_data(self, result_id: int) -> dict[str, Any]:
        """
        Get query result data by result ID.

        Args:
            result_id: ID of the query result to retrieve

        Returns:
            Query result data with columns and rows
        """
        result = await self._make_request("GET", f"api/query_results/{result_id}")
        return cast(dict[str, Any], result)

    async def download_query_result(
        self, result_id: int, format: str = "csv", download_path: str | None = None
    ) -> str:
        """
        Download query result to file and return file path.

        Args:
            result_id: ID of the query result to download
            format: Download format - "csv", "json", "tsv", or "xlsx"
            download_path: Optional path to save file. If None, uses temp dir.

        Returns:
            Path to the downloaded file
        """
        if format not in ("csv", "json", "tsv", "xlsx"):
            raise ValueError(f"Unsupported format: {format}. Must be csv, json, tsv, or xlsx")

        # Use path-based filetype as Redash expects: /api/query_results/{id}.{format}
        url = urljoin(self.redash_url, f"api/query_results/{result_id}.{format}")

        if not download_path:
            download_path = f"{tempfile.gettempdir()}/assetdb_{result_id}.{format}"

        # Ensure directory exists
        Path(download_path).parent.mkdir(parents=True, exist_ok=True)

        # Stream download for large files
        async with self.session.stream("GET", url) as response:
            response.raise_for_status()

            with open(download_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        return download_path

    async def get_data_sources(self) -> list[dict[str, Any]]:
        """
        Get available data sources.

        Returns:
            List of data source objects with id, name, type, etc.
        """
        result = await self._make_request("GET", "api/data_sources")
        return cast(list[dict[str, Any]], result)

    async def get_schema(self, data_source_id: int = 1) -> dict[str, Any]:
        """
        Get database schema for a data source.

        Args:
            data_source_id: ID of the data source (default 1 for main AssetDB)

        Returns:
            Schema information with tables and columns
        """
        result = await self._make_request("GET", f"api/data_sources/{data_source_id}/schema")
        return cast(dict[str, Any], result)
