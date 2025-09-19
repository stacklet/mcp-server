from typing import Annotated, Any, Callable

from fastmcp import Context
from pydantic import Field

from ..settings import SETTINGS
from ..utils.json import json_guard
from ..utils.text import get_file_text
from ..utils.tool import ToolsetInfo, info_tool_result
from .models import (
    DownloadResult,
    ExportFormat,
    Query,
    QueryArchiveResult,
    QueryDownloadResults,
    QueryListItem,
    QueryListPagination,
    QueryListResult,
    QueryResult,
    QueryResultDownloadDetails,
    QueryUpsert,
)
from .redash import AssetDBClient


def tools() -> list[Callable[..., Any]]:
    """List of available AssetDB tools."""
    tools: list[Callable[..., Any]] = [
        assetdb_sql_info,
        assetdb_sql_query,
        assetdb_query_list,
        assetdb_query_get,
        assetdb_query_results,
    ]
    if SETTINGS.assetdb_allow_save:
        tools.append(assetdb_query_save)
        tools.append(assetdb_query_archive)
    return tools


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
) -> QueryListResult:
    """
    Browse and search through saved SQL queries in AssetDB.

    Use this to discover existing queries before creating new ones, or to find
    queries by name, content, or tags. Results are paginated for performance.

    Common use cases:
    - Find queries related to a specific topic: search="cost analysis"
    - Browse queries by category: tags=["production", "monitoring"]
    - List recently created queries: page=1, page_size=10

    Next steps: Use assetdb_query_get() to get full details or assetdb_query_results() to execute.
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
                "is_archived": q.is_archived,
                "is_draft": q.is_draft,
                "is_favorite": q.is_favorite,
                "tags": q.tags,
                "user": q.user,
            }
        )

    query_items = [QueryListItem(**q) for q in queries]
    pagination = QueryListPagination(
        page=response.page,
        page_size=response.page_size,
        has_next_page=page * page_size < response.count,
        total_count=response.count,
    )

    return QueryListResult(queries=query_items, pagination=pagination)


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
    creation info, and other metadata. Use assetdb_query_results() to actually
    execute the query and get data.
    """
    client = AssetDBClient.get(ctx)
    return await client.get_query(query_id)


@json_guard
async def assetdb_query_results(
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
) -> QueryDownloadResults:
    """
    Execute a saved query and get its results with smart caching.

    This runs a previously saved query and returns links to the results in various
    formats, which can be used to access the data in a preferred format. Redash caches
    results to improve performance - use max_age to control cache behavior.

    Parameters are required for parameterized queries - check the query definition
    first using assetdb_query_get() to see what parameters are expected.
    """
    client = AssetDBClient.get(ctx)

    result_id = await client.execute_saved_query(
        query_id=query_id, parameters=parameters, max_age=max_age, timeout=timeout
    )

    query_details = await client.get_query(query_id)
    result_urls = client.get_query_result_urls(query_id, result_id, query_details.api_key)
    downloads = [
        QueryResultDownloadDetails(format=fmt, url=url) for fmt, url in result_urls.items()
    ]
    return QueryDownloadResults(
        result_id=result_id,
        query_id=query_id,
        downloads=downloads,
    )


@json_guard
async def assetdb_sql_query(
    ctx: Context,
    query: Annotated[
        str, Field(min_length=1, description="SQL query string to execute against AssetDB")
    ],
    timeout: Annotated[
        int,
        Field(ge=5, le=300, default=60, description="Query execution timeout in seconds (max 300)"),
    ],
    download_format: Annotated[
        ExportFormat | None,
        Field(
            None,
            description='Format to download results in ("csv", "json", "tsv", "xlsx"). '
            "If specified, saves to file instead of returning data",
        ),
    ] = None,
    download_path: Annotated[
        str | None,
        Field(
            None,
            description="Path where to save downloaded file (ignored if download_format not set)",
        ),
    ] = None,
) -> QueryResult | DownloadResult:
    """
    Execute custom SQL queries directly against the AssetDB data warehouse.

    ⚠️  IMPORTANT: AssetDB contains massive datasets. Always use LIMIT clauses and
    indexed filters to avoid timeouts. Call assetdb_sql_info() first to understand
    the schema and best practices.

    This tool is for ad-hoc analysis and exploration. For frequently-used queries,
    consider saving them with assetdb_query_save() for better performance and reuse.
    """
    client = AssetDBClient.get(ctx)
    result_id = await client.execute_adhoc_query(query, timeout=timeout)
    if not download_format:
        return await client.get_query_result_data(result_id)

    file_path = await client.download_query_result(
        result_id=result_id, format=download_format, download_path=download_path
    )
    return DownloadResult(
        file_path=file_path,
        format=download_format,
        result_id=result_id,
    )


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
