from typing import Annotated, Any, Callable

from fastmcp import Context
from pydantic import Field

from ..settings import SETTINGS
from ..utils import ToolsetInfo, get_file_text, info_tool_result, json_guard
from .models import ExportFormat, QueryDownloadDetails, QueryResults, QueryUpsert
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
    return tools


@json_guard
async def assetdb_query_list(
    ctx: Context,
    page: Annotated[int, Field(ge=1, default=1)],
    page_size: Annotated[int, Field(ge=1, le=100, default=25)],
    search: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    List and search saved queries using Redash's built-in capabilities.

    Args:
        page: Page number (1-based)
        page_size: Queries per page (max 100)
        search: Search query names, descriptions, and SQL content
        tags: Match only queries with these tags

    Returns:
        List of queries with pagination metadata
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

    return {
        "queries": queries,
        "pagination": {
            "page": response.page,
            "page_size": response.page_size,
            "has_next_page": page * page_size < response.count,
            "total_count": response.count,
        },
    }


@json_guard
async def assetdb_query_get(ctx: Context, query_id: int) -> dict[str, Any]:
    """
    Get detailed information about a specific saved query.

    Args:
        query_id: ID of the query to retrieve

    Returns:
        Complete query object with SQL and parameters
    """
    client = AssetDBClient.get(ctx)
    result = await client.get_query(query_id)
    result.pop("visualizations", None)  # sometimes large, not currently relevant
    result.pop("api_key", None)  # avoid sharing the secret
    return result


@json_guard
async def assetdb_query_results(
    ctx: Context,
    query_id: int,
    max_age: Annotated[int, Field(ge=-1, default=-1)],
    timeout: Annotated[int, Field(ge=5, le=300, default=60)],
    parameters: dict[str, Any] | None = None,
) -> QueryResults:
    """Get results for a query with caching control.

    Results are provided in the form of URLs for each supported data format,
    which can be used to fetch the result data in the desired format.

    Args:
        query_id: ID of the query to get results for
        parameters: Optional parameters for the query (for parameterized queries)
        max_age: Maximum age of cached results in seconds (default -1 = any cached
                 result, 0 = always fresh)
        timeout: Timeout in seconds for query execution if not cached (default 60,
                 max 300)
    Returns:
        Details about query results, including URLs to get the result data in differnet formats.

    """
    client = AssetDBClient.get(ctx)

    result_id = await client.execute_saved_query(
        query_id=query_id, parameters=parameters, max_age=max_age, timeout=timeout
    )

    query_details = await client.get_query(query_id)
    result_urls = client.get_query_result_urls(query_id, result_id, query_details["api_key"])
    downloads = [QueryDownloadDetails(format=fmt, url=url) for fmt, url in result_urls.items()]
    return QueryResults(
        result_id=result_id,
        query_id=query_id,
        downloads=downloads,
    )


@json_guard
async def assetdb_sql_query(
    ctx: Context,
    query: str,
    timeout: Annotated[int, Field(ge=5, le=300, default=60)],
    download_format: ExportFormat | None = None,
    download_path: str | None = None,
) -> dict[str, Any]:
    """
    Execute an ad-hoc SQL query against AssetDB.

    Only call this tool when you understand the principles outlined in the
    assetdb_sql_info tool. Always explore the schema first and use appropriate
    filters to scope your queries.

    Args:
        query: The SQL query string to execute
        timeout: Query timeout in seconds (default 60, max 300)
        download_format: Optional format to download results ("csv", "json", "tsv",
                         "xlsx"). If specified, results are downloaded to file instead
                         of returned directly.
        download_path: Optional path to save downloaded file. Ignored if download
                       format not set.

    Returns:
        Query results with data, columns, and metadata
        OR download information if download_format was specified
    """
    client = AssetDBClient.get(ctx)
    result_id = await client.execute_adhoc_query(query, timeout=timeout)
    if not download_format:
        return await client.get_query_result_data(result_id)

    file_path = await client.download_query_result(
        result_id=result_id, format=download_format, download_path=download_path
    )
    return {
        "downloaded": True,
        "file_path": file_path,
        "format": download_format,
        "result_id": result_id,
    }


@json_guard
async def assetdb_query_save(
    ctx: Context,
    query_id: int | None = None,
    name: str | None = None,
    query: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    options: dict[str, Any] | None = None,
    is_draft: bool | None = None,
) -> dict[str, Any]:
    """
    With "query_id" set, updates an existing query; otherwise creates a new
    query. All arguments are optional.

    Args:
        query_id: Int ID of existing query to update
        name: Query display name string
        query: SQL query text string
        description: Query description string
        tags: List of string tags for categorization
        options: Query options/parameters configuration dict
        is_draft: Draft status (defaults to True for new queries)

    Returns:
        Complete query object with ID, timestamps, and metadata
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
        result = await client.update_query(query_id, upsert)
    else:
        if not upsert.name:  # Accepted by redash, but unreasonable.
            upsert.name = "Untitled LLM Query"
        if upsert.query is None:  # This would actually 500.
            upsert.query = ""  # Maybe also unreasonable, but will get feedback.
        result = await client.create_query(upsert)

    result.pop("visualizations", None)  # sometimes large, not currently relevant
    return result


def assetdb_sql_info() -> ToolsetInfo:
    """
    Key information for LLMs using the assetdb_sql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the AssetDB SQL toolset.
    """
    return info_tool_result(get_file_text("assetdb/sql_info.md"))
