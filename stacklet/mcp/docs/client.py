# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
Client for accessing Stacklet documentation.
"""

from typing import Self
from urllib.parse import urljoin, urlparse

import httpx

from fastmcp import Context

from ..lifespan import server_singleton
from ..request_credentials import current_credentials
from ..upstream_errors import check_response
from ..utils.http import PerCallClient
from .models import DocContent, DocFile


# Cap the redirect chain so a misconfigured docs service can't loop us.
_MAX_REDIRECTS = 5


class DocsClient(PerCallClient):
    """Client to fetch documentation files.

    Auth is NOT held on the instance — each HTTP call reads per-request
    credentials via `current_credentials(ctx)` and passes the identity-token
    cookie per-call. The shared-transport/per-call-AsyncClient pattern lives
    on `PerCallClient`.

    There is no server-wide docs index cache: the previous `_index` field was
    populated by an authenticated request, which would make one caller's view
    of the index visible to every caller in a multi-user deployment. The
    index is fetched per `get_index` call; if latency becomes painful, cache
    keyed on the identity token with a short TTL.

    Redirects are followed only when the target host matches the configured
    docs host. Cross-host redirects are rejected: silently following them
    would forward the identity-token cookie off-host. This allows harmless
    same-host canonicalization (e.g. `/guide` → `/guide/`) while keeping the
    cookie scope tight.
    """

    @classmethod
    def get(cls, ctx: Context) -> Self:
        return server_singleton(ctx, "DOCS_CLIENT", cls)

    def docs_url(self, ctx: Context) -> str:
        """Return the docs service URL for the current request."""
        return current_credentials(ctx).service_endpoint("docs")

    async def get_index(self, ctx: Context) -> list[DocFile]:
        """Fetch the documents index. Always hits upstream — the previous
        server-wide cache leaked per-user results across callers."""
        url = urljoin(self.docs_url(ctx), "index.json")
        response = await self._get(ctx, url)
        check_response(response)
        return [DocFile(**entry) for entry in response.json()]

    async def get_doc_file(self, ctx: Context, resource: str) -> DocContent:
        """Fetch a documentation file.

        Args:
            ctx: FastMCP request context.
            resource: resource path

        Returns:
            The document content
        """
        known_docs = {doc.path for doc in await self.get_index(ctx)}
        if resource not in known_docs:
            raise ValueError("Resource is not a known document file")

        url = urljoin(self.docs_url(ctx), resource)
        response = await self._get(ctx, url)
        check_response(response)
        return DocContent(
            path=resource,
            content=response.content.decode(),
        )

    async def _get(self, ctx: Context, url: str) -> httpx.Response:
        creds = current_credentials(ctx)
        # Compare (scheme, hostname, port) against the original URL on every
        # hop. Same hostname alone is not enough — an `https → http`
        # downgrade would forward the identity-token cookie on the wire in
        # plaintext, and a port hop could land it on a co-tenanted service
        # behind the same DNS name.
        origin = urlparse(url)
        origin_key = (origin.scheme, origin.hostname, origin.port)
        cookies = {"stacklet-auth": creds.identity_token}

        async with self._async_client() as session:
            current_url = url
            for _ in range(_MAX_REDIRECTS):
                response = await session.get(
                    current_url,
                    cookies=cookies,
                    follow_redirects=False,
                )
                if not (300 <= response.status_code < 400):
                    return response

                location = response.headers.get("location")
                if not location:
                    return response  # let caller surface the broken redirect

                target = urljoin(str(response.url), location)
                target_parsed = urlparse(target)
                target_key = (target_parsed.scheme, target_parsed.hostname, target_parsed.port)
                if target_key != origin_key:
                    raise RuntimeError(
                        f"Docs service returned a cross-host redirect to "
                        f"{target!r}; refusing to forward identity-token "
                        f"cookie off the configured docs origin "
                        f"{origin.scheme}://{origin.hostname}"
                        f"{':' + str(origin.port) if origin.port else ''}."
                    )
                current_url = target
            raise RuntimeError(f"Docs service exceeded {_MAX_REDIRECTS} redirects for {url}")
