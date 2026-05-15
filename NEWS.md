## Next Release

### Features

### Changes

### Fixes

---

## April 22, 2026

### Features

- **`streamable-http` transport**: `stacklet-mcp run --transport streamable-http` now starts
  a network server suitable for hosting the MCP broker centrally. Each incoming request must
  carry its own `Authorization: Bearer <access_token>` and `X-Stacklet-Identity-Token`
  headers; those credentials are forwarded untouched to Platform GraphQL and Redash so the
  upstream's existing per-user Postgres RLS applies. Default transport remains `stdio` for
  local users — zero regression.
- **`/health` endpoint**: accepts GET and HEAD, returns `{status, version, git_sha}`. Never
  touches upstream services so ALB target groups don't flap during upstream hiccups.
- **Upstream error mapping**: 401/403/5xx upstream responses are now translated into
  user-friendly tool errors with retry guidance (e.g. "Your Stacklet session has expired.
  Run `stacklet-admin login` …"). Tokens are sanitized out of any passed-through error body.

### Changes

- **Per-request credentials**: `PlatformClient`, `AssetDBClient`, and `DocsClient` no longer
  hold auth on their instances. Each HTTP call reads credentials at call time and passes
  them per-call via httpx `headers=`/`cookies=` kwargs, with a shared `AsyncHTTPTransport`
  for connection-pool reuse and a fresh `AsyncClient` per call. This change is required for
  safe multi-user hosting but affects stdio callers too — the client surface is slightly
  different internally.
- **`service_endpoint` parses URLs properly**: derived service URLs are rebuilt from the
  parsed host instead of a substring replace, so hosts like `foo-api.example.com` fail loudly
  instead of silently producing `foo-redash.example.com`.
- **`DocsClient` no longer caches the docs index**: the previous cache leaked the first
  caller's authenticated view to every subsequent caller. Each `docs_list` call now fetches
  the index; two round trips per `docs_read`. If latency bites in hosted deployments, a
  per-identity-token TTL cache is a straightforward follow-up.
- **`DocsClient` blocks cross-host redirects**: same-host redirects (e.g. trailing-slash
  canonicalization) are followed up to a 5-hop cap, but a redirect whose target host
  differs from the configured docs host is rejected with a clear error. Silently following
  a cross-host redirect would forward the identity-token cookie off-host.
- **Schema drift alarm**: after the GraphQL schema cache is warm, one lightweight probe per
  hour (per worker) compares the live type set against the cached digest and emits a
  `schema_drift_detected` warning log if they differ. Probe failures rewind the timestamp
  so a transient outage doesn't silence drift detection for a full interval.

### Fixes

---

## February 23, 2026

### Features

### Changes

### Fixes

- **Fix breakage with `pydantic-settings` 2.13.0 release**: The 2.13.0 release of `pydantic-settings`
  included a breaking change. Fixed the change, updated the library, and adjusted the version pinning
  to prevent future issues.

---

## November 17, 2025

### Features

- **Python 3.14 support**: the Stacklet MCP server now works with Python 3.14.

### Changes

### Fixes

---
