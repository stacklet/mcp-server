# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

from fastmcp import Context

from .lifespan import server_cached
from .stacklet_auth import StackletCredentials, load_stacklet_auth


class LocalAuthProvider:
    """Auth provider for local stdio-based MCP servers.

    Loads credentials from ~/.stacklet/ files or environment variables,
    cached in server state for the process lifetime.
    """

    def get_credentials(self, ctx: Context) -> StackletCredentials:
        return server_cached(ctx, "STACKLET_CREDS", load_stacklet_auth)
