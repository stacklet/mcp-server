# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Map upstream HTTP errors to user-facing tool errors.

Every HTTP error that reaches a tool handler should pass through this module
so the MCP client sees a helpful message instead of `HTTP 401` or a raw
upstream body. Tokens are aggressively stripped from any body we pass
through to guard against a future upstream that echoes request headers into
error payloads.
"""

import re

import httpx

from .utils.error import AnnotatedError


MSG_SESSION_EXPIRED = (
    "Your Stacklet session has expired. Run `stacklet-admin login` and "
    "regenerate your MCP client config."
)
MSG_FORBIDDEN = "You don't have access to this resource."
MSG_UPSTREAM_UNAVAILABLE = (
    "Stacklet upstream is unavailable. Retry in a moment; contact support if it persists."
)


_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+", re.IGNORECASE)
_COOKIE_RE = re.compile(r"stacklet-auth=\S+", re.IGNORECASE)


def sanitize_error_body(text: str) -> str:
    """Strip Bearer tokens and identity-token cookie values from `text`.

    Defense-in-depth: today upstream never echoes request headers into
    error bodies, but if that ever changes this keeps us from surfacing
    tokens to the MCP client.
    """
    text = _BEARER_RE.sub("Bearer [redacted]", text)
    text = _COOKIE_RE.sub("stacklet-auth=[redacted]", text)
    return text


def map_http_status_error(err: httpx.HTTPStatusError) -> AnnotatedError:
    """Translate an httpx HTTPStatusError into a user-facing AnnotatedError.

    Status classes:
      - 401 → session-expired guidance
      - 403 → generic access-denied
      - 5xx → "upstream unavailable, retry" with no body passthrough
      - other 4xx → pass the sanitized upstream body through, since it may
        contain useful validation detail.
    """
    status = err.response.status_code
    if status == 401:
        return AnnotatedError(
            problem="Unauthorized",
            likely_cause="the caller's Stacklet session has expired or was never valid",
            next_steps=MSG_SESSION_EXPIRED,
        )
    if status == 403:
        return AnnotatedError(
            problem="Forbidden",
            likely_cause="the caller does not have access to this resource",
            next_steps=MSG_FORBIDDEN,
        )
    if 500 <= status < 600:
        return AnnotatedError(
            problem=f"Upstream {status}",
            likely_cause="a downstream Stacklet service is unavailable",
            next_steps=MSG_UPSTREAM_UNAVAILABLE,
        )
    # Other 4xx: pass through a sanitized upstream body.
    body = sanitize_error_body(err.response.text)
    return AnnotatedError(
        problem=f"Upstream HTTP {status}",
        likely_cause="the upstream service rejected the request",
        next_steps=body,
        original_error=str(err),
    )


def check_response(response: httpx.Response) -> None:
    """Like `response.raise_for_status()`, but raises an AnnotatedError."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as err:
        raise map_http_status_error(err) from err
