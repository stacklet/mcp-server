import json

import pytest

from fastmcp.client.client import CallToolResult, Client

from stacklet.mcp.mcp import mcp


@pytest.fixture
async def mcp_client(mock_stacklet_credentials):
    async with Client(mcp) as client:
        yield client


def json_guard_param(arg, value):
    "parametrize arg with value and JSON-encoded value, see json_guard"
    return pytest.mark.parametrize(arg, [value, json.dumps(value)])


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
