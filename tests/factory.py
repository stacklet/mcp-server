"""
Test data factories for creating mock AssetDB responses that match real Redash API format.
"""

from typing import Any


def make_assetdb_user_dict(
    id: int = 1,
    name: str = "Test User",
    email: str = "test@example.com",
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "email": email,
        # The model doesn't care about any of these, but they're here anyway.
        "profile_image_url": "https://example.com/avatar.jpg",
        "groups": [1],
        "updated_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "disabled_at": None,
        "is_disabled": False,
        "active_at": "2024-01-01T00:00:00Z",
        "is_invitation_pending": False,
        "is_email_verified": True,
    }


def redash_query(
    id: int = 123,
    name: str = "Test Query",
    description: str = "A sample query",
    query: str = "SELECT * FROM resources LIMIT 10",
    user_name: str = "Test User",
    user_email: str = "test@example.com",
    user_id: int = 1,
    is_archived: bool = False,
    is_draft: bool = False,
    is_favorite: bool = False,
    data_source_id: int = 1,
    tags: list[str] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    visualizations: list[dict[str, Any]] | None = None,
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if tags is None:
        tags = []
    if parameters is None:
        parameters = []
    if visualizations is None:
        visualizations = []
    if user is None:
        user = make_assetdb_user_dict()

    # Base dict matching redash.serializers.serialize_query()
    return {
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
        "is_favorite": is_favorite,
        "updated_at": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "data_source_id": data_source_id,
        "options": {"parameters": parameters} if parameters else {},
        "version": 1,
        "tags": tags,
        "visualizations": visualizations,
        "is_safe": True,
        "user": make_assetdb_user_dict(id=user_id, name=user_name, email=user_email),
        "last_modified_by_id": None,
    }


def redash_query_list(
    queries: list[dict[str, Any]],
    page_size_total: tuple[int, int, int] | None = None,
) -> dict[str, Any]:
    result_count = len(queries)
    page, page_size, total = 1, 25, result_count
    if page_size_total:
        page, page_size, total = page_size_total

    # Couple of sanity checks on general principles.
    assert page_size >= result_count
    assert total >= result_count
    return {
        "page": page,
        "page_size": page_size,
        "count": total,
        "results": queries,
    }
