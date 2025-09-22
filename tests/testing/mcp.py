# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

import json

from functools import cached_property

import pytest

from fastmcp.client.client import CallToolResult


class ToolCallResult:
    """Result returned by a tool call."""

    def __init__(self, result: CallToolResult):
        self.result = result

    @cached_property
    def is_error(self):
        return self.result.isError

    @cached_property
    def text(self):
        [content] = self.result.content
        return content.text

    def json(self):
        return json.loads(self.text)


def json_guard_parametrize(values):
    """
    Parametrizes with `value` (taken from `values`), and `mangle` which is either
    `json.dumps` or the identity function, to enable us to test that we treat both
    `value` and `mangle(value)` exactly the same.

    Wish we didn't have to, see json_guard.
    """
    mangle = pytest.mark.parametrize("mangle", [json.dumps, lambda x: x])
    value = pytest.mark.parametrize("value", values)
    return lambda fn: mangle(value(fn))


class MCPTest:
    """Base test class for MCP tools."""

    tool_name: str

    @pytest.fixture(autouse=True)
    def setup_client(self, mcp_client):
        self.client = mcp_client

    async def assert_call(self, params, error=False) -> ToolCallResult:
        call_result = await self.client.call_tool_mcp(self.tool_name, params)
        result = ToolCallResult(call_result)
        assert result.is_error == error
        return result


class MCPCookieTest(MCPTest):
    """MCP test class for tools that use cookie-based authentication."""

    @pytest.fixture(autouse=True)
    def setup_http(self, mock_http_cookie):
        self.http = mock_http_cookie


class MCPBearerTest(MCPTest):
    """MCP test class for tools that use bearer token authentication."""

    @pytest.fixture(autouse=True)
    def setup_http(self, mock_http_bearer):
        self.http = mock_http_bearer
