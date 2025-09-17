from typing import Annotated, Any, Callable

from fastmcp import Context
from pydantic import Field

from ..utils import get_package_file, json_guard
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
        platform_dataset_export,
        platform_dataset_lookup,
        platform_dataset_info,
    ]


def platform_graphql_info() -> str:
    """
    Key information for LLMs using the platform_graphql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the toolset.
    """
    return get_package_file("platform/graphql_info.md").read_text()


@json_guard
async def platform_graphql_list_types(ctx: Context, match: str | None = None) -> ListTypesResult:
    """
    List the types available in the Stacklet Platform GraphQL API.

    Args:
        match: Optional regular expression filter

    Returns:
        Structured response with context
    """
    client = PlatformClient.get(ctx)
    return await client.list_types(match)


@json_guard
async def platform_graphql_get_types(ctx: Context, type_names: list[str]) -> GetTypesResult:
    """
    Retrieve information about types in the Stacklet Platform GraphQL API.

    Args:
        type_names: Names of requested types.

    Returns:
        JSON string mapping valid type names to GraphQL SDL definitions.
    """
    client = PlatformClient.get(ctx)
    return await client.get_types(type_names)


@json_guard
async def platform_graphql_query(
    ctx: Context, query: str, variables: dict[str, Any] | None = None
) -> GraphQLQueryResult:
    """
    Execute a GraphQL query against the Stacklet API.

    Only call this tool when you understand the principles outlined in the
    platform_graphql_info tool. Always remember to check input and output
    types before you use them.

    Args:
        query: The GraphQL query string
        variables: Variables dict for the query

    Returns:
        Structured GraphQL query result with context
    """
    client = PlatformClient.get(ctx)
    return await client.query(query, variables or {})


@json_guard
async def platform_dataset_export(
    ctx: Context,
    connection_field: Annotated[str, Field(min_length=1)],
    columns: Annotated[list[ExportColumn], Field(min_length=1)],
    node_id: Annotated[str, Field(min_length=1)] | None = None,
    params: list[ExportParam] | None = None,
    timeout: Annotated[int, Field(ge=0, le=600, default=0)] = 0,
) -> ConnectionExport:
    """
    Export a full dataset from a Stacklet Platform GraphQL Connection field into CSV
    format.

    This tool initiates a server-side export that pages through all data accessible
    via a Connection node, generates a CSV file, and makes it available for download.

    By default, this tool returns immediately, with a `dataset_id` that can be used
    with the `platform_dataset_lookup` tool to check progress and eventually get a
    download URL. When `timeout` is greater than 0, the tool will periodically check
    status and return only when the export completes or the timeout expires.
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
    dataset_id: str,
    timeout: Annotated[int, Field(ge=0, le=600, default=0)] = 0,
) -> ConnectionExport:
    """
    Check the status of a `platform_dataset_export`.

    By default, this tool returns immediately. When `timeout` is greater than 0, the
    tool will periodically check status and return only when the export completes or
    the timeout expires.
    """
    client = PlatformClient.get(ctx)
    return await client.wait_for_export(dataset_id, timeout)


def platform_dataset_info() -> str:
    """
    Key information for LLMs using the platform_dataset_ tools; call this first.

    Returns:
        Comprehensive guide to using platform dataset export functionality.
    """
    return get_package_file("platform/dataset_info.md").read_text()
