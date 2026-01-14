# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import json
import sys

from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from ..settings import Settings


class Profile(StrEnum):
    DEFAULT = "default"
    UNRESTRICTED = "unrestricted"


# profiles for mcp.json env variables
MCP_SETTINGS_PROFILES = {
    Profile.DEFAULT: Settings(
        assetdb_allow_archive=False,
        assetdb_allow_save=False,
        platform_allow_mutations=False,
    ),
    Profile.UNRESTRICTED: Settings(
        assetdb_allow_archive=True,
        assetdb_allow_save=True,
        platform_allow_mutations=True,
    ),
}


class MCPServerConfig(BaseModel):
    """The .mcp.json file content."""

    command: str
    args: tuple[str, ...] | None = None
    env: dict[str, str] | None = None

    def file_content(self) -> dict[str, Any]:
        """Content of the mcp.json file."""
        config = self.model_dump(exclude_none=True)
        return {
            "mcpServers": {
                "stacklet": config,
            }
        }


def mcp_config(profile: Profile) -> str:
    """Return the MCP server for the MCP server for a profile."""
    command, args = _get_command()
    env = _get_profile_env(profile)
    config = MCPServerConfig(command=command, args=args, env=env)

    return json.dumps(config.file_content(), indent=2)


def _get_command() -> tuple[str, tuple[str, ...] | None]:
    script = sys.argv[0]
    if script.endswith("__main__.py"):
        command = sys.executable
        args = ("-m", "stacklet.mcp")
    else:
        command = script
        args = None

    return command, args


def _get_profile_env(profile: Profile) -> dict[str, str] | None:
    settings = MCP_SETTINGS_PROFILES[profile]
    env_prefix = Settings.model_config["env_prefix"]
    env = {
        (env_prefix + name).upper(): str(value)
        for name, value in settings.model_dump(exclude_defaults=True).items()
    }
    return env or None
