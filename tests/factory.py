"""
Test data factories for creating mock AssetDB responses that match real Redash API format.
"""

from typing import Any


def redash_user(
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
    query: str = "SELECT * FROM resources LIMIT 10",
    description: str | None = None,
    data_source_id: int = 1,
    is_archived: bool = False,
    is_draft: bool = False,
    is_favorite: bool = False,
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
        user = redash_user()

    # Base dict matching redash.serializers.serialize_query()
    return {
        "id": id,
        "latest_query_data_id": 1234567,
        "name": name,
        "description": description,
        "query": query,
        "query_hash": "abc123",
        "schedule": {"interval": 7 * 24 * 3600},
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
        "user": user,
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


def redash_job_response(
    job_id: str,
    status: int,
    error: str = "",
    query_result_id: int | None = None,
    updated_at: int = 0,
) -> dict[str, Any]:
    """
    Generate Redash job response matching serialize_job output.

    Args:
        job_id: Job ID string
        status: Job status (1=QUEUED, 2=STARTED, 3=FINISHED, 4=FAILED/CANCELED)
        error: Error message for failed jobs
        query_result_id: Query result ID for successful jobs
        updated_at: Job started timestamp
    """
    return {
        "job": {
            "id": job_id,
            "updated_at": updated_at,
            "status": status,
            "error": error,
            "result": query_result_id,  # this matches redash, but we ignore it
            "query_result_id": query_result_id,
        }
    }


def redash_query_result_response(result_id: int) -> dict[str, Any]:
    return {
        "query_result": {
            "id": result_id,
            "query": "SELECT 1 AS col",
            "data": {
                "columns": [{"name": "col", "type": "int", "friendly_name": "Col"}],
                "rows": [{"col": i} for i in range(100)],  # yes, doesn't match query
            },
            "data_source_id": 1,
            "runtime": 0.1,
            "retrieved_at": "2024-01-01T00:00:00Z",
        },
    }
