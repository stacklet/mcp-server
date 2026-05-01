# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Tests for AssetDBClient._poll_job cancellation semantics.

`CancelledError` inherits from `BaseException` so it shouldn't be caught and
re-raised as a different type — that breaks cancellation contracts
(including `asyncio.TaskGroup` in Python 3.11+). `_poll_job` must let it
propagate so the outer task unwinds cleanly.
"""

import asyncio

import pytest

from stacklet.mcp.assetdb.models import Job, JobStatus
from stacklet.mcp.assetdb.redash import AssetDBClient


@pytest.fixture
def client():
    return AssetDBClient(data_source_id=1)


class TestPollCancellation:
    async def test_cancelled_error_propagates(self, client, monkeypatch):
        """CancelledError from _make_request must propagate as-is, not get
        wrapped in another exception type. If we wrapped it, callers that
        expect CancelledError for cancellation detection (TaskGroup, the
        MCP server itself) would break.
        """

        async def raise_cancelled(*args, **kwargs):
            raise asyncio.CancelledError()

        monkeypatch.setattr(client, "_make_request", raise_cancelled)

        with pytest.raises(asyncio.CancelledError):
            await client._poll_job(
                ctx=object(),
                job=Job(id="job-1", status=JobStatus.QUEUED, error=None, query_result_id=None),
                timeout=60,
            )

    async def test_cancelled_error_mid_loop_propagates(self, client, monkeypatch):
        """Even after a successful first poll, a later CancelledError must
        propagate — asyncio.sleep is a cancellation point.
        """
        calls = 0

        async def flaky(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {
                    "job": {
                        "id": "j",
                        "status": JobStatus.QUEUED,
                        "error": None,
                        "query_result_id": None,
                    }
                }
            raise asyncio.CancelledError()

        monkeypatch.setattr(client, "_make_request", flaky)

        async def no_sleep(*args, **kwargs):
            pass

        monkeypatch.setattr("stacklet.mcp.assetdb.redash.asyncio.sleep", no_sleep)

        with pytest.raises(asyncio.CancelledError):
            await client._poll_job(
                ctx=object(),
                job=Job(id="job-1", status=JobStatus.QUEUED, error=None, query_result_id=None),
                timeout=60,
            )
