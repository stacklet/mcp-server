from pathlib import Path

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
