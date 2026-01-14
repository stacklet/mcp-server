# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from typing import Annotated, Any, Callable

from fastmcp import Context
from pydantic import Field

from ..utils.json import json_guard
from ..utils.text import get_file_text
from ..utils.tool import ToolsetInfo, info_tool_result
from .graphql import PlatformClient
from .models import (
    ConnectionExport,
    ExportColumn,
    ExportParam,
    ExportRequest,
    GetTypesResult,
    GraphQLQueryResult,
    ListTypesResult,
)


def tools() -> list[Callable[..., Any]]:
    """List of available Platform tools."""
    return [
        platform_graphql_info,
        platform_graphql_list_types,
        platform_graphql_get_types,
        platform_graphql_query,
        platform_dataset_info,
        platform_dataset_export,
        platform_dataset_lookup,
    ]


def platform_graphql_info() -> ToolsetInfo:
    """
    Essential guide for Stacklet Platform GraphQL API - read this first before using other tools.

    The Platform API provides access to all Stacklet governance features: policies, account groups,
    bindings, resources, executions, and more. This guide explains the GraphQL schema patterns,
    connection-based pagination, filtering, and best practices for effective queries.

    ⚠️  Always check this guide first - it contains critical information about schema introspection,
    filtering syntax, and performance considerations for large-scale governance data.
    """
    return info_tool_result(get_file_text("platform/graphql_info.md"))


@json_guard
async def platform_graphql_list_types(
    ctx: Context,
    match: Annotated[
        str | None,
        Field(None, description="Optional regular expression to filter GraphQL types by name"),
    ] = None,
) -> ListTypesResult:
    """
    Discover available GraphQL types in the Stacklet Platform API.

    Use this to explore the schema and find the right types for your queries.
    Essential for understanding what data is available and how types relate to each other.

    Without a filter, returns all available types. With a regex filter, narrows down
    to matching type names (e.g., "Account.*" finds AccountGroup, AccountList, etc.).

    Next step: Use platform_graphql_get_types() to see detailed definitions for interesting types.
    """
    client = PlatformClient.get(ctx)
    return await client.list_types(match)


@json_guard
async def platform_graphql_get_types(
    ctx: Context,
    type_names: Annotated[
        list[str],
        Field(
            min_length=1, description="List of GraphQL type names to retrieve SDL definitions for"
        ),
    ],
) -> GetTypesResult:
    """
    Get detailed GraphQL type definitions to understand schema structure.

    Returns the full GraphQL Schema Definition Language (SDL) for specified types,
    showing all fields, arguments, relationships, and documentation. Essential for
    building correct queries.

    Use this after platform_graphql_list_types() to understand:
    - What fields are available on each type
    - Required vs optional arguments
    - Relationships between types
    - Input types for mutations

    The SDL output shows exactly how to structure your GraphQL queries.
    """
    client = PlatformClient.get(ctx)
    return await client.get_types(type_names)


@json_guard
async def platform_graphql_query(
    ctx: Context,
    query: Annotated[
        str,
        Field(
            min_length=1,
            description="GraphQL query string to execute against the Stacklet Platform API",
        ),
    ],
    variables: Annotated[
        dict[str, Any] | None, Field(None, description="Variables to pass to the GraphQL query")
    ] = None,
) -> GraphQLQueryResult:
    """
    Execute GraphQL queries against the Stacklet Platform for governance operations.

    This is your main tool for querying policies, account groups, bindings, resources,
    executions, and all other governance data. Supports both queries and mutations.

    ⚠️  Important guidelines:
    - Always query for "problems" field alongside your data
    - Use small page sizes (5-10) for exploration, larger for known datasets
    - Check types with platform_graphql_get_types() first
    - For large exports, use platform_dataset_export() instead
    """
    client = PlatformClient.get(ctx)
    return await client.query(query, variables or {})


def platform_dataset_info() -> ToolsetInfo:
    """
    Guide for exporting large datasets from Stacklet Platform - use for big data analysis.

    When you need to export thousands of governance records (policies, resources, executions,
    etc.), the dataset export tools provide server-side CSV generation that's much more
    efficient than paging through GraphQL connections.

    This guide explains how to structure export requests, handle large datasets, and
    work with the async export process. Essential for data analysis workflows.
    """
    return info_tool_result(get_file_text("platform/dataset_info.md"))


@json_guard
async def platform_dataset_export(
    ctx: Context,
    connection_field: Annotated[
        str,
        Field(min_length=1, description="Name of the GraphQL connection field to export data from"),
    ],
    columns: Annotated[
        list[ExportColumn],
        Field(min_length=1, description="List of columns to include in the exported CSV file"),
    ],
    node_id: Annotated[
        str, Field(min_length=1, description="Starting node ID to begin the export from (optional)")
    ]
    | None = None,
    params: Annotated[
        list[ExportParam] | None,
        Field(
            None,
            description="Parameters to pass to the connection field for filtering or customization",
        ),
    ] = None,
    timeout: Annotated[
        int,
        Field(
            ge=0,
            le=600,
            default=0,
            description="Maximum time to wait for export completion in seconds "
            "(0 = return immediately with dataset_id)",
        ),
    ] = 0,
) -> ConnectionExport:
    """
    Export large governance datasets to CSV for analysis and reporting.

    Perfect for exporting thousands of resources, policies, executions, or other governance
    data when GraphQL pagination would be too slow. The server handles all paging and
    generates a downloadable CSV file.

    Process:
    1. Define columns mapping GraphQL fields to CSV columns
    2. Optionally add filters via params
    3. Export runs asynchronously - use timeout=0 to return immediately
    4. Use platform_dataset_lookup() to check progress and get download URL
    """
    dataset_input = ExportRequest(
        connection_field=connection_field,
        columns=columns,
        node_id=node_id,
        params=params,
    )

    client = PlatformClient.get(ctx)
    dataset_id = await client.start_export(dataset_input)
    return await client.wait_for_export(dataset_id, timeout)


@json_guard
async def platform_dataset_lookup(
    ctx: Context,
    dataset_id: Annotated[
        str,
        Field(min_length=1, description="Dataset export ID returned from platform_dataset_export"),
    ],
    timeout: Annotated[
        int,
        Field(
            ge=0,
            le=600,
            default=0,
            description="Maximum time to wait for export completion in seconds "
            "(0 = return current status immediately)",
        ),
    ] = 0,
) -> ConnectionExport:
    """
    Monitor dataset export progress and retrieve download links.

    Use this to check on exports started with platform_dataset_export(). Returns current
    status, progress info, and download URL when complete.

    Export states:
    - Processing: Export is running (shows progress if available)
    - Complete: Ready for download (includes download_url and expiry time)
    - Failed: Export encountered an error

    Set timeout > 0 to wait for completion, or timeout=0 for immediate status check.
    Download URLs are temporary and expire after a few hours.
    """
    client = PlatformClient.get(ctx)
    return await client.wait_for_export(dataset_id, timeout)
