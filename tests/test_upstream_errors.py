# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Tests for upstream_errors: status-code mapping and body sanitization."""

import httpx
import pytest

from stacklet.mcp.upstream_errors import (
    MSG_FORBIDDEN,
    MSG_SESSION_EXPIRED,
    MSG_UPSTREAM_UNAVAILABLE,
    check_response,
    map_http_status_error,
    sanitize_error_body,
)
from stacklet.mcp.utils.error import AnnotatedError


def _status_error(status_code: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.example.com/")
    response = httpx.Response(status_code, content=body.encode(), request=request)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as err:
        return err
    raise AssertionError("expected HTTPStatusError")


class TestSanitize:
    def test_strips_bearer_tokens(self):
        assert "redacted" in sanitize_error_body("Authorization: Bearer abc-123.xyz_9")

    def test_strips_cookie_values(self):
        assert "redacted" in sanitize_error_body("Cookie: stacklet-auth=abcdef")

    def test_leaves_normal_text_alone(self):
        assert sanitize_error_body("invalid json at line 12") == "invalid json at line 12"


class TestMapStatus:
    def test_401_maps_to_session_expired(self):
        err = _status_error(401)
        mapped = map_http_status_error(err)
        assert isinstance(mapped, AnnotatedError)
        assert MSG_SESSION_EXPIRED in str(mapped)

    def test_403_maps_to_forbidden(self):
        mapped = map_http_status_error(_status_error(403))
        assert MSG_FORBIDDEN in str(mapped)

    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_5xx_maps_to_upstream_unavailable(self, status):
        mapped = map_http_status_error(_status_error(status))
        assert MSG_UPSTREAM_UNAVAILABLE in str(mapped)

    def test_other_4xx_passes_sanitized_body(self):
        err = _status_error(418, body="invalid Bearer abc123.xyz")
        mapped = map_http_status_error(err)
        text = str(mapped)
        # Body content is preserved...
        assert "invalid" in text
        # ...but tokens are redacted.
        assert "abc123.xyz" not in text
        assert "redacted" in text


class TestCheckResponse:
    def test_raises_on_4xx(self):
        request = httpx.Request("GET", "https://api.example.com/")
        response = httpx.Response(401, request=request)
        with pytest.raises(AnnotatedError):
            check_response(response)

    def test_noop_on_2xx(self):
        request = httpx.Request("GET", "https://api.example.com/")
        response = httpx.Response(200, request=request)
        check_response(response)  # must not raise
