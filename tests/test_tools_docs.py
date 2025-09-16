"""
Tests for docs-related MCP tools.
"""

import json

from .testing.http import ExpectRequest
from .testing.mcp import MCPTest


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

        assert result.json() == {
            "base_url": "https://docs.example.com/",
            "available_document_files": docs,
            "note": "Use docs_read with any of these file paths to read the content",
            "recommended_start": "index_llms.md",
        }

    async def test_cached(self):
        """Document listing is cached across requests.."""
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
            result1 = await self.assert_call({})
            result2 = await self.assert_call({})
        assert result1.json() == result2.json()


class TestDocsRead(MCPTest):
    tool_name = "docs_read"

    async def test_read_doc(self):
        """Reading a document returns its content."""
        path = "some/file.md"
        doc_text = "This is a sample doc"

        index = [{"path": path, "title": "Sample doc"}]

        with self.http.expect(
            ExpectRequest(
                url="https://docs.example.com/index.json",
                response=json.dumps(index),
            ),
            ExpectRequest(
                url="https://docs.example.com/some/file.md",
                response=doc_text,
            ),
        ):
            result = await self.assert_call({"file_path": path})

        assert result.json() == {
            "path": path,
            "content": doc_text,
        }

    async def test_read_other_file(self):
        """Trying to read a document with an unknown file returns an error."""
        index = [{"path": "some/file.md", "title": "Sample doc"}]

        with self.http.expect(
            ExpectRequest(
                url="https://docs.example.com/index.json",
                response=json.dumps(index),
            ),
        ):
            result = await self.assert_call({"file_path": "some_other_file.md"}, error=True)

        assert (
            result.text == "Error calling tool 'docs_read': Resource is not a known document file"
        )
