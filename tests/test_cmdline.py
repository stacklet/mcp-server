# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from textwrap import dedent
from unittest.mock import MagicMock

import pytest

from stacklet.mcp.cmdline import CLIArguments
from stacklet.mcp.utils.mcp_json import Profile, mcp_config


@pytest.fixture
def mock_server(monkeypatch):
    server = MagicMock()
    monkeypatch.setattr("stacklet.mcp.cmdline.make_server", lambda: server)
    yield server


@pytest.fixture
def run_cli(monkeypatch):
    def run(*args):
        monkeypatch.setattr("sys.argv", ["stacklet-mcp", *args])
        args = CLIArguments()
        args.cli_cmd()

    yield run


class TestCLIArguments:
    def test_default_run_when_no_args(self, mock_server, run_cli):
        run_cli()

        mock_server.run.assert_called_once_with(show_banner=False)

    def test_explicit_run_command(self, mock_server, run_cli):
        run_cli("run")

        mock_server.run.assert_called_once_with(show_banner=False)

    def test_agent_config_list(self, capsys, run_cli):
        run_cli("agent-config", "list")

        out, err = capsys.readouterr()
        assert out == dedent(
            """\
            Available profiles:
             - default
             - unrestricted
            """
        )
        assert err == ""

    @pytest.mark.parametrize("profile", Profile)
    def test_agent_config_generate(self, capsys, run_cli, profile):
        run_cli("agent-config", "generate", str(profile))
        out, err = capsys.readouterr()
        assert out == mcp_config(profile) + "\n"
        assert err == ""
