from pathlib import Path
from typing import Any

from pydantic import BaseModel


class DocsList(BaseModel):
    """Available documentation files."""

    available_files: list[Path]
    note: str
    recommended_start: Path = Path("index_llms.md")


class DocContent(BaseModel):
    """Content for a document."""

    file_path: Path
    content: str


class QueryUpsert(BaseModel):
    """Query data for create/update operations."""

    name: str | None = None
    query: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    options: dict[str, Any] | None = None
    is_draft: bool | None = None

    def payload(self, data_source_id: int) -> dict[str, Any]:
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
            payload["description"] = self.description
        if self.tags is not None:
            payload["tags"] = [tag for tag in self.tags if tag]  # Filter empty tags
        if self.options is not None:
            payload["options"] = self.options
        if self.is_draft is not None:
            payload["is_draft"] = self.is_draft

        payload["data_source_id"] = data_source_id

        return payload
