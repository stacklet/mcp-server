from typing import Any, Callable

from fastmcp import Context

from ..utils import get_package_file, json_guard
from .graphql import PlatformClient


def tools() -> list[Callable[..., Any]]:
    """List of available Platform tools."""
    return [
        platform_graphql_info,
        platform_graphql_list_types,
        platform_graphql_get_types,
        platform_graphql_query,
    ]


def platform_graphql_info() -> str:
    """
    Key information for LLMs using the platform_graphql_ tools; call this first.

    Returns:
        Text to guide correct and effective use of the toolset.
    """
    return get_package_file("platform/graphql_info.md").read_text()


@json_guard
async def platform_graphql_list_types(ctx: Context, match: str | None = None) -> list[str]:
    """
    List the types available in the Stacklet Platform GraphQL API.

    Args:
        match: Optional regular expression filter

    Returns:
        List of type names
    """
    client = PlatformClient.get(ctx)
    return await client.list_types(match)


@json_guard
async def platform_graphql_get_types(ctx: Context, type_names: list[str]) -> dict[str, str]:
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
) -> dict[str, Any]:
    """
    Execute a GraphQL query against the Stacklet API.

    Only call this tool when you understand the principles outlined in the
    platform_graphql_info tool. Always remember to check input and output
    types before you use them.

    Args:
        query: The GraphQL query string
        variables: Variables dict for the query

    Returns:
        Complete GraphQL query result
    """
    client = PlatformClient.get(ctx)
    return await client.query(query, variables or {})
