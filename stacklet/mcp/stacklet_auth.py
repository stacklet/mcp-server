#!/usr/bin/env python3

import json
import os

from pathlib import Path
from typing import NamedTuple, Self, cast

from fastmcp import Context

from .lifespan import server_cached


class StackletCredentials(NamedTuple):
    """Stacklet authentication credentials."""

    endpoint: str
    access_token: str
    identity_token: str

    @classmethod
    def get(cls, ctx: Context) -> Self:
        return cast(Self, server_cached(ctx, "STACKLET_CREDS", load_stacklet_auth))

    def service_endpoint(self, service: str) -> str:
        """Return the endpoint for a service."""
        endpoint = self.endpoint.replace("api.", f"{service}.", 1)
        if not endpoint.endswith("/"):
            endpoint += "/"
        return endpoint


def get_stacklet_dir() -> Path:
    """
    Get the Stacklet configuration directory (~/.stacklet).

    Returns:
        Path to the .stacklet directory
    """
    return Path.home() / ".stacklet"


def load_stacklet_auth() -> StackletCredentials:
    """
    Load Stacklet authentication credentials from:

    1. Environment variables (STACKLET_ENDPOINT, STACKLET_ACCESS_TOKEN, STACKLET_IDENTITY_TOKEN)
    2. CLI configuration files (~/.stacklet/config.json, ~/.stacklet/credentials, ~/.stacklet/id)

    Returns:
        StackletCredentials with endpoint, access_token, and identity_token
    """
    # Lookup environment variables first
    creds_endpoint = os.getenv("STACKLET_ENDPOINT")
    creds_access_token = os.getenv("STACKLET_ACCESS_TOKEN")
    creds_identity_token = os.getenv("STACKLET_IDENTITY_TOKEN")

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

    # Load identity token from id file if still needed
    if not creds_identity_token:
        id_file = stacklet_dir / "id"
        if id_file.exists():
            creds_identity_token = id_file.read_text().strip()

    # Return credentials only if all are available
    if creds_endpoint and creds_access_token and creds_identity_token:
        return StackletCredentials(
            endpoint=creds_endpoint,
            access_token=creds_access_token,
            identity_token=creds_identity_token,
        )

    # If we get here, credentials are missing
    missing = []
    if not creds_endpoint:
        missing.append("endpoint")
    if not creds_access_token:
        missing.append("access_token")
    if not creds_identity_token:
        missing.append("identity_token")

    raise ValueError(
        f"Missing Stacklet credentials: {', '.join(missing)}. "
        "Run `stacklet-admin login`, or set via environment STACKLET_ENDPOINT, "
        "STACKLET_ACCESS_TOKEN, STACKLET_IDENTITY_TOKEN."
    )
