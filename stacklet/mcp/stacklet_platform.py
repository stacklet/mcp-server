"""
Stacklet Platform client for GraphQL API operations.
"""

import re

from typing import Any, Self, cast

import httpx

from fastmcp import Context
from graphql import GraphQLSchema, build_client_schema, get_introspection_query, print_type

from .stacklet_auth import StackletCredentials


class PlatformClient:
    """Client for Stacklet Platform GraphQL API."""

    @classmethod
    def get(cls, ctx: Context) -> Self:
        key = "PLATFORM_CLIENT"
        if not ctx.get_state(key):
            creds = StackletCredentials.get(ctx)
            ctx.set_state(key, cls(creds))
        return cast(Self, ctx.get_state(key))

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

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute a GraphQL query against the Stacklet Platform API.

        Args:
            query: The GraphQL query string
            variables: Optional variables for the query

        Returns:
            Query result as dictionary
        """
        request_data: dict[str, Any] = {"query": query}
        if variables:
            request_data["variables"] = variables

        response = await self.session.post(self.credentials.endpoint, json=request_data)
        # Don't raise on HTTP errors initially - backend erroneously sets HTTP status codes
        # for GraphQL-level errors. GraphQL transport should be HTTP 200 with errors in payload.
        # However, if we can't parse JSON, then it's likely a real HTTP error.
        try:
            return cast(dict[str, Any], response.json())
        except Exception:
            # If JSON parsing fails, fall back to standard HTTP error handling
            response.raise_for_status()
            raise  # Re-raise the JSON parsing error

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

    async def list_types(self, match: str | None = None) -> list[str]:
        """
        List the types available in the GraphQL API.

        Args:
            match: Optional regular expression filter

        Returns:
            List of type names
        """
        schema = await self.get_schema()
        names = schema.type_map.keys()

        if match:
            f = re.compile(match)
            names = filter(f.search, names)

        return sorted(names)

    async def get_types(self, type_names: list[str]) -> dict[str, str]:
        """
        Retrieve information about specific types in the GraphQL API.

        Args:
            type_names: Names of requested types

        Returns:
            Dictionary mapping valid type names to GraphQL SDL definitions
        """
        schema = await self.get_schema()
        found = {}

        for type_name in type_names:
            if match := schema.type_map.get(type_name):
                found[type_name] = print_type(match)

        return found
