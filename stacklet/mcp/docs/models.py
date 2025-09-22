# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

from pydantic import BaseModel, Field


class DocFile(BaseModel):
    """A documentation file."""

    path: str = Field(..., description="Relative path to the documentation file")
    title: str = Field(..., description="Human-readable title of the documentation file")


class DocsList(BaseModel):
    """Available documentation files."""

    base_url: str = Field(..., description="Base URL of the Stacklet documentation service")
    available_document_files: list[DocFile] = Field(
        ..., description="List of all available documentation files"
    )
    note: str = Field(..., description="Usage note about how to read these files")
    recommended_start: str = Field(
        default="index_llms.md", description="Recommended starting documentation file for LLMs"
    )


class DocContent(BaseModel):
    """Content for a document."""

    path: str = Field(..., description="Relative path of the documentation file")
    content: str = Field(..., description="Full markdown content of the documentation file")
