# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import asyncio
import json

from typing import Annotated, Any, Callable

from fastmcp import Context
from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from pydantic import AnyUrl, Field

from mcp.types import ContentBlock, EmbeddedResource, TextContent, TextResourceContents

from ..settings import SETTINGS
from ..utils.file import download_file
from ..utils.json import json_guard
from ..utils.text import get_file_text
from ..utils.tool import ToolsetInfo, info_tool_result, make_tool
from .models import (
    Query,
    QueryArchiveResult,
    QueryResult,
    QueryUpsert,
    ToolQueryList,
    ToolQueryListItem,
    ToolQueryListPagination,
    ToolQueryResult,
    ToolQueryResultArtifact,
)
from .redash import AssetDBClient


def tools() -> list[Tool]:
    """List of available AssetDB tools."""
    tools: list[Tool] = [
        make_tool(assetdb_sql_info, read_only=True, open_world=False),
        _result_tool(assetdb_sql_query),
        make_tool(assetdb_query_list, read_only=True),
        make_tool(assetdb_query_get, read_only=True),
        _result_tool(assetdb_query_result),
    ]
    if SETTINGS.assetdb_allow_save:
        # Saving against an existing query_id overwrites its stored SQL.
        tools.append(make_tool(assetdb_query_save, read_only=False, destructive=True))
    if SETTINGS.assetdb_allow_archive:
        # Archiving also drops the query's visualizations and alerts and can't be
        # undone through the API, but archiving twice changes nothing further.
        tools.append(
            make_tool(assetdb_query_archive, read_only=False, destructive=True, idempotent=True)
        )
    return tools


def _result_tool(fn: Callable[..., Any]) -> Tool:
    """Build one of the two tools that run SQL and return a hand-built ToolResult.

    SQL reaches Redash as written; nothing here holds it to reads, so what a call
    can do is whatever the data source's role allows it to do. The same goes for
    the stored SQL a saved query runs.

    Neither tool can advertise its shape through its return annotation, so declare
    the output schema explicitly rather than leaving clients without one.
    """
    return make_tool(
        fn,
        read_only=False,
        destructive=True,
        output_schema=ToolQueryResult.model_json_schema(),
    )


def assetdb_sql_info() -> ToolsetInfo:
    """
    Essential guide for working with AssetDB - read this before writing SQL queries.

    AssetDB is Stacklet's massive cloud asset warehouse containing billions of records
    across resources, costs, tags, and relationships. This guide explains the schema,
    performance best practices, and common query patterns.

    ⚠️  Critical: Many tables are extremely large and require careful indexing and
    filtering to avoid timeouts. This guide shows you how to query safely and efficiently.
    """
    return info_tool_result(get_file_text("assetdb/sql_info.md"))


