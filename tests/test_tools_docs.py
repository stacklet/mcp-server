"""
Tests for docs-related MCP tools.
"""

import json

from .conftest import ExpectRequest
from .mcp_test import MCPTest


class TestDocsList(MCPTest):
    tool_name = "docs_list"

    async def test_list(self):
        """Document listing returns the list of available documents."""
        docs = [
            {"path": "foo.md", "title": "How to foo"},
            {"path": "bar.md", "title": "How to bar"},
        ]

        with self.http.expect(
            ExpectRequest(
                url="https://docs.example.com/index.json",
                response=json.dumps(docs),
            ),
        ):
            result = await self.assert_call({})

        assert hasattr(result, "content")
        assert len(result.content) == 1
        content = json.loads(result.content[0].text)
        assert content == {
            "available_document_files": docs,
            "note": "Use docs_read with any of these file paths to read the content",
            "recommended_start": "index_llms.md",
        }


class TestDocsRead(MCPTest):
    tool_name = "docs_read"

    async def test_read(self):
        """Reading a document returns its content."""
        path = "some/file.md"
        doc_text = "This is a sample doc"

        with self.http.expect(
            ExpectRequest(
                url="https://docs.example.com/some/file.md",
                response=doc_text,
            ),
        ):
            result = await self.assert_call({"file_path": path})

        assert hasattr(result, "content")
        assert len(result.content) == 1
        content = json.loads(result.content[0].text)
        assert content == {
            "path": path,
            "content": doc_text,
        }
