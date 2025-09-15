from pydantic import BaseModel


class DocFile(BaseModel):
    """A documentation file."""

    path: str
    title: str


class DocsList(BaseModel):
    """Available documentation files."""

    available_document_files: list[DocFile]
    note: str
    recommended_start: str = "index_llms.md"


class DocContent(BaseModel):
    """Content for a document."""

    path: str
    content: str
