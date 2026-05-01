# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Shared per-call HTTP client base.

Credentials must never live on a client instance — they're per-request, not
per-process. Each Stacklet HTTP client keeps a long-lived `AsyncHTTPTransport`
for connection-pool reuse, but constructs a fresh `httpx.AsyncClient` per
call so its cookie jar and default-header state start empty. Any `Set-Cookie`
from upstream stays isolated to a single request rather than leaking across
callers.
"""

import httpx

from .. import USER_AGENT


class PerCallClient:
    """Base providing a shared transport + fresh-per-call `AsyncClient`.

    Subclasses override `TIMEOUT_SECONDS` if they need a non-default timeout.
    Use `async with self._async_client() as session:` and pass auth per-call
    via `headers=` / `cookies=` kwargs — never on the session defaults.
    """

    TIMEOUT_SECONDS: float = 30.0

    def __init__(self) -> None:
        self._transport = httpx.AsyncHTTPTransport(retries=0)

    def _async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self._transport,
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
        )
