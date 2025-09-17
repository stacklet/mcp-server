"""
Stacklet Platform client for GraphQL API operations.
"""

import asyncio
import re
import time

from typing import Any, Self, cast

import httpx

from fastmcp import Context
from graphql import GraphQLSchema, build_client_schema, get_introspection_query, print_type

from ..lifespan import server_cached
from ..stacklet_auth import StackletCredentials
from .models import (
    ConnectionExport,
    ExportRequest,
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

    async def start_export(self, spec: ExportRequest) -> str:
        """
        Start a dataset export and poll for completion, then download the result.

        Args:
            spec: Validated export configuration with connection field, columns, and options

        Returns:
            Node ID of started export job.
        """

        result = await self.query(self.Q_START_EXPORT, {"input": spec.for_graphql()})
        if result.errors:
            raise RuntimeError(f"Export mutation failed: {result.errors}")

        # If no errors, data is at least guaranteed truthy.
        export = cast(dict[str, Any], result.data)["exportConnection"]["export"]
        return cast(dict[str, str], export)["id"]

    Q_START_EXPORT = """
        mutation exportConnection($input: ExportConnectionInput!) {
            exportConnection(input: $input) { export { id } }
        }
    """

    async def wait_for_export(self, export_id: str, timeout_s: int) -> ConnectionExport:
        cutoff = time.time() + timeout_s
        interval_s = 2
        while True:
            # Always try at least once.
            export = await self._get_export(export_id)
            if export.completed:
                return export

            # Aim for the final attempt to happen at cutoff time.
            remaining_s = cutoff - time.time()
            if remaining_s < 0:
                return export
            await asyncio.sleep(min(interval_s, remaining_s))
            interval_s *= 2

    async def _get_export(self, export_id: str) -> ConnectionExport:
        result = await self.query(self.Q_GET_EXPORT, {"id": export_id})
        if result.errors:
            raise RuntimeError(f"GraphQL errors: {result.errors}")

        # If no errors, data is at least guaranteed guaranteed truthy.
        fields = cast(dict[str, Any], result.data)["node"]
        return ConnectionExport(**fields)

    Q_GET_EXPORT = """
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
