from datetime import datetime
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class ListTypesResult(BaseModel):
    searched_for: str | None
    found_types: list[str]


class GetTypesResult(BaseModel):
    asked_for: list[str]
    found_sdl: dict[str, str]
    not_found: list[str]


class GraphQLError(BaseModel):
    message: str
    locations: list[dict[str, int]] | None = None
    path: list[str | int] | None = None
    extensions: dict[str, Any] | None = None


class GraphQLQueryResult(BaseModel):
    query: str
    variables: dict[str, Any]
    data: dict[str, Any] | None = None
    errors: list[GraphQLError] | None = None

    @model_validator(mode="after")
    def validate_graphql_structure(self) -> Self:
        """Ensure this looks like a valid GraphQL response with either data or errors."""
        if not (self.data or self.errors):
            raise ValueError("GraphQL response must contain either 'data' or 'errors' field")
        return self


# Export-related models


class ExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "CSV"


class ExportColumn(BaseModel):
    """Defines an output column to be generated in an export."""

    name: str = Field(
        ..., min_length=1, description="Name of a column in the generated export file"
    )
    path: str = Field(
        ...,
        min_length=1,
        description="Path to the field for this column, relative to the 'node' field",
    )
    subpath: str | None = Field(
        None, description="Optional jmespath to the data within the JSON-encoded field"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate column name doesn't contain problematic characters."""
        if "\n" in v or "\r" in v:
            raise ValueError("Column name cannot contain newline characters")
        return v


class ExportParam(BaseModel):
    """Defines a parameter for a query field in an export."""

    name: str = Field(..., min_length=1, description="Name of the connection parameter")
    type: str = Field(..., min_length=1, description="Exact GraphQL type of the parameter")
    value_json: str = Field(
        ..., min_length=1, alias="valueJSON", description="JSON-encoded value of the parameter"
    )

    @field_validator("value_json")
    @classmethod
    def validate_json_format(cls, v: str) -> str:
        """Validate that value_json is valid JSON."""
        import json

        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"value_json must be valid JSON: {e}")
        return v


class ExportConnectionInput(BaseModel):
    """Input for requesting a connection export."""

    connection_field: str = Field(
        ..., min_length=1, description="Name of the connection field to export"
    )
    columns: list[ExportColumn] = Field(
        ..., min_length=1, description="At least one column to include"
    )
    node_id: str | None = Field(None, description="Optional starting node ID")
    params: list[ExportParam] | None = Field(None, description="Optional connection parameters")
    filename: str | None = Field(None, description="Optional custom filename")
    format: ExportFormat = Field(default=ExportFormat.CSV, description="Export format")
    timeout: int = Field(
        default=300, ge=5, le=600, description="Timeout in seconds for export completion"
    )
    download_path: str | None = Field(
        None, description="Optional local path to save downloaded file"
    )

    @field_validator("columns")
    @classmethod
    def validate_unique_column_names(cls, v: list[ExportColumn]) -> list[ExportColumn]:
        """Ensure column names are unique."""
        names = [col.name for col in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(f"Duplicate column names found: {duplicates}")
        return v

    @field_validator("params")
    @classmethod
    def validate_unique_param_names(cls, v: list[ExportParam] | None) -> list[ExportParam] | None:
        """Ensure parameter names are unique."""
        if v is None:
            return v
        names = [param.name for param in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(f"Duplicate parameter names found: {duplicates}")
        return v

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str | None) -> str | None:
        """Validate filename doesn't contain problematic characters."""
        if v is None:
            return v
        if "/" in v or ":" in v:
            raise ValueError("Filename cannot contain '/' or ':' characters")
        if len(v.encode("utf-8")) > 980:
            raise ValueError("Filename (with extension) cannot exceed 980 UTF-8 bytes")
        return v


class ConnectionExportStatus(BaseModel):
    """Status information for a connection export."""

    id: str = Field(..., description="Export ID")
    started: datetime | None = Field(None, description="When export task was started")
    completed: datetime | None = Field(None, description="When export task finished")
    success: bool | None = Field(None, description="Final status of the export attempt")
    processed: int | None = Field(None, description="Count of rows processed")
    download_url: str | None = Field(
        None, alias="downloadURL", description="Where to download the exported dataset"
    )
    available_until: datetime | None = Field(
        None, alias="availableUntil", description="When download URL expires"
    )
    message: str | None = Field(None, description="Status message, especially for failures")

    @property
    def is_complete(self) -> bool:
        """Check if the export is complete."""
        return self.completed is not None

    @property
    def is_successful(self) -> bool:
        """Check if the export completed successfully."""
        return self.success is True and self.download_url is not None


class ExportResult(BaseModel):
    """Result of a completed dataset export."""

    downloaded: bool = Field(default=True, description="Whether file was successfully downloaded")
    file_path: str = Field(..., description="Local path to downloaded file")
    format: str = Field(default="csv", description="Format of the exported file")
    export_id: str = Field(..., description="Platform export job ID")
    processed_rows: int | None = Field(None, description="Number of rows in the export")
    available_until: datetime | None = Field(None, description="When download URL expires")

    @field_validator("file_path")
    @classmethod
    def validate_file_exists(cls, v: str) -> str:
        """Validate that the file path exists."""
        from pathlib import Path

        if not Path(v).exists():
            raise ValueError(f"Downloaded file does not exist: {v}")
        return v
