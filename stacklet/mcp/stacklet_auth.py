#!/usr/bin/env python3

import json
import os

from pathlib import Path
from typing import NamedTuple, Optional


class StackletCredentials(NamedTuple):
    """Stacklet authentication credentials."""

    endpoint: str
    access_token: str


def get_stacklet_dir() -> Optional[Path]:
    """
    Get the Stacklet configuration directory (~/.stacklet).

    Returns:
        Path to the .stacklet directory, or None if home directory cannot be determined
    """
    try:
        home_dir = Path.home()
        return home_dir / ".stacklet"
    except (OSError, RuntimeError):
        # Handle cases where home directory can't be determined
        return None


def load_stacklet_auth(
    endpoint: Optional[str] = None, access_token: Optional[str] = None
) -> Optional[StackletCredentials]:
    """
    Load Stacklet authentication credentials using the same priority order
    as the Stacklet Terraform provider:

    1. Direct configuration (parameters)
    2. Environment variables (STACKLET_ENDPOINT, STACKLET_ACCESS_TOKEN)
    3. CLI configuration files (~/.stacklet/config.json, ~/.stacklet/credentials)

    Args:
        endpoint: Optional direct endpoint configuration
        access_token: Optional direct access token configuration

    Returns:
        StackletCredentials if both endpoint and access_token are found, None otherwise
    """
    creds_endpoint = endpoint
    creds_access_token = access_token

    # Lookup environment variables if not provided directly
    if not creds_endpoint:
        creds_endpoint = os.getenv("STACKLET_ENDPOINT")
    if not creds_access_token:
        creds_access_token = os.getenv("STACKLET_ACCESS_TOKEN")

    # Lookup CLI configuration files
    stacklet_dir = get_stacklet_dir()
    if stacklet_dir:
        # Load endpoint from config.json if still needed
        if not creds_endpoint:
            config_file = stacklet_dir / "config.json"
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config = json.load(f)
                        creds_endpoint = config.get("api")
                except (json.JSONDecodeError, KeyError, IOError):
                    pass

        # Load access token from credentials file if still needed
        if not creds_access_token:
            creds_file = stacklet_dir / "credentials"
            if creds_file.exists():
                try:
                    creds_access_token = creds_file.read_text().strip()
                except IOError:
                    pass

    # Return credentials only if both are available
    if creds_endpoint and creds_access_token:
        return StackletCredentials(endpoint=creds_endpoint, access_token=creds_access_token)

    return None
