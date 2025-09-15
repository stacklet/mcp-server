from typing import Annotated, Any, Callable

from fastmcp import Context
from pydantic import Field

from ..utils import get_package_file, json_guard
from .graphql import PlatformClient
from .models import (
    ExportColumn,
    ExportConnectionInput,
    ExportParam,
    ExportResult,
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
    connection_field: str,
    columns: list[ExportColumn],
    node_id: str | None = None,
    params: list[ExportParam] | None = None,
    filename: str | None = None,
    timeout: Annotated[int, Field(ge=5, le=600, default=300)] = 300,
    download_path: str | None = None,
) -> ExportResult:
    """
    Export a full dataset from a Stacklet Platform GraphQL connection to CSV format.

    This tool initiates a server-side export that pages through all data accessible
    via a Connection node, generates a CSV file, and makes it available for download.
    """
    # Create the export input with validation
    export_input = ExportConnectionInput(
        connection_field=connection_field,
        columns=columns,
        node_id=node_id,
        params=params,
        filename=filename,
        timeout=timeout,
        download_path=download_path,
    )

    client = PlatformClient.get(ctx)
    return await client.export_dataset(export_input)
