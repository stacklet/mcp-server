import copy

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExportFormat(StrEnum):
    """Format for query result export."""

    CSV = "csv"
    JSON = "json"
    TSV = "tsv"
    XLSX = "xlsx"


class JobStatus(IntEnum):
    """Status values for AssetDB query execution jobs."""

    QUEUED = 1
    STARTED = 2
    FINISHED = 3
    FAILED = 4
    CANCELED = 5
    DEFERRED = 6
    SCHEDULED = 7

    @property
    def is_terminal(self) -> bool:
        """Whether this job status represents a completed state (finished, failed, or canceled)."""
        return self in (JobStatus.FINISHED, JobStatus.FAILED, JobStatus.CANCELED)


class Job(BaseModel):
    """Redash job object for async query execution."""

    id: str
    status: JobStatus
    error: str | None
    query_result_id: int | None


class QueryArchiveResult(BaseModel):
    """Result of archiving/deleting a query."""

    success: bool
    message: str
    query_id: int


class User(BaseModel):
    """Redash user object model."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="Unique user ID in the Redash system")
    name: str | None = Field(None, description="User's display name")
    email: str | None = Field(None, description="User's email address")


class Query(BaseModel):
    """Redash query object model based on serialize_query output."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="Unique query ID in the Redash system")
    latest_query_data_id: int | None = Field(
        None, description="ID of the most recent query result data"
    )
    name: str = Field(..., description="Query display name")
    description: str | None = Field(None, description="Query description or documentation")
    query: str = Field(..., description="SQL query text")
    api_key: str = Field(..., description="API key for accessing this query")
    is_draft: bool = Field(..., description="Whether the query is in draft status")
    updated_at: datetime = Field(..., description="Timestamp of last modification")
    created_at: datetime = Field(..., description="Timestamp when query was created")
    data_source_id: int = Field(..., description="ID of the data source this query runs against")
    options: dict[str, Any] = Field(
        ..., description="Query configuration options including parameters"
    )
    tags: list[str] = Field(..., description="List of tags for categorizing the query")
    is_safe: bool = Field(..., description="Whether the query is considered safe to run")
    user: User = Field(..., description="User who created the query")
    last_modified_by: User | None = Field(None, description="User who last modified the query")
    retrieved_at: datetime | None = Field(
        None, description="Timestamp when query data was last retrieved"
    )
    runtime: float | None = Field(None, description="Last execution runtime in seconds")
    is_favorite: bool = Field(..., description="Whether the query is marked as favorite")

    @model_validator(mode="before")
    @classmethod
    def transform_user_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

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
    """Raw response model for query list endpoint (internal use)."""

    model_config = ConfigDict(extra="ignore")

    count: int = Field(..., description="Total number of queries matching the search criteria")
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Number of queries per page")
    results: list[Query] = Field(..., description="List of queries on the current page")


class QueryUpsert(BaseModel):
    """Query data for create/update operations."""

    name: str | None = Field(None, description="Query display name (required for new queries)")
    query: str | None = Field(None, description="SQL query text (required for new queries)")
    description: str | None = Field(None, description="Query description or documentation")
    tags: list[str] | None = Field(None, description="List of tags for categorizing the query")
    options: dict[str, Any] | None = Field(
        None, description="Query configuration options including parameters"
    )
    is_draft: bool | None = Field(None, description="Whether the query should be in draft status")

    def payload(self, data_source_id: int | None = None) -> dict[str, Any]:
        """
        Build API payload for query create/update.

        Args:
            data_source_id: Required data source ID for the query

        Returns:
            Payload dictionary with non-None values
        """
        payload = self.model_dump(exclude_none=True)
        if data_source_id:
            payload["data_source_id"] = data_source_id

        return payload


class ToolQueryListPagination(BaseModel):
    """Pagination metadata for query list responses."""

    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Number of queries per page")
    has_next_page: bool = Field(..., description="Whether there are more pages available")
    total_count: int = Field(
        ..., description="Total number of queries matching the search criteria"
    )


class ToolQueryListItem(BaseModel):
    """Simplified query information for list responses."""

    id: int = Field(..., description="Unique query ID")
    name: str = Field(..., description="Query display name")
    description: str | None = Field(..., description="Query description or documentation")
    has_parameters: bool = Field(..., description="Whether the query accepts parameters")
    data_source_id: int = Field(..., description="ID of the data source this query runs against")
    is_draft: bool = Field(..., description="Whether the query is in draft status")
    is_favorite: bool = Field(..., description="Whether the query is marked as favorite")
    tags: list[str] = Field(..., description="List of tags for categorizing the query")
    user: User = Field(..., description="User who created the query")


class ToolQueryList(BaseModel):
    """Complete response for query list operations."""

    queries: list[ToolQueryListItem] = Field(..., description="List of queries on the current page")
    pagination: ToolQueryListPagination = Field(..., description="Pagination information")


class QueryResultColumn(BaseModel):
    """Column definition in a query result."""

    name: str = Field(..., description="Column name")
    type: str | None = Field(None, description="Column data type")
    friendly_name: str | None = Field(None, description="Human-friendly column name")

    model_config = ConfigDict(extra="ignore")


class QueryResultData(BaseModel):
    """The data structure within a query result containing columns and rows."""

    columns: list[QueryResultColumn] = Field(
        ..., description="Column definitions for the query result"
    )
    rows: list[dict[str, Any]] = Field(
        ..., description="Query result rows as key-value dictionaries"
    )

    model_config = ConfigDict(extra="ignore")


class QueryResult(BaseModel):
    """Query result object as returned by Redash QueryResult.to_dict()."""

    id: int = Field(..., description="Query result ID")
    query: str = Field(..., description="The SQL query text that was executed")
    data: QueryResultData = Field(..., description="Query result data with columns and rows")
    data_source_id: int = Field(..., description="ID of the data source used")
    runtime: float = Field(..., description="Query execution time in seconds")
    retrieved_at: datetime = Field(..., description="When the query result was retrieved")

    model_config = ConfigDict(extra="ignore")


class ToolQueryResultArtifact(BaseModel):
    """Query download details for a data format."""

    format: ExportFormat = Field(..., description="Export format for the query result download")
    download_from: str = Field(..., description="URL to download the data in the specified format")


class ToolQueryResult(BaseModel):
    """
    Truncated query results suitable for LLMs, along with ways to get the full
    result set for analysis with tools suited to that task.
    """

    result_id: int = Field(..., description="Query result id")
    query_id: int | None = Field(None, description="Query id, if applicable")

    # These fields come directly from the redash QueryResult.
    query_text: str = Field(..., description="The SQL query text that was executed")
    query_runtime: float = Field(..., description="Query execution duration in seconds")
    query_timestamp: datetime = Field(..., description="Query execution finish timestamp")
    columns: list[QueryResultColumn] = Field(
        ..., description="Column definitions; sparse row dicts are keyed on column name"
    )

    # These fields are derived from the QueryResult rows.
    row_count: int = Field(..., description="Total rows in the full query result")
    some_rows: list[dict[str, Any]] = Field(
        ..., description="Sample of up to 20 rows from the query result for preview"
    )

    # Complete result data is always saved locally for further analysis. (We don't *have*
    # to do this on every path, but we do on *some*, so we choose consistency.)
    full_results_saved_to: str = Field(
        ..., description="Local path where complete result data was saved as JSON"
    )

    # Available only for saved queries (not ad-hoc queries) that have API keys.
    alternate_formats: list[ToolQueryResultArtifact] | None = Field(
        None, description="Download URLs for different formats, None for ad-hoc queries"
    )
