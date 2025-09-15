from typing import Any

from pydantic import BaseModel


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
