from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliPositionalArg,
    CliSubCommand,
)

from .server import make_server
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
        CliApp.run_subcommand(self)


class RunCommand(BaseModel):
    """Run the MCP server"""

    def cli_cmd(self) -> None:
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
