# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

import json

import pytest

from stacklet.mcp.utils.mcp_json import Profile, mcp_config


class TestMCPConfig:
    def get_config(self, profile=Profile.DEFAULT):
        config = json.loads(mcp_config(profile))
        return config["mcpServers"]["stacklet"]

    @pytest.mark.parametrize(
        "profile,env",
        [
            (Profile.DEFAULT, None),
            (
                Profile.UNRESTRICTED,
                {
                    "STACKLET_MCP_ASSETDB_ALLOW_ARCHIVE": "True",
                    "STACKLET_MCP_ASSETDB_ALLOW_SAVE": "True",
                    "STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS": "True",
                },
            ),
        ],
    )
    def test_config_env(self, profile, env):
        config = self.get_config(profile)
        assert config.get("env") == env

    def test_config_command_via_module(self, monkeypatch):
        python_executable = "/path/to/python3"
        monkeypatch.setattr("sys.executable", python_executable)
        monkeypatch.setattr("sys.argv", ["stacklet/mcp/__main__.py"])
        config = self.get_config()
        assert config["command"] == python_executable
        assert config["args"] == ["-m", "stacklet.mcp"]

    def test_config_command_via_script(self, monkeypatch):
        executable = "/path/to/stacklet-mcp"
        monkeypatch.setattr("sys.argv", [executable])
        config = self.get_config()
        assert config["command"] == executable
        assert "args" not in config
