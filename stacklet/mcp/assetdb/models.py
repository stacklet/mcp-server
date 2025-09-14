import copy

from datetime import datetime
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class JobStatus(IntEnum):
    QUEUED = 1
    STARTED = 2
    FINISHED = 3
    FAILED = 4
    CANCELED = 5
    DEFERRED = 6
    SCHEDULED = 7


class User(BaseModel):
    """Redash user object model."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str | None = None
    email: str | None = None


class Query(BaseModel):
    """Redash query object model based on serialize_query output."""

    model_config = ConfigDict(extra="ignore")

    id: int
    latest_query_data_id: int | None
    name: str
    description: str | None
    query: str
    api_key: str
    is_archived: bool
    is_draft: bool
    updated_at: datetime
    created_at: datetime
    data_source_id: int
    options: dict[str, Any]
    tags: list[str]
    is_safe: bool
    user: User
    last_modified_by: User | None = None
    retrieved_at: datetime | None = None
    runtime: float | None = None
    is_favorite: bool

    @model_validator(mode="before")
    @classmethod
    def transform_user_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Deep copy to avoid any mutation issues
            data = copy.deepcopy(data)

            # Handle user field - convert user_id to User object if needed
            if "user_id" in data and "user" not in data:
                data["user"] = {"id": data["user_id"]}

            # Handle last_modified_by - convert last_modified_by_id to User object if needed
            if "last_modified_by_id" in data and "last_modified_by" not in data:
                if data["last_modified_by_id"] is not None:
                    data["last_modified_by"] = {"id": data["last_modified_by_id"]}
                else:
                    data["last_modified_by"] = None

        return data


class QueryListResponse(BaseModel):
    """Response model for query list endpoint."""

    model_config = ConfigDict(extra="ignore")

    count: int
    page: int
    page_size: int
    results: list[Query]


class QueryUpsert(BaseModel):
    """Query data for create/update operations."""

    name: str | None = None
    query: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    options: dict[str, Any] | None = None
    is_draft: bool | None = None

    def payload(self, data_source_id: int | None = None) -> dict[str, Any]:
        """
        Build API payload for query create/update.

        Args:
            data_source_id: Required data source ID for the query

        Returns:
            Payload dictionary with non-None values
        """
        payload: dict[str, Any] = {}

        if self.name is not None:
            payload["name"] = self.name
        if self.query is not None:
            payload["query"] = self.query
        if self.description is not None:
            # NOTE that None _is_ a valid description, but since "" is
            # functionally equivalent there's no need to complicate with
            # NotSet/EMPTY-style handling.
            payload["description"] = self.description
        if self.tags is not None:
            payload["tags"] = self.tags
        if self.options is not None:
            payload["options"] = self.options
        if self.is_draft is not None:
            payload["is_draft"] = self.is_draft

        if data_source_id:
            payload["data_source_id"] = data_source_id

        return payload
