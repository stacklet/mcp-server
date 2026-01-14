# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import sys

from pydantic import ValidationError
from pydantic_settings import (
    CliApp,
    SettingsError,
)

from .cmdline import CLIArguments


def main() -> None:
    """Main entry point for the MCP server."""
    try:
        CliApp.run(CLIArguments)
    except (ValidationError, SettingsError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
