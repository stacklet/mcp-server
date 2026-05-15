# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2026 Stacklet, Inc.
#

"""Tests for PlatformClient lazy-schema loading and drift alarm."""

import asyncio
import logging

import pytest

from graphql import build_schema

from stacklet.mcp.platform.graphql import PlatformClient


SCHEMA_A = "type Query { foo: String }"
SCHEMA_B = "type Query { foo: String, bar: Int }"


class FakeSession:
    """Minimal stand-in for an httpx.AsyncClient.post response."""

    def __init__(self, introspection_payload: dict) -> None:
        self.payload = introspection_payload
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def post(self, url, json, headers):
        self.calls += 1
        return FakeResponse(self.payload)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def _introspection_payload(schema_sdl: str) -> dict:
    """Build an introspection-query-shaped payload from SDL."""
    from graphql import get_introspection_query, graphql_sync

    schema = build_schema(schema_sdl)
    result = graphql_sync(schema, get_introspection_query())
    assert result.data is not None, result.errors
    return {"data": result.data}


def _probe_payload(type_names: list[str]) -> dict:
    return {"data": {"__schema": {"types": [{"name": n} for n in type_names]}}}


class _FakeClient:
    """Serves sequential introspection or drift-probe responses."""

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.calls = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def post(self, url, json, headers):
        self.calls += 1
        if not self._payloads:
            raise AssertionError("no more canned payloads")
        return FakeResponse(self._payloads.pop(0))


@pytest.fixture
def ctx_stub(monkeypatch):
    """Stub current_credentials so PlatformClient doesn't need a real context."""
    from stacklet.mcp.stacklet_auth import StackletCredentials

    creds = StackletCredentials(
        endpoint="https://api.example.com",
        access_token="at",
        identity_token="it",
    )
    monkeypatch.setattr("stacklet.mcp.platform.graphql.current_credentials", lambda ctx: creds)
    return object()  # opaque stand-in for Context


class TestSchemaLazyLoad:
    async def test_concurrent_cold_start_introspects_once(self, ctx_stub, monkeypatch):
        """Two coroutines racing a cold cache must share one introspection."""
        payload = _introspection_payload(SCHEMA_A)
        fake = _FakeClient([payload])
        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        # Fire two concurrent get_schema calls.
        r1, r2 = await asyncio.gather(
            client.get_schema(ctx_stub),
            client.get_schema(ctx_stub),
        )
        assert r1 is r2  # both return the same cached schema instance
        assert fake.calls == 1  # only one introspection RPC

    async def test_warm_cache_does_not_introspect(self, ctx_stub, monkeypatch):
        payload = _introspection_payload(SCHEMA_A)
        fake = _FakeClient([payload])
        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        await client.get_schema(ctx_stub)
        assert fake.calls == 1

        # Suppress drift probes so a second get_schema() hits the pure fast
        # path. SCHEMA_DRIFT_INTERVAL_SECONDS=inf = never probe again.
        monkeypatch.setattr(client, "SCHEMA_DRIFT_INTERVAL_SECONDS", float("inf"))
        await client.get_schema(ctx_stub)
        assert fake.calls == 1  # still one — second call was the cache


