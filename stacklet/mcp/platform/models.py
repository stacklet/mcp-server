import json

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


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

    export_id: str = Field(..., validation_alias="id", description="Export job node ID")
    started: datetime | None = Field(None, description="When processing started")
    processed_rows: int | None = Field(
        None, validation_alias="processed", description="Number of rows exported so far"
    )
    completed: datetime | None = Field(None, description="When processing finished")
    success: bool | None = Field(None, description="Set when completed")
    message: str | None = Field(None, description="Set when completed")
    download_url: str | None = Field(
        None, validation_alias="downloadURL", description="Export download URL"
    )
    available_until: datetime | None = Field(
        None, validation_alias="availableUntil", description="When download URL expires"
    )
