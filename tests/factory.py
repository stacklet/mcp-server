"""
Test data factories for creating mock AssetDB responses that match real Redash API format.
"""

from typing import Any


def make_assetdb_user_dict(
    id: int = 1,
    name: str = "Test User",
    email: str = "test@example.com",
    profile_image_url: str = "https://example.com/avatar.jpg",
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a user dict matching Redash User.to_dict() format."""
    return {
        "id": id,
        "name": name,
        "email": email,
        "profile_image_url": profile_image_url,
        "groups": [1],
        "updated_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "disabled_at": None,
        "is_disabled": False,
        "active_at": "2024-01-01T00:00:00Z",
        "is_invitation_pending": False,
        "is_email_verified": True,
        **kwargs,
    }


def make_assetdb_query_dict(
    id: int = 123,
    name: str = "Test Query",
    description: str = "A sample query",
    query: str = "SELECT * FROM resources LIMIT 10",
    tags: list[str] | None = None,
    user_name: str = "Test User",
    user_email: str = "test@example.com",
    user_id: int = 1,
    is_archived: bool = False,
    is_draft: bool = False,
    data_source_id: int = 1,
    parameters: list[dict[str, Any]] | None = None,
    visualizations: list[dict[str, Any]] | None = None,
    include_visualizations: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a mock query dict for testing matching Redash serialize_query format.

    Args:
        id: Query ID
        name: Query display name
        description: Query description
        query: SQL query text
        tags: List of tags
        user_name: Name of query author
        user_email: Email of query author
        user_id: ID of query author
        is_archived: Whether query is archived
        is_draft: Whether query is a draft
        data_source_id: ID of data source
        parameters: List of query parameters
        visualizations: List of visualization configs (removed by query_get)
        include_visualizations: Whether to include visualizations in response
        **kwargs: Additional fields to include

    Returns:
        Dictionary representing a query dict matching Redash serialization
    """
    if tags is None:
        tags = []
    if parameters is None:
        parameters = []
    if visualizations is None:
        visualizations = []

    # Base dict matching redash.serializers.serialize_query()
    query_dict = {
        "id": id,
        "latest_query_data_id": None,
        "name": name,
        "description": description,
        "query": query,
        "query_hash": "abc123",
        "schedule": None,
        "api_key": "test-api-key",
        "is_archived": is_archived,
        "is_draft": is_draft,
        "updated_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "data_source_id": data_source_id,
        "options": {"parameters": parameters} if parameters else {},
        "version": 1,
        "tags": tags,
        "is_safe": True,
        "user": make_assetdb_user_dict(id=user_id, name=user_name, email=user_email),
        "last_modified_by": None,
        **kwargs,
    }

    # Include visualizations if requested (they get removed by assetdb_query_get)
    if include_visualizations:
        query_dict["visualizations"] = visualizations

    return query_dict


def make_assetdb_query_list_response(
    queries: list[dict[str, Any]], total_count: int | None = None
) -> dict[str, Any]:
    """
    Create a mock query list response.

    Args:
        queries: List of query dicts
        total_count: Total count (defaults to length of queries)

    Returns:
        Dictionary representing a query list API response
    """
    if total_count is None:
        total_count = len(queries)

    return {
        "results": queries,
        "count": total_count,
    }