class TestDriftAlarm:
    async def test_fires_when_types_change(self, ctx_stub, monkeypatch, caplog):
        """After cache is warm and interval elapses, a probe with a different
        type set emits a warn-level schema_drift_detected log."""
        introspection = _introspection_payload(SCHEMA_A)
        # After warm cache, the probe query returns a different type list.
        drift_probe = _probe_payload(["Query", "String", "Int", "NewType"])
        fake = _FakeClient([introspection, drift_probe])

        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        # Warm the cache.
        await client.get_schema(ctx_stub)

        # Force the interval boundary.
        monkeypatch.setattr(client, "SCHEMA_DRIFT_INTERVAL_SECONDS", 0)

        with caplog.at_level(logging.WARNING, logger="stacklet.mcp.platform.graphql"):
            await client.get_schema(ctx_stub)

        assert fake.calls == 2  # introspection + probe
        assert any("schema_drift_detected" in rec.message for rec in caplog.records)

    async def test_no_log_when_types_match(self, ctx_stub, monkeypatch, caplog):
        """No drift log if the live type set matches the cached digest."""
        introspection = _introspection_payload(SCHEMA_A)
        schema = build_schema(SCHEMA_A)
        # Probe returns the same type set as the cached schema.
        drift_probe = _probe_payload(sorted(schema.type_map.keys()))
        fake = _FakeClient([introspection, drift_probe])

        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        await client.get_schema(ctx_stub)
        monkeypatch.setattr(client, "SCHEMA_DRIFT_INTERVAL_SECONDS", 0)

        with caplog.at_level(logging.WARNING, logger="stacklet.mcp.platform.graphql"):
            await client.get_schema(ctx_stub)

        assert not any("schema_drift_detected" in rec.message for rec in caplog.records)

    async def test_probe_failure_does_not_break_request(self, ctx_stub, monkeypatch, caplog):
        """A failing drift probe emits a warn-level log but the request still
        succeeds."""
        introspection = _introspection_payload(SCHEMA_A)
        # Probe will fail.
        failing_probe = {"errors": [{"message": "upstream down"}]}
        fake = _FakeClient([introspection, failing_probe])

        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        await client.get_schema(ctx_stub)
        monkeypatch.setattr(client, "SCHEMA_DRIFT_INTERVAL_SECONDS", 0)

        with caplog.at_level(logging.WARNING, logger="stacklet.mcp.platform.graphql"):
            schema = await client.get_schema(ctx_stub)

        assert schema is not None
        assert any("schema_drift_probe_failed" in rec.message for rec in caplog.records)

    async def test_auth_error_on_probe_logged_at_debug_not_warning(
        self, ctx_stub, monkeypatch, caplog
    ):
        """A 401/403 from the drift probe is almost always an expired user
        session, not real drift. It must NOT show up as a warn-level
        `schema_drift_probe_failed` — that noise would drown out real
        drift signals in operator dashboards.
        """
        import httpx

        introspection = _introspection_payload(SCHEMA_A)
        fake = _FakeClient([introspection])

        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)
        await client.get_schema(ctx_stub)
        monkeypatch.setattr(client, "SCHEMA_DRIFT_INTERVAL_SECONDS", 0)

        # Second get_schema call triggers the drift probe. Make the probe
        # fail with an auth-shaped HTTP error.
        async def raise_401(self):
            request = httpx.Request("POST", "https://api.example.com/")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("mocked 401", request=request, response=response)

        from stacklet.mcp.upstream_errors import map_http_status_error

        async def probe_401(ctx):
            request = httpx.Request("POST", "https://api.example.com/")
            response = httpx.Response(401, request=request)
            err = httpx.HTTPStatusError("mocked 401", request=request, response=response)
            raise map_http_status_error(err)

        monkeypatch.setattr(client, "_probe_schema_digest", probe_401)

        with caplog.at_level(logging.DEBUG, logger="stacklet.mcp.platform.graphql"):
            await client.get_schema(ctx_stub)

        warn_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert not any("schema_drift_probe_failed" in r.message for r in warn_records), (
            "auth failures in the probe must not surface as drift-probe warnings"
        )

    async def test_failed_probe_does_not_claim_interval_slot(self, ctx_stub, monkeypatch, caplog):
        """A transient probe failure (e.g. upstream 503) must not silence
        drift detection for a full interval. The next request should retry.
        """
        introspection = _introspection_payload(SCHEMA_A)
        # First probe fails, second probe succeeds with a drift.
        failing_probe = {"errors": [{"message": "upstream down"}]}
        drift_probe = _probe_payload(["Query", "NewType"])
        fake = _FakeClient([introspection, failing_probe, drift_probe])

        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        await client.get_schema(ctx_stub)
        monkeypatch.setattr(client, "SCHEMA_DRIFT_INTERVAL_SECONDS", 0)

        # First attempt: probe fails, timestamp rewound.
        await client.get_schema(ctx_stub)
        # Second attempt: probe runs again (slot not claimed), sees drift.
        with caplog.at_level(logging.WARNING, logger="stacklet.mcp.platform.graphql"):
            await client.get_schema(ctx_stub)

        assert fake.calls == 3  # introspection + failed probe + retried probe
        assert any("schema_drift_detected" in rec.message for rec in caplog.records)

    async def test_interval_gating(self, ctx_stub, monkeypatch):
        """Within the interval, no drift probe runs."""
        introspection = _introspection_payload(SCHEMA_A)
        fake = _FakeClient([introspection])

        client = PlatformClient()
        monkeypatch.setattr(client, "_async_client", fake)

        await client.get_schema(ctx_stub)
        # Second call inside the interval window — no probe should run.
        await client.get_schema(ctx_stub)
        await client.get_schema(ctx_stub)
        assert fake.calls == 1  # still just the cold-start introspection
