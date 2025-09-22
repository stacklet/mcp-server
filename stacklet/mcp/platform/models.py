# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

import json

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class ListTypesResult(BaseModel):
    """Result of listing GraphQL types in the Stacklet Platform API."""

    searched_for: str | None = Field(
        None, description="Regular expression filter used for type search (if any)"
    )
    found_types: list[str] = Field(
        ..., description="List of GraphQL type names matching the search criteria"
    )


class GetTypesResult(BaseModel):
    """Result of retrieving specific GraphQL type definitions."""

    asked_for: list[str] = Field(..., description="List of type names that were requested")
    found_sdl: dict[str, str] = Field(
        ..., description="Dictionary mapping found type names to their GraphQL SDL definitions"
    )
    not_found: list[str] = Field(
        ..., description="List of requested type names that were not found in the schema"
    )


class GraphQLError(BaseModel):
    """GraphQL error information from query execution."""

    message: str = Field(..., description="Error message describing what went wrong")
    locations: list[dict[str, int]] | None = Field(
        None, description="Source locations where the error occurred (line/column)"
    )
    path: list[str | int] | None = Field(
        None, description="Path to the field in the query that caused the error"
    )
    extensions: dict[str, Any] | None = Field(
        None, description="Additional error metadata and debugging information"
    )


class GraphQLQueryResult(BaseModel):
    """Result of executing a GraphQL query against the Stacklet Platform."""

    query: str = Field(..., description="The GraphQL query that was executed")
    variables: dict[str, Any] = Field(..., description="Variables that were passed to the query")
    data: dict[str, Any] | None = Field(
        None, description="Query result data (null if query failed)"
    )
    errors: list[GraphQLError] | None = Field(
        None, description="List of errors that occurred during query execution"
    )

    @model_validator(mode="after")
    def validate_graphql_structure(self) -> Self:
        """Ensure this looks like a valid GraphQL response with either data or errors."""
        if not (self.data or self.errors):
            raise ValueError("GraphQL response must contain either 'data' or 'errors' field")
        return self


# Export-related models


class ExportColumn(BaseModel):
    """Defines an output column to be generated in an export."""

    name: str = Field(
        ..., min_length=1, description="Name of a column in the generated export file"
    )
    path: str = Field(
        ...,
        min_length=1,
        description="Path to the value, relative to the 'node' in the connection",
    )
    subpath: str | None = Field(
        None, description="Optional jmespath to the data within a JSON-encoded field"
    )

    def for_graphql(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ExportParam(BaseModel):
    """Defines a parameter for a query field in an export."""

    name: str = Field(..., min_length=1, description="Name of the connection parameter")
    type: str = Field(..., min_length=1, description="Exact GraphQL type of the parameter")
    value: Any = Field(..., description="value of the parameter")

    def for_graphql(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload["valueJSON"] = json.dumps(payload.pop("value"))
        return payload


class ExportRequest(BaseModel):
    node_id: str | None = Field(None, description="Optional starting node ID")
    connection_field: str = Field(
        ..., min_length=1, description="Name of the connection field to export"
    )
    params: list[ExportParam] | None = Field(
        None, description="Optional parameters for the connection field, e.g. for filtering"
    )
    columns: list[ExportColumn] = Field(
        ..., min_length=1, description="At least one column to include"
    )

    def for_graphql(self) -> dict[str, Any]:
        input_ = {
            "field": self.connection_field,
            "columns": [c.for_graphql() for c in self.columns],
            "format": "CSV",  # only one that exists
        }
        if self.node_id:
            input_["node"] = self.node_id
        if self.params:
            input_["params"] = [p.for_graphql() for p in self.params]
        return input_


class ConnectionExport(BaseModel):
    """Result of a completed dataset export."""

    dataset_id: str = Field(..., validation_alias="id", description="Dataset export node ID")
    started: datetime | None = Field(None, description="When processing started")
    processed_rows: int | None = Field(
        None,
        validation_alias="processed",
        description="Number of rows processed and exported so far",
    )
    completed: datetime | None = Field(None, description="When processing finished")
    success: bool | None = Field(
        None, description="Whether the export completed successfully (set when completed)"
    )
    message: str | None = Field(None, description="Status message or error details.")
    download_url: str | None = Field(
        None, validation_alias="downloadURL", description="Export download URL"
    )
    available_until: datetime | None = Field(
        None, validation_alias="availableUntil", description="When download URL expires"
    )
