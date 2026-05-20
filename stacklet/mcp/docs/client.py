# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
Client for accessing Stacklet documentation.
"""

from typing import Self, cast
from urllib.parse import urljoin

import httpx

from fastmcp import Context

from .. import USER_AGENT
from ..lifespan import ServerState, server_cached
from ..stacklet_auth import StackletCredentials
from .models import DocContent, DocFile


class DocsClient:
    """Client to fetch documentation files."""

    def __init__(self, credentials: StackletCredentials, server_state: ServerState):
        self.credentials = credentials
        self.server_state = server_state
        self.docs_url = self.credentials.service_endpoint("docs")
        self.session = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            cookies={"stacklet-auth": credentials.identity_token},
        )

    @classmethod
    def get(cls, ctx: Context) -> Self:
        def construct() -> DocsClient:
            state = ctx.request_context.lifespan_context  # type: ignore[union-attr]
            return cls(StackletCredentials.get(ctx), state)

        return cast(Self, server_cached(ctx, "DOCS_CLIENT", construct))

    async def get_index(self) -> list[DocFile]:
        """Fetch documents index, using the server-level cache."""
        return await self.server_state.ensure_cached_async("DOCS_INDEX", self._fetch_index)

    async def get_doc_file(self, resource: str) -> DocContent:
        """Fetch a documentation file.

        Args:
            endpoint: resource path

        Returns:
            The document content
        """
        known_docs = {doc.path for doc in await self.get_index()}
        if resource not in known_docs:
            raise ValueError("Resource is not a known document file")

        url = urljoin(self.docs_url, resource)
        response = await self.session.get(url, follow_redirects=True)
        response.raise_for_status()
        return DocContent(
            path=resource,
            content=response.content.decode(),
        )

    async def _fetch_index(self) -> list[DocFile]:
        url = urljoin(self.docs_url, "index.json")
        response = await self.session.get(url, follow_redirects=True)
        response.raise_for_status()
        return [DocFile(**entry) for entry in response.json()]
