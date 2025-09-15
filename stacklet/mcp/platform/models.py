from typing import Any, Self

from pydantic import BaseModel, model_validator


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
