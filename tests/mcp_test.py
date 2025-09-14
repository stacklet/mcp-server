import json

import pytest

from fastmcp.client.client import CallToolResult, Client

from stacklet.mcp.mcp import mcp


@pytest.fixture
async def mcp_client(mock_stacklet_credentials):
    async with Client(mcp) as client:
        yield client


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
    tool_name: str

    @pytest.fixture(autouse=True)
    def setup(self, mcp_client, mock_assetdb_request):
        self.client = mcp_client
        self.http = mock_assetdb_request

    async def assert_call(self, params, error=False) -> CallToolResult:
        result = await self.client.call_tool_mcp(self.tool_name, params)
        assert result.isError == error
        return result
