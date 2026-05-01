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


@pytest.fixture
def mock_run_streamable_http(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("stacklet.mcp.cmdline.run_streamable_http", mock)
    return mock


class TestCLIArguments:
    def test_default_run_when_no_args(self, mock_server, run_cli):
        run_cli()

        mock_server.run.assert_called_once_with(show_banner=False)

    def test_explicit_run_command(self, mock_server, run_cli):
        run_cli("run")

        mock_server.run.assert_called_once_with(show_banner=False)

    def test_run_streamable_http(self, mock_run_streamable_http, run_cli):
        from stacklet.mcp.server import HttpTransportOptions

        run_cli(
            "run",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            "9090",
            "--forwarded-allow-ips",
            "10.0.0.0/8",
            "--timeout-graceful-shutdown",
            "400",
            "--max-bytes",
            "2097152",
        )

        mock_run_streamable_http.assert_called_once_with(
            HttpTransportOptions(
                host="127.0.0.1",
                port=9090,
                forwarded_allow_ips="10.0.0.0/8",
                timeout_graceful_shutdown=400,
                max_bytes=2097152,
            )
        )

    def test_rejects_zero_max_bytes(self, run_cli):
        with pytest.raises(Exception, match="max_bytes"):
            run_cli("run", "--transport", "streamable-http", "--max-bytes", "0")

    def test_rejects_negative_max_bytes(self, run_cli):
        with pytest.raises(Exception, match="max_bytes"):
            run_cli("run", "--transport", "streamable-http", "--max-bytes", "-1")

    def test_rejects_negative_timeout_graceful_shutdown(self, run_cli):
        with pytest.raises(Exception, match="timeout_graceful_shutdown"):
            run_cli("run", "--transport", "streamable-http", "--timeout-graceful-shutdown", "-5")

    def test_run_streamable_http_uses_defaults(self, mock_run_streamable_http, run_cli):
        from stacklet.mcp.server import HttpTransportOptions

        run_cli("run", "--transport", "streamable-http")

        mock_run_streamable_http.assert_called_once_with(HttpTransportOptions())

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
