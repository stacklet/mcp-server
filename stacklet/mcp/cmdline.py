# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliPositionalArg,
    CliSubCommand,
    get_subcommand,
)

from .middleware import DEFAULT_MAX_BYTES
from .server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_GRACEFUL_SHUTDOWN,
    HttpTransportOptions,
    make_server,
    run_streamable_http,
)
from .utils.mcp_json import MCP_SETTINGS_PROFILES, Profile, mcp_config


class AgentConfigListCommand(BaseModel):
    """List available config profiles"""

    def cli_cmd(self) -> None:
        print("Available profiles:")
        for name in sorted(MCP_SETTINGS_PROFILES):
            print(f" - {name}")


class AgentConfigGenerateCommand(BaseModel):
    """Output configuration for a profile"""

    profile: CliPositionalArg[Profile] = Field(description="profile name")

    def cli_cmd(self) -> None:
        print(mcp_config(self.profile))


class AgentConfigCommand(BaseModel):
    """Manage .json.mcp file content"""

    list: CliSubCommand[AgentConfigListCommand]
    generate: CliSubCommand[AgentConfigGenerateCommand]

    def cli_cmd(self) -> None:
        sub_command: AgentConfigListCommand | AgentConfigGenerateCommand = get_subcommand(
            self,
            is_required=True,
        )  # type: ignore[assignment]
        sub_command.cli_cmd()


class RunCommand(BaseModel):
    """Run the MCP server"""

    transport: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        description="Transport protocol to use. 'stdio' (default) runs a local subprocess; "
        "'streamable-http' runs a network server for multi-user hosting.",
    )
    host: str = Field(
        default=DEFAULT_HOST,
        description="Bind address for streamable-http transport.",
    )
    port: int = Field(
        default=DEFAULT_PORT,
        description="Listen port for streamable-http transport.",
    )
    forwarded_allow_ips: str | None = Field(
        default=None,
        description=(
            "Trusted sources for uvicorn's ProxyHeadersMiddleware, as a "
            "comma-separated list of IPs or CIDRs (e.g. '10.0.0.0/8') or '*' "
            "when behind a trusted ALB. Defaults to uvicorn's own default "
            "(127.0.0.1 only). Required for 'request.client.host' to reflect "
            "the real caller behind an ALB."
        ),
    )
    timeout_graceful_shutdown: int = Field(
        default=DEFAULT_TIMEOUT_GRACEFUL_SHUTDOWN,
        ge=0,
        description=(
            "Seconds uvicorn waits for in-flight requests to drain on SIGTERM. "
            "Must exceed the AssetDB 300s poll ceiling plus a small grace so "
            "ECS task replacement doesn't kill long-running queries."
        ),
    )
    max_bytes: int = Field(
        default=DEFAULT_MAX_BYTES,
        gt=0,
        description="Maximum request body size in bytes for streamable-http.",
    )

    def cli_cmd(self) -> None:
        if self.transport == "streamable-http":
            run_streamable_http(
                HttpTransportOptions(
                    host=self.host,
                    port=self.port,
                    forwarded_allow_ips=self.forwarded_allow_ips,
                    timeout_graceful_shutdown=self.timeout_graceful_shutdown,
                    max_bytes=self.max_bytes,
                )
            )
            return

        mcp = make_server()
        mcp.run(show_banner=False)


class CLIArguments(
    BaseSettings, cli_parse_args=True, cli_kebab_case=True, cli_use_class_docs_for_groups=True
):
    """Command line arguments."""

    agent_config: CliSubCommand[AgentConfigCommand]
    run: CliSubCommand[RunCommand]

    def cli_cmd(self) -> None:
        if not self.model_dump(exclude_none=True):
            # no option was provided, run by default
            RunCommand().cli_cmd()
        else:
            CliApp.run_subcommand(self)
