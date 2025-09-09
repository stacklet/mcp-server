#!/usr/bin/env python3

import json
import os

from pathlib import Path
from typing import NamedTuple, Optional


class StackletCredentials(NamedTuple):
    """Stacklet authentication credentials."""

    endpoint: str
    access_token: str


def get_stacklet_dir() -> Path:
    """
    Get the Stacklet configuration directory (~/.stacklet).

    Returns:
        Path to the .stacklet directory

    Raises:
        OSError, RuntimeError: If home directory cannot be determined
    """
    home_dir = Path.home()
    return home_dir / ".stacklet"


def load_stacklet_auth(
    endpoint: Optional[str] = None, access_token: Optional[str] = None
) -> StackletCredentials:
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
        StackletCredentials with both endpoint and access_token

    Raises:
        ValueError: If credentials cannot be found or loaded
        OSError, RuntimeError: If home directory cannot be determined
        json.JSONDecodeError: If config.json is malformed
        IOError: If credential files cannot be read
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

    # Load endpoint from config.json if still needed
    if not creds_endpoint:
        config_file = stacklet_dir / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
                creds_endpoint = config.get("api")

    # Load access token from credentials file if still needed
    if not creds_access_token:
        creds_file = stacklet_dir / "credentials"
        if creds_file.exists():
            creds_access_token = creds_file.read_text().strip()

    # Return credentials only if both are available
    if creds_endpoint and creds_access_token:
        return StackletCredentials(endpoint=creds_endpoint, access_token=creds_access_token)

    # If we get here, credentials are missing
    missing = []
    if not creds_endpoint:
        missing.append("endpoint")
    if not creds_access_token:
        missing.append("access_token")

    raise ValueError(
        f"Missing Stacklet credentials: {', '.join(missing)}. "
        f"Set STACKLET_ENDPOINT/STACKLET_ACCESS_TOKEN environment variables "
        f"or configure ~/.stacklet/config.json and ~/.stacklet/credentials files."
    )