@json_guard
async def assetdb_query_list(
    ctx: Context,
    page: Annotated[
        int, Field(ge=1, default=1, description="Page number for pagination (1-based)")
    ],
    page_size: Annotated[
        int,
        Field(
            ge=1, le=100, default=25, description="Number of queries to return per page (max 100)"
        ),
    ],
    search: Annotated[
        str | None,
        Field(
            None,
            description="Search term to match against query names, descriptions, and SQL content",
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(None, description="List of tags to filter queries by (all must match)"),
    ] = None,
) -> ToolQueryList:
    """
    Browse and search through saved SQL queries in AssetDB.

    Use this to discover existing queries before creating new ones, or to find
    queries by name, content, or tags. Results are paginated for performance.

    Common use cases:
    - Find queries related to a specific topic: search="cost analysis"
    - Browse queries by category: tags=["production", "monitoring"]
    - List recently created queries: page=1, page_size=10

    Next steps: Use assetdb_query_get() to get full details or assetdb_query_result()
    to execute.
    """
    client = AssetDBClient.get(ctx)
    response = await client.list_queries(
        page=page,
        page_size=page_size,
        search=search,
        tags=tags,
    )

    # Clean up the response for LLM consumption
    queries = []
    for q in response.results:
        queries.append(
            {
                "id": q.id,
                "name": q.name,
                "description": q.description,
                "has_parameters": bool(q.options.get("parameters")),
                "data_source_id": q.data_source_id,
                "is_draft": q.is_draft,
                "is_favorite": q.is_favorite,
                "tags": q.tags,
                "user": q.user,
            }
        )

    query_items = [ToolQueryListItem(**q) for q in queries]
    pagination = ToolQueryListPagination(
        page=response.page,
        page_size=response.page_size,
        has_next_page=page * page_size < response.count,
        total_count=response.count,
    )

    return ToolQueryList(queries=query_items, pagination=pagination)


@json_guard
async def assetdb_query_get(
    ctx: Context,
    query_id: Annotated[int, Field(ge=1, description="ID of the query to retrieve details for")],
) -> Query:
    """
    Get complete details for a saved query including its SQL, parameters, and metadata.

    Use this when you need to examine a query's structure, understand its parameters,
    or check its settings before executing or modifying it.

    Returns the full query object with SQL text, parameter definitions, tags,
    creation info, and other metadata. Use assetdb_query_result() to actually
    execute the query and get data.
    """
    client = AssetDBClient.get(ctx)
    return await client.get_query(query_id)


@json_guard
async def assetdb_query_save(
    ctx: Context,
    query_id: Annotated[
        int | None,
        Field(
            None,
            ge=1,
            description="ID of existing query to update (if provided), otherwise creates new query",
        ),
    ] = None,
    name: Annotated[
        str | None,
        Field(
            None, min_length=1, description="Display name for the query (required for new queries)"
        ),
    ] = None,
    query: Annotated[
        str | None,
        Field(None, min_length=1, description="SQL query text (required for new queries)"),
    ] = None,
    description: Annotated[
        str | None, Field(None, description="Description or documentation for the query")
    ] = None,
    tags: Annotated[
        list[str] | None, Field(None, description="List of tags for categorizing the query")
    ] = None,
    options: Annotated[
        dict[str, Any] | None,
        Field(None, description="Query options including parameter definitions"),
    ] = None,
    is_draft: Annotated[
        bool | None,
        Field(
            None,
            description="Whether the query should be in draft status "
            "(defaults to True for new queries)",
        ),
    ] = None,
) -> Query:
    """
    Save a new query or update an existing one in AssetDB.

    Use this to preserve useful SQL queries for future use and sharing. New queries
    are created as drafts by default - set is_draft=False to publish them.

    Creating a new query (query_id=None):
    - Provide at minimum: name and query (SQL text)
    - Optionally add description, tags for organization

    Updating existing query (provide query_id):
    - Only specify fields you want to change
    - Leave others as None/unset to keep current values

    Tags help organize queries by team, purpose, or data domain. Use descriptive
    names like "cost-analysis", "security", "daily-reports".
    """
    upsert = QueryUpsert(
        name=name,
        query=query,
        description=description,
        tags=tags,
        options=options,
        is_draft=is_draft,
    )

    client = AssetDBClient.get(ctx)
    if query_id and query_id > 0:
        return await client.update_query(query_id, upsert)

    if not upsert.name:  # Accepted by redash, but unreasonable.
        upsert.name = "Untitled LLM Query"
    if upsert.query is None:  # This would actually 500.
        upsert.query = ""  # Maybe also unreasonable, but will get feedback.
    return await client.create_query(upsert)


@json_guard
async def assetdb_query_archive(
    ctx: Context,
    query_id: Annotated[int, Field(ge=1, description="ID of the query to archive")],
) -> QueryArchiveResult:
    """
    Archive a saved query in AssetDB.

    Archives the query by setting its archived status to true. Archived queries are
    hidden from normal query listings but remain in the database. The query's associated
    visualizations and alerts are also removed during archiving.

    This operation cannot be undone through the API, but the query data is preserved
    in the database and could potentially be restored by database administrators.
    """
    client = AssetDBClient.get(ctx)
    await client.delete_query(query_id)
    return QueryArchiveResult(
        success=True,
        message=f"Query {query_id} has been successfully archived",
        query_id=query_id,
    )


@json_guard
async def assetdb_query_result(
    ctx: Context,
    query_id: Annotated[
        int, Field(ge=1, description="ID of the query to execute and get results for")
    ],
    max_age: Annotated[
        int,
        Field(
            ge=-1,
            default=-1,
            description="Maximum age of cached results in seconds "
            "(-1 = any cached result, 0 = always fresh)",
        ),
    ],
    timeout: Annotated[
        int,
        Field(
            ge=5,
            le=300,
            default=60,
            description="Query execution timeout in seconds if not cached (max 300)",
        ),
    ],
    parameters: Annotated[
        dict[str, Any] | None, Field(None, description="Parameter values for parameterized queries")
    ] = None,
) -> ToolResult:
    """
    Execute a saved query and get its results with smart caching.

    This runs a previously saved query and returns links to the results in various
    formats, which can be used to access the data in a preferred format. Redash caches
    results to improve performance - use max_age to control cache behavior.

    Parameters are required for parameterized queries - check the query definition
    first using assetdb_query_get() to see what parameters are expected.

    **Result Handling:**
    - Only the first 20 rows are included in the response to reduce context usage
    - The complete rows are always available: either saved as a JSON file in the
      configured downloads directory, or attached to the response as a JSON resource
    - Download links point at the saved query's results and need a Redash session
    """
    client = AssetDBClient.get(ctx)

    query_result = await client.execute_saved_query(
        query_id=query_id, parameters=parameters, max_age=max_age, timeout=timeout
    )
    query = await client.get_query(query_id)
    return await _tool_query_result(client, query_result, query)


@json_guard
async def assetdb_sql_query(
    ctx: Context,
    query: Annotated[
        str, Field(min_length=1, description="SQL query string to execute against AssetDB")
    ],
    max_age: Annotated[
        int,
        Field(
            ge=-1,
            default=3600,
            description="Maximum age of cached results in seconds "
            "(-1 = any cached result, 0 = always fresh)",
        ),
    ],
    timeout: Annotated[
        int,
        Field(ge=5, le=300, default=60, description="Query execution timeout in seconds (max 300)"),
    ],
) -> ToolResult:
    """
    Execute custom SQL queries directly against the AssetDB data warehouse.

    ⚠️  IMPORTANT: AssetDB contains massive datasets. Always use LIMIT clauses and
    indexed filters to avoid timeouts. Call assetdb_sql_info() first to understand
    the schema and best practices.

    This tool is for ad-hoc analysis and exploration. For frequently-used queries,
    consider saving them with assetdb_query_save() for better performance and reuse.

    **Result Handling:**
    - Only the first 20 rows are included in the response to reduce context usage
    - The complete rows are always available: either saved as a JSON file in the
      configured downloads directory, or attached to the response as a JSON resource
    - For alternate formats, save the query first with assetdb_query_save() then use
      assetdb_query_result()
    """
    client = AssetDBClient.get(ctx)
    query_result = await client.execute_adhoc_query(query, max_age=max_age, timeout=timeout)
    return await _tool_query_result(client, query_result, None)


async def _tool_query_result(
    client: AssetDBClient, query_result: QueryResult, query: Query | None
) -> ToolResult:
    """
    Convert a raw QueryResult into an LLM-friendly ToolQueryResult.

    This helper function processes query results by:
    - Making the complete row data available for analysis with other tools
    - Truncating row data to first 20 rows for context efficiency
    - Generating download links when a saved query is provided
    - Creating a structured response suitable for LLM consumption

    **Full Result Behavior:**
    The caller always gets the complete rows, by exactly one of two routes:
    - downloads_enabled: written to STACKLET_MCP_DOWNLOADS_PATH, path in
      full_results_saved_to. Only useful when the caller shares our filesystem.
    - otherwise: attached to the response as a JSON resource, because a hosted server's
      paths mean nothing to its callers and the files would accumulate forever.

    Either way the payload is just the rows; every other field of the QueryResult is
    already in the ToolQueryResult envelope, so repeating it would double the bytes.

    **Download Links:**
    - Saved queries (query != None): Provides alternate_formats with download links
    - Ad-hoc queries (query == None): No alternate_formats, as there is no URL to give

    Args:
        client: AssetDB client for generating download URLs
        query_result: Raw query result from Redash API
        query: Optional saved query object (None for ad-hoc queries)

    Returns:
        ToolResult carrying the truncated ToolQueryResult, and the full rows when
        they are not on disk
    """
    # We've always got the whole dataset, but we generally don't want to dump it all
    # into context. Serializing it is expensive enough to be worth keeping off the
    # event loop, which every other request in a hosted process is sharing.
    rows = query_result.data.rows
    identity = f"{query.id}_{query_result.id}" if query else f"{query_result.id}"

    full_results_saved_to = None
    full_results_resource = None
    if SETTINGS.downloads_enabled:
        full_results_saved_to = await asyncio.to_thread(_write_rows, rows, identity)
    else:
        full_results_resource = await asyncio.to_thread(_rows_resource, rows, identity)

    alternate_formats = None
    if query:
        # If we've got an actual Query, its results are addressable, so we can give
        # back handles to the data in all available formats.
        result_urls = client.get_query_result_urls(query, query_result)
        alternate_formats = [
            ToolQueryResultArtifact(format=fmt, download_from=url)
            for fmt, url in result_urls.items()
        ]

    # LLM-suited result with truncated data.
    result = ToolQueryResult(
        result_id=query_result.id,
        query_id=query.id if query else None,
        query_text=query_result.query,
        query_runtime=query_result.runtime,
        query_timestamp=query_result.retrieved_at,
        columns=query_result.data.columns,
        row_count=len(rows),
        some_rows=rows[:20],
        full_results_saved_to=full_results_saved_to,
        alternate_formats=alternate_formats,
    )

    # Hand-build the content blocks: fastmcp only generates the text block for us when
    # we don't supply any, and we need to sit the full results alongside it.
    content: list[ContentBlock] = [TextContent(type="text", text=result.model_dump_json())]
    if full_results_resource:
        content.append(full_results_resource)
    return ToolResult(content=content, structured_content=result.model_dump(mode="json"))


def _write_rows(rows: list[dict[str, Any]], identity: str) -> str:
    """Write rows to a JSON file in the downloads directory, returning its path."""
    with download_file("w", f"assetdb_{identity}", ".json") as f:
        json.dump(rows, f, ensure_ascii=False, default=str)
        return f.name


def _rows_resource(rows: list[dict[str, Any]], identity: str) -> EmbeddedResource:
    """Attach rows to the response as a JSON resource.

    The URI identifies the payload; it is not separately readable from this server.
    """
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            uri=AnyUrl(f"assetdb://query_results/{identity}.json"),
            mimeType="application/json",
            text=json.dumps(rows, ensure_ascii=False, default=str),
        ),
    )
