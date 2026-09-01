# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
Tests for docs-related MCP tools.
"""

import json

import pytest

from stacklet.mcp.docs.tools import tools

from .testing.http import ExpectRequest
from .testing.mcp import MCPCookieTest


@pytest.mark.parametrize("name", ["docs_list", "docs_read"])
def test_tool_annotations(name: str):
    """Reading docs changes nothing, and hosts should be told so."""
    [tool] = [tool for tool in tools() if tool.name == name]
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is True


class TestDocsList(MCPCookieTest):
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


class TestDocsRead(MCPCookieTest):
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
        """An unknown path returns an error that tells the agent how to recover.

        A page can be missing because the caller guessed the path, or because
        this installation runs a documentation build older than the page. The
        agent cannot tell those apart, and in both cases the useful move is the
        same: list what is actually there, and report the gap.

        The message has to bound the claim as well as prompt it. Documentation
        coverage and deployed features are independent, and an agent given only
        the surviving pages will describe the product from them. An earlier
        version said to answer from what docs_list returns, and a live agent
        turned a missing page into "this deployment does post-deploy detection
        only", which is worse than the bare error it replaced.
        """
        index = [{"path": "some/file.md", "title": "Sample doc"}]

        with self.http.expect(
            ExpectRequest(
                url="https://docs.example.com/index.json",
                response=json.dumps(index),
            ),
        ):
            result = await self.assert_call({"file_path": "some_other_file.md"}, error=True)

        assert "some_other_file.md" in result.text
        assert "documentation index" in result.text
        assert "docs_list" in result.text
        assert "documentation does not cover the topic" in result.text
        # The agent must not read deployed features off documentation coverage.
        assert "not evidence that the deployment lacks the feature" in result.text
