"""
Client for accessing Stacklet documentation.
"""

from typing import Self, cast
from urllib.parse import urljoin

import httpx

from fastmcp import Context

from ..stacklet_auth import StackletCredentials
from .models import DocContent, DocFile


class DocsClient:
    """Client to fetch documentation files."""

    def __init__(self, credentials: StackletCredentials):
        """
        Initialize the docs client with Stacklet credentials.

        Args:
            credentials: StackletCredentials object containing endpoint and identity_token
        """

        self.credentials = credentials
        self.docs_url = self.credentials.service_endpoint("docs")
        self.session = httpx.AsyncClient(cookies={"stacklet-auth": credentials.identity_token})
        self._index: list[DocFile] = []

    @classmethod
    def get(cls, ctx: Context) -> Self:
        key = "DOCS_CLIENT"
        if not ctx.get_state(key):
            creds = StackletCredentials.get(ctx)
            ctx.set_state(key, cls(creds))
        return cast(Self, ctx.get_state(key))

    async def get_index(self) -> list[DocFile]:
        """Fetch documents index.

        Returns:
            List of available documents.
        """
        if not self._index:
            self._index = await self._get_index()
        return self._index

    async def get_doc_file(self, resource: str) -> DocContent:
        """Fetch a documentation file.

        Args:
            endpoint: resource path

        Returns:
            The document content
        """
        known_docs = {doc.path for doc in await self._get_index()}
        if resource not in known_docs:
            raise ValueError("Resource is not a known document file")

        url = urljoin(self.docs_url, resource)
        response = await self.session.get(url, follow_redirects=True)
        response.raise_for_status()
        return DocContent(
            path=resource,
            content=response.content.decode(),
        )

    async def _get_index(self) -> list[DocFile]:
        url = urljoin(self.docs_url, "index.json")
        response = await self.session.get(url, follow_redirects=True)
        response.raise_for_status()
        return [DocFile(**entry) for entry in response.json()]
