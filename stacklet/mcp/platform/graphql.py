"""
Stacklet Platform client for GraphQL API operations.
"""

import asyncio
import re
import tempfile
import time

from pathlib import Path
from typing import Any, Self, cast

import httpx

from fastmcp import Context
from graphql import GraphQLSchema, build_client_schema, get_introspection_query, print_type

from ..lifespan import server_cached
from ..stacklet_auth import StackletCredentials
from .models import (
    ConnectionExportStatus,
    ExportConnectionInput,
    ExportResult,
    GetTypesResult,
    GraphQLError,
    GraphQLQueryResult,
    ListTypesResult,
)


class PlatformClient:
    """Client for Stacklet Platform GraphQL API."""

    @classmethod
    def get(cls, ctx: Context) -> Self:
        def construct() -> PlatformClient:
            return cls(StackletCredentials.get(ctx))

        return cast(Self, server_cached(ctx, "PLATFORM_CLIENT", construct))

    def __init__(self, credentials: StackletCredentials):
        """
        Initialize Platform client with Stacklet credentials.

        Args:
            credentials: StackletCredentials object containing endpoint and access_token
        """
        self.credentials = credentials
        self.session = httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {credentials.access_token}",
            },
            timeout=30.0,
        )
        self._schema_cache = None

    async def query(self, query: str, variables: dict[str, Any]) -> GraphQLQueryResult:
        """
        Execute a GraphQL query against the Stacklet Platform API.

        Args:
            query: The GraphQL query string
            variables: Optional variables for the query

        Returns:
            Structured GraphQL query result
        """
        request_data = {"query": query, "variables": variables}
        response = await self.session.post(self.credentials.endpoint, json=request_data)

        # Try to parse as a valid GraphQL response, because platform backend
        # sometimes sets 4xx/5xx error codes on valid graphql responses.
        try:
            raw_result = cast(dict[str, Any], response.json())
            errors = None
            if raw_errors := raw_result.get("errors"):
                errors = [GraphQLError(**error) for error in raw_errors]

            return GraphQLQueryResult(
                query=query,
                variables=variables,
                data=raw_result.get("data"),
                errors=errors,
            )
        except Exception:
            # Any failure (JSON parsing, validation, etc.) -> unexpected response
            raise Exception(f"Unexpected response: {response.text}")

    async def get_schema(self) -> GraphQLSchema:
        """
        Retrieve the GraphQL schema from the Stacklet Platform API.
        Uses instance-level caching to avoid repeated introspection queries.

        Returns:
            GraphQL schema object
        """
        if self._schema_cache is not None:
            return self._schema_cache

        # Use the standard GraphQL introspection query
        introspection_query = {"query": get_introspection_query()}

        response = await self.session.post(self.credentials.endpoint, json=introspection_query)
        response.raise_for_status()

        result = response.json()
        if errors := result.get("errors"):
            raise Exception(f"GraphQL introspection errors: {errors}")

        schema = result.get("data", {}).get("__schema")
        if not schema:
            raise Exception("GraphQL introspection returned no schema data")

        # Cache the schema for future requests
        self._schema_cache = build_client_schema({"__schema": schema})
        return self._schema_cache

    async def list_types(self, match: str | None = None) -> ListTypesResult:
        """
        List the types available in the GraphQL API.

        Args:
            match: Optional regular expression filter

        Returns:
            Structured result with context
        """
        schema = await self.get_schema()
        names = schema.type_map.keys()

        if match:
            f = re.compile(match)
            names = filter(f.search, names)

        return ListTypesResult(searched_for=match, found_types=sorted(names))

    async def get_types(self, type_names: list[str]) -> GetTypesResult:
        """
        Retrieve information about specific types in the GraphQL API.

        Args:
            type_names: Names of requested types

        Returns:
            Structured result with context
        """
        schema = await self.get_schema()
        found = {}
        missing = []

        for type_name in sorted(set(type_names)):
            if match := schema.type_map.get(type_name):
                found[type_name] = print_type(match)
            else:
                missing.append(type_name)

        return GetTypesResult(asked_for=type_names, found_sdl=found, not_found=missing)

    async def export_dataset(self, export_input: ExportConnectionInput) -> ExportResult:
        """
        Start a dataset export and poll for completion, then download the result.

        Args:
            export_input: Validated export configuration with connection field, columns, and options

        Returns:
            ExportResult with download information and file path
        """
        # Build the GraphQL input from the validated Pydantic model
        graphql_input = {
            "field": export_input.connection_field,
            "columns": [col.model_dump(by_alias=True) for col in export_input.columns],
            "format": export_input.format.value,
        }

        if export_input.node_id:
            graphql_input["node"] = export_input.node_id
        if export_input.params:
            graphql_input["params"] = [
                param.model_dump(by_alias=True) for param in export_input.params
            ]
        if export_input.filename:
            graphql_input["filename"] = export_input.filename

        # Start the export
        export_mutation = """
        mutation exportConnection($input: ExportConnectionInput!) {
          exportConnection(input: $input) {
            export {
              id
            }
          }
        }
        """

        result = await self.query(export_mutation, {"input": graphql_input})
        if result.errors:
            raise RuntimeError(f"Export mutation failed: {result.errors}")

        # Type assertion: if no errors, data is guaranteed to be present per GraphQL spec
        export_id = cast(dict[str, Any], result.data)["exportConnection"]["export"]["id"]

        # Poll for completion
        poll_query = """
        query getExport($id: ID!) {
          node(id: $id) {
            ... on ConnectionExport {
              started
              completed
              success
              processed
              downloadURL
              availableUntil
              message
            }
          }
        }
        """

        export_status = await self._poll_export_completion(
            poll_query, export_id, export_input.timeout
        )

        if not export_status.is_successful:
            error_msg = export_status.message or "Export failed with no error message"
            raise RuntimeError(f"Export failed: {error_msg}")

        # Download the file
        if not export_status.download_url:
            raise RuntimeError("Export completed but no download URL provided")
        file_path = await self._download_export_file(
            export_status.download_url, export_input.download_path, export_input.filename
        )

        return ExportResult(
            downloaded=True,
            file_path=file_path,
            format="csv",
            export_id=export_id,
            processed_rows=export_status.processed,
            available_until=export_status.available_until,
        )

    async def _poll_export_completion(
        self, poll_query: str, export_id: str, timeout: int, interval: float = 2.0
    ) -> ConnectionExportStatus:
        """
        Poll for export completion using GraphQL queries.

        Args:
            poll_query: GraphQL query to check export status
            export_id: ID of the export to poll
            timeout: Timeout in seconds
            interval: Polling interval in seconds

        Returns:
            ConnectionExportStatus when export is complete
        """
        end_time = time.time() + timeout

        while time.time() < end_time:
            result = await self.query(poll_query, {"id": export_id})
            if result.errors:
                raise RuntimeError(f"Export polling failed: {result.errors}")

            # Type assertion: if no errors, data is guaranteed to be present per GraphQL spec
            export_data = cast(dict[str, Any], result.data)["node"]

            # Check if completed
            if export_data.get("completed"):
                return ConnectionExportStatus(id=export_id, **export_data)

            await asyncio.sleep(interval)

        raise RuntimeError(f"Export timed out after {timeout} seconds")

    async def _download_export_file(
        self, download_url: str, download_path: str | None, filename: str | None
    ) -> str:
        """
        Download export file from URL.

        Args:
            download_url: URL to download the file from
            download_path: Optional path to save file
            filename: Optional filename hint

        Returns:
            Path to the downloaded file
        """
        if not download_path:
            # Generate a temp file name
            suffix = ".csv"
            if filename and "." in filename:
                suffix = "." + filename.split(".")[-1]
            download_path = f"{tempfile.gettempdir()}/platform_export_{int(time.time())}{suffix}"

        # Ensure directory exists
        Path(download_path).parent.mkdir(parents=True, exist_ok=True)

        # Stream download for potentially large files
        async with self.session.stream("GET", download_url) as response:
            response.raise_for_status()

            with open(download_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        return download_path
