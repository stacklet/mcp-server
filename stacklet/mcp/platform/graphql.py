# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
Stacklet Platform client for GraphQL API operations.
"""

import asyncio
import hashlib
import logging
import re
import time

from typing import Any, Self, cast

from fastmcp import Context
from graphql import (
    GraphQLSchema,
    OperationType,
    build_client_schema,
    get_introspection_query,
    parse,
    print_type,
)

from ..lifespan import server_singleton
from ..request_credentials import current_credentials
from ..settings import SETTINGS
from ..upstream_errors import check_response
from ..utils.error import AnnotatedError
from ..utils.http import PerCallClient
from .models import (
    ConnectionExport,
    ExportRequest,
    GetTypesResult,
    GraphQLError,
    GraphQLQueryResult,
    ListTypesResult,
)


logger = logging.getLogger(__name__)


def _schema_digest(schema: GraphQLSchema) -> str:
    """Digest the schema's type-name list for drift detection."""
    names = sorted(schema.type_map.keys())
    return hashlib.sha256("\n".join(names).encode()).hexdigest()


class PlatformClient(PerCallClient):
    """Client for Stacklet Platform GraphQL API.

    Auth is NOT held on the instance — each HTTP call reads per-request
    credentials via `current_credentials(ctx)` and passes the bearer token
    per-call. The shared-transport/per-call-AsyncClient pattern lives on
    `PerCallClient`.
    """

    # Drift-alarm interval. One probe per worker per interval after the
    # schema has been cached; emits a warn-level log if the live type set
    # has changed, so we hear about it before users do.
    SCHEMA_DRIFT_INTERVAL_SECONDS = 3600.0

    def __init__(self, enable_mutations: bool = False):
        super().__init__()
        self.enable_mutations = enable_mutations
        self._schema_cache: GraphQLSchema | None = None
        self._schema_lock = asyncio.Lock()
        self._schema_digest: str | None = None
        self._last_drift_check: float = 0.0

    @classmethod
    def get(cls, ctx: Context) -> Self:
        def construct() -> PlatformClient:
            return cls(SETTINGS.platform_allow_mutations)

        return cast(Self, server_singleton(ctx, "PLATFORM_CLIENT", construct))

    async def query(
        self, ctx: Context, query: str, variables: dict[str, Any]
    ) -> GraphQLQueryResult:
        """
        Execute a GraphQL query against the Stacklet Platform API.

        Args:
            ctx: FastMCP request context.
            query: The GraphQL query string
            variables: Optional variables for the query

        Returns:
            Structured GraphQL query result
        """
        if not self.enable_mutations and has_mutations(query):
            raise AnnotatedError(
                problem="Mutations disabled",
                likely_cause="the user doesn't want you to run mutations",
                next_steps="tell the user to set 'STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS'",
            )

        return await self._query(ctx, query, variables)

    async def get_schema(self, ctx: Context) -> GraphQLSchema:
        """
        Retrieve the GraphQL schema from the Stacklet Platform API.

        First call introspects and caches; subsequent calls return the cache.
        Concurrent cold-start callers wait on an instance-level lock so only
        one introspection runs per worker. After the cache is warm, a
        drift-alarm probe runs at most once per `SCHEMA_DRIFT_INTERVAL_SECONDS`
        and emits a warn-level log if the live type set has changed — so
        operators hear about schema drift before users do.

        Returns:
            GraphQL schema object
        """
        if self._schema_cache is not None:
            await self._maybe_check_drift(ctx)
            return self._schema_cache

        async with self._schema_lock:
            if self._schema_cache is not None:
                return self._schema_cache
            schema = await self._introspect(ctx)
            self._schema_cache = schema
            self._schema_digest = _schema_digest(schema)
            self._last_drift_check = time.monotonic()
            return schema

    async def _introspect(self, ctx: Context) -> GraphQLSchema:
        creds = current_credentials(ctx)
        introspection_query = {"query": get_introspection_query()}

        async with self._async_client() as session:
            response = await session.post(
                creds.endpoint,
                json=introspection_query,
                headers=self._auth_headers(creds.access_token),
            )
        check_response(response)

        result = response.json()
        if errors := result.get("errors"):
            raise Exception(f"GraphQL introspection errors: {errors}")

        schema = result.get("data", {}).get("__schema")
        if not schema:
            raise Exception("GraphQL introspection returned no schema data")

        return build_client_schema({"__schema": schema})

    async def _maybe_check_drift(self, ctx: Context) -> None:
        """Probe for schema drift at most once per interval per worker.

        This is telemetry, not a gate — the request still succeeds even if
        the digest changed. The interval bookkeeping runs inside
        `_schema_lock` but the actual network probe runs OUTSIDE the
        lock — otherwise a slow or hung probe would stall every concurrent
        `get_schema()` caller for the full httpx timeout. If the probe
        fails, the timestamp is rewound so the next request retries rather
        than going silent for a full interval on a transient issue.
        """
        now = time.monotonic()
        if now - self._last_drift_check < self.SCHEMA_DRIFT_INTERVAL_SECONDS:
            return

        async with self._schema_lock:
            now = time.monotonic()
            if now - self._last_drift_check < self.SCHEMA_DRIFT_INTERVAL_SECONDS:
                return
            previous_check = self._last_drift_check
            self._last_drift_check = now

        try:
            current_digest = await self._probe_schema_digest(ctx)
        except AnnotatedError as exc:
            # `check_response` already translates 401/403/5xx into
            # AnnotatedError. These reflect the triggering caller's session
            # state or an upstream blip, not real schema drift — log at
            # debug so real drift signals don't get drowned out.
            self._last_drift_check = previous_check
            logger.debug("schema_drift_probe_skipped: %s", exc)
            return
        except Exception as exc:
            self._last_drift_check = previous_check
            logger.warning("schema_drift_probe_failed: %s", exc)
            return

        if current_digest != self._schema_digest:
            logger.warning(
                "schema_drift_detected cached=%s live=%s",
                self._schema_digest,
                current_digest,
            )

    async def _probe_schema_digest(self, ctx: Context) -> str:
        """Run a lightweight `__schema { types { name } }` query and digest
        the type-name list. Cheap probe for drift detection.
        """
        creds = current_credentials(ctx)
        probe_query = {"query": "{ __schema { types { name } } }"}

        async with self._async_client() as session:
            response = await session.post(
                creds.endpoint,
                json=probe_query,
                headers=self._auth_headers(creds.access_token),
            )
        check_response(response)

        result = response.json()
        if result.get("errors"):
            raise Exception(f"Schema probe errors: {result['errors']}")
        types = result.get("data", {}).get("__schema", {}).get("types", [])
        names = sorted(t["name"] for t in types if "name" in t)
        return hashlib.sha256("\n".join(names).encode()).hexdigest()

    async def list_types(self, ctx: Context, match: str | None = None) -> ListTypesResult:
        """
        List the types available in the GraphQL API.

        Args:
            ctx: FastMCP request context.
            match: Optional regular expression filter

        Returns:
            Structured result with context
        """
        schema = await self.get_schema(ctx)
        names = schema.type_map.keys()

        if match:
            f = re.compile(match)
            names = filter(f.search, names)

        return ListTypesResult(searched_for=match, found_types=sorted(names))

    async def get_types(self, ctx: Context, type_names: list[str]) -> GetTypesResult:
        """
        Retrieve information about specific types in the GraphQL API.

        Args:
            ctx: FastMCP request context.
            type_names: Names of requested types

        Returns:
            Structured result with context
        """
        schema = await self.get_schema(ctx)
        found = {}
        missing = []

        for type_name in sorted(set(type_names)):
            if match := schema.type_map.get(type_name):
                found[type_name] = print_type(match)
            else:
                missing.append(type_name)

        return GetTypesResult(asked_for=type_names, found_sdl=found, not_found=missing)

    async def start_export(self, ctx: Context, spec: ExportRequest) -> str:
        """
        Start a dataset export and poll for completion, then download the result.

        Args:
            ctx: FastMCP request context.
            spec: Validated export configuration with connection field, columns, and options

        Returns:
            Node ID of started export job.
        """
        result = await self._query(ctx, self.Q_START_EXPORT, {"input": spec.for_graphql()})
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

    async def wait_for_export(
        self, ctx: Context, dataset_id: str, timeout_s: int
    ) -> ConnectionExport:
        cutoff = time.monotonic() + timeout_s
        interval_s = 2
        while True:
            # Always try at least once.
            export = await self._get_export(ctx, dataset_id)
            if export.completed:
                return export

            # Aim for the final attempt to happen at cutoff time.
            remaining_s = cutoff - time.monotonic()
            if remaining_s <= 0:
                return export
            await asyncio.sleep(min(interval_s, remaining_s))
            interval_s *= 2

    async def _get_export(self, ctx: Context, dataset_id: str) -> ConnectionExport:
        result = await self.query(ctx, self.Q_GET_EXPORT, {"id": dataset_id})
        if result.errors:
            raise RuntimeError(f"GraphQL errors: {result.errors}")

        # If no errors, data is at least guaranteed truthy.
        fields = cast(dict[str, Any], result.data)["node"]
        return ConnectionExport(**fields)

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

    async def _query(
        self, ctx: Context, query: str, variables: dict[str, Any]
    ) -> GraphQLQueryResult:
        creds = current_credentials(ctx)
        request_data = {"query": query, "variables": variables}
        async with self._async_client() as session:
            response = await session.post(
                creds.endpoint,
                json=request_data,
                headers=self._auth_headers(creds.access_token),
            )

        # Auth and upstream-outage classes get mapped to user-friendly
        # AnnotatedErrors before we try to parse the body. Other non-2xx
        # codes are treated as possibly-valid GraphQL error responses
        # (platform does this deliberately).
        if response.status_code in (401, 403) or response.status_code >= 500:
            check_response(response)

        # Platform sometimes returns non-auth 4xx with a valid GraphQL body.
        # 401/403/5xx were already raised above; here we accept the body.
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

    @staticmethod
    def _auth_headers(access_token: str) -> dict[str, str]:
        # Content-Type is set by httpx when `json=` is passed.
        return {"Authorization": f"Bearer {access_token}"}


def has_mutations(query: str) -> bool:
    """Return whether a GraphQL query string calls mutations."""
    doc = parse(query)
    operations = {dd.operation for dd in doc.definitions}
    return OperationType.MUTATION in operations
