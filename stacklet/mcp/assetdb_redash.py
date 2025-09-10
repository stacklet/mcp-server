"""
AssetDB client using Redash API with Stacklet authentication.
"""

import asyncio
import time

from typing import Any
from urllib.parse import urljoin

import httpx

from .stacklet_auth import StackletCredentials


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
        self.redash_url = credentials.endpoint.replace("api.", "redash.")
        if not self.redash_url.endswith("/"):
            self.redash_url += "/"

        self.session = httpx.AsyncClient(
            cookies={"stacklet-auth": credentials.identity_token}, timeout=60.0
        )

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
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

    async def list_queries(self, page: int = 1, page_size: int = 25) -> list[dict[str, Any]]:
        """
        Get list of queries.

        Args:
            page: Page number (1-based)
            page_size: Number of queries per page

        Returns:
            List of query objects
        """
        params = {"page": page, "page_size": page_size}
        result = await self._make_request("GET", "api/queries", params=params)
        return result.get("results", [])

    async def execute_adhoc_query(
        self, query: str, data_source_id: int = 1, timeout: int = 60
    ) -> dict[str, Any]:
        """
        Execute an ad-hoc SQL query without saving it.

        Args:
            query: SQL query string to execute
            data_source_id: ID of the data source (default 1 for main AssetDB)
            timeout: Timeout in seconds for query execution

        Returns:
            Query results with data, columns, and metadata
        """
        payload = {
            "query": query,
            "data_source_id": data_source_id,
            "max_age": 0,  # Force fresh results
            "apply_auto_limit": True,
            "parameters": {},
        }

        result = await self._make_request("POST", "api/query_results", json=payload)

        # If query is async, poll for results
        if "job" in result:
            return await self._poll_job_results(result["job"]["id"], timeout)

        return result

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

        Raises:
            TimeoutError: If query doesn't complete within timeout
            RuntimeError: If query execution fails
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            job_result = await self._make_request("GET", f"api/jobs/{job_id}")
            job_status = job_result.get("job", {}).get("status")

            if job_status == 3:  # Completed
                job_data = job_result.get("job", {})
                if "query_result_id" in job_data:
                    # Get the actual results
                    return await self._make_request(
                        "GET", f"api/query_results/{job_data['query_result_id']}"
                    )
                else:
                    # Return result directly
                    return job_data.get("result", {})

            elif job_status == 4:  # Error
                error_msg = job_result.get("job", {}).get("error", "Unknown error")
                raise RuntimeError(f"Query execution failed: {error_msg}")

            # Wait before next poll
            await asyncio.sleep(interval)

        raise TimeoutError(f"Query execution timed out after {timeout} seconds")

    async def get_data_sources(self) -> list[dict[str, Any]]:
        """
        Get available data sources.

        Returns:
            List of data source objects with id, name, type, etc.
        """
        return await self._make_request("GET", "api/data_sources")

    async def get_schema(self, data_source_id: int = 1) -> dict[str, Any]:
        """
        Get database schema for a data source.

        Args:
            data_source_id: ID of the data source (default 1 for main AssetDB)

        Returns:
            Schema information with tables and columns
        """
        return await self._make_request("GET", f"api/data_sources/{data_source_id}/schema")
