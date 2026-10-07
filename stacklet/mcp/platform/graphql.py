# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
Stacklet Platform client for GraphQL API operations.
"""

import asyncio
import os
import re
import time

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Self, cast
from urllib.parse import urlparse

import httpx

from fastmcp import Context
from graphql import (
    DocumentNode,
    GraphQLSchema,
    GraphQLSyntaxError,
    OperationType,
    build_client_schema,
    get_introspection_query,
    parse,
    print_type,
    validate,
)

from .. import USER_AGENT
from ..lifespan import ServerStateProtocol
from ..settings import SETTINGS
from ..stacklet_auth import StackletCredentials
from ..utils.error import AnnotatedError
from ..utils.file import download_file
from .models import (
    ConnectionExport,
    ExportRequest,
    GetTypesResult,
    GraphQLError,
    GraphQLQueryResult,
    ListTypesResult,
)


HOSTED_DOWNLOAD_NOTE = (
    "Open this link in a browser where you're signed in to Stacklet. "
    "It works for 24 hours and only for you."
)


class PlatformClient:
    """Client for Stacklet Platform GraphQL API."""

    def __init__(
        self,
        credentials: StackletCredentials,
        server_state: ServerStateProtocol,
        enable_mutations: bool = False,
    ):
        self.credentials = credentials
        self.server_state = server_state
        self.enable_mutations = enable_mutations

        transport = server_state.ensure_cached("HTTP_TRANSPORT", httpx.AsyncHTTPTransport)
        self.session = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {credentials.access_token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "X-Stacklet-MCP": "1",
            },
            transport=transport,
            timeout=30.0,
        )

    @classmethod
    def get(cls, ctx: Context) -> Self:
        state = ctx.request_context.lifespan_context  # type: ignore[union-attr]
        return cls(StackletCredentials.get(ctx), state, SETTINGS.platform_allow_mutations)

    async def query(self, query: str, variables: dict[str, Any]) -> GraphQLQueryResult:
        """
        Execute a GraphQL query against the Stacklet Platform API.

        Args:
            query: The GraphQL query string
            variables: Optional variables for the query

        Returns:
            Structured GraphQL query result
        """
        try:
            doc = parse(query)
        except GraphQLSyntaxError as e:
            raise AnnotatedError(
                problem=f"GraphQL syntax error: {e.message}",
                likely_cause="query has invalid syntax",
                next_steps="fix the syntax error in the query",
            )

        if not self.enable_mutations and has_mutations(doc):
            raise AnnotatedError(
                problem="Mutations disabled",
                likely_cause="the user doesn't want you to run mutations",
                next_steps="tell the user to set 'STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS'",
            )

        schema = await self.get_schema()
        if validation_errors := validate(schema, doc):
            error_messages = "\n".join(str(e) for e in validation_errors)
            raise AnnotatedError(
                problem=f"GraphQL validation failed:\n{error_messages}",
                likely_cause="query references fields or types not in the schema",
                next_steps=(
                    "use 'platform_graphql_list_types' and 'platform_graphql_get_types'"
                    " to check the schema, then fix the query"
                ),
            )

        return await self._query(query, variables)

    async def get_schema(self) -> GraphQLSchema:
        """Retrieve the GraphQL schema, using the server-level cache."""
        return await self.server_state.ensure_cached_async("PLATFORM_SCHEMA", self._fetch_schema)

    async def _fetch_schema(self) -> GraphQLSchema:
        introspection_query = {"query": get_introspection_query()}
        response = await self.session.post(self.credentials.endpoint, json=introspection_query)
        response.raise_for_status()

        result = response.json()
        if errors := result.get("errors"):
            raise Exception(f"GraphQL introspection errors: {errors}")

        schema = result.get("data", {}).get("__schema")
        if not schema:
            raise Exception("GraphQL introspection returned no schema data")

        return build_client_schema({"__schema": schema})

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
        result = await self._query(self.Q_START_EXPORT, {"input": spec.for_graphql()})
        if result.errors:
            raise AnnotatedError(
                problem=f"Export mutation failed: {result.errors}",
                likely_cause="what it says",
                next_steps="check data types with 'platform_get_types'",
            )

        # If no errors, data is at least guaranteed truthy.
        export = cast(dict[str, Any], result.data)["exportConnection"]["export"]
        return cast(dict[str, str], export)["id"]

    Q_START_EXPORT = """
        mutation exportConnection($input: ExportConnectionInput!) {
            exportConnection(input: $input) { export { id } }
        }
    """

    async def wait_for_export(self, dataset_id: str, timeout_s: int) -> ConnectionExport:
        cutoff = time.monotonic() + timeout_s
        interval_s = 2
        while True:
            # Always try at least once.
            export = await self._get_export(dataset_id)
            if export.completed:
                return await self._deliver(export)

            # Aim for the final attempt to happen at cutoff time.
            remaining_s = cutoff - time.monotonic()
            if remaining_s <= 0:
                return export
            await asyncio.sleep(min(interval_s, remaining_s))
            interval_s *= 2

    async def _get_export(self, dataset_id: str) -> ConnectionExport:
        result = await self._query(self.Q_GET_EXPORT, {"id": dataset_id})
        if result.errors:
            raise RuntimeError(f"GraphQL errors: {result.errors}")

        # If no errors, data is at least guaranteed guaranteed truthy.
        fields = cast(dict[str, Any], result.data)["node"]
        if fields is None:
            raise AnnotatedError(
                problem=f"Dataset export {dataset_id} not found",
                likely_cause="the ID is wrong, or the export belongs to another user",
                next_steps="start a new export with platform_dataset_export",
            )
        return ConnectionExport(**fields)

    async def _deliver(self, export: ConnectionExport) -> ConnectionExport:
        """Make a completed export's file reachable by the caller.

        The download URL only works with the credentials of the user who started the
        export, so the server fetches it when the caller can read the result, and
        otherwise tells the caller to open it in their own signed-in browser.
        """
        # The platform keeps returning the URL after the file has expired.
        if not export.download_url or (
            export.available_until and export.available_until <= datetime.now(UTC)
        ):
            return export
        if not SETTINGS.downloads_enabled:
            return export.model_copy(update={"download_note": HOSTED_DOWNLOAD_NOTE})
        path = await self._download(export.dataset_id, export.download_url)
        return export.model_copy(update={"full_results_saved_to": path})

    async def _download(self, dataset_id: str, url: str) -> str:
        """Stream an export file into the downloads directory, returning its path."""
        next_steps = (
            f"retry with platform_dataset_lookup, or give the user {url} "
            "to open in a browser where they're signed in to Stacklet"
        )
        try:
            async with self.session.stream("GET", url) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise AnnotatedError(
                        problem=(
                            f"Downloading dataset export {dataset_id} failed "
                            f"with HTTP {response.status_code}"
                        ),
                        likely_cause="the export expired, or these credentials cannot read it",
                        next_steps=next_steps,
                        original_error=response.text,
                    )
                return await self._save(response, PurePosixPath(urlparse(url).path).suffix)
        except httpx.HTTPError as e:
            raise AnnotatedError(
                problem=f"Downloading dataset export {dataset_id} failed",
                likely_cause="a network error while fetching the file",
                next_steps=next_steps,
                original_error=str(e),
            ) from e

    async def _save(self, response: httpx.Response, suffix: str) -> str:
        """Write a response body to a new downloads file, removing it if anything fails.

        File I/O runs in a thread so a large export does not block the event loop.
        """
        f = await asyncio.to_thread(download_file, "wb", "export_", suffix or ".csv")
        try:
            async for chunk in response.aiter_bytes():
                await asyncio.to_thread(f.write, chunk)
            await asyncio.to_thread(f.close)
        except BaseException:
            with suppress(OSError):
                f.close()
            os.unlink(f.name)
            raise
        return f.name

    Q_GET_EXPORT = """
        query getExport($id: ID!) {
          node(id: $id) {
            ... on ConnectionExport {
              id
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

    async def _query(self, query: str, variables: dict[str, Any]) -> GraphQLQueryResult:
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


def has_mutations(doc: DocumentNode) -> bool:
    """Return whether a GraphQL document calls mutations."""
    operations = {dd.operation for dd in doc.definitions}
    return OperationType.MUTATION in operations
