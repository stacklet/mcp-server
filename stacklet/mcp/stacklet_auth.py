# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import json
import os

from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse, urlunparse


def service_endpoint(endpoint: str, service: str) -> str:
    """Return the URL for a Stacklet service (e.g. "redash", "docs").

    Derives the service URL by replacing the ``api.`` prefix of the host with
    ``{service}.``. Substring-replace on the whole URL is unsafe — hosts like
    ``foo-api.example.com`` would match spuriously and silently produce the
    wrong service URL.

    Raises ValueError if the endpoint has no host or the host does not start
    with ``api.`` (so local dev hosts or path-based endpoints fail loudly
    instead of silently pointing at the wrong service).
    """
    parsed = urlparse(endpoint)
    host = parsed.hostname
    if not host:
        raise ValueError(f"Invalid endpoint (no host): {endpoint!r}")
    if not host.startswith("api."):
        raise ValueError(
            f"Endpoint host must start with 'api.' to derive service URLs; got {host!r}"
        )
    # urlunparse with a new netloc would silently drop userinfo. Stacklet
    # URLs don't carry user:pass@, but refuse to drop any caller's
    # credentials rather than silently losing them.
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"Endpoint must not contain userinfo: {endpoint!r}")
    new_host = service + host[len("api") :]
    new_netloc = new_host
    if parsed.port is not None:
        new_netloc = f"{new_host}:{parsed.port}"
    rebuilt = urlunparse(parsed._replace(netloc=new_netloc))
    if not rebuilt.endswith("/"):
        rebuilt += "/"
    return rebuilt


class StackletCredentials(NamedTuple):
    """Stacklet authentication credentials."""

    endpoint: str
    access_token: str
    identity_token: str

    def service_endpoint(self, service: str) -> str:
        """Return the URL for a Stacklet service (e.g. "redash", "docs")."""
        return service_endpoint(self.endpoint, service)


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
