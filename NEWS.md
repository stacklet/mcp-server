## Next Release

### Features

### Changes

### Fixes

---

## October 23, 2026

### Features

- **Ask about IaC Governance**: your AI assistant can now answer questions about
  Stacklet's IaC Governance from the Stacklet documentation. When the documentation does
  not cover something, it says so instead of guessing.
- **See which tools can change things**: AI apps that support it can now show which
  Stacklet tools only read your data and which can make changes, so you can choose to
  approve changes before they happen. AssetDB queries count as able to make changes,
  because what a query can do depends on your database permissions, so your app may ask
  before it runs one.

### Changes

- **Private dataset exports**: only the person who starts a dataset export can download
  it, and they must be signed in to Stacklet. Your assistant still downloads finished
  exports for you, using your Stacklet sign-in. If an export has expired, or belongs to
  someone else, you now get a clear message instead of a broken link.
- **Simpler saved query results**: when your assistant saves the full results of an
  AssetDB query to a file, the file now holds just the rows, which is easier to open in
  other tools. If you have scripts that read these files, check them against the new
  format. Links to download query results now work only for people signed in to Stacklet.
- **Fewer startup errors on Windows**: the configuration that `stacklet-mcp agent-config`
  generates now avoids text encoding errors when your AI app starts the server.

### Fixes

- **AssetDB queries work on more Stacklet deployments**: some deployments could not run
  AssetDB queries at all. The server now finds AssetDB on its own.
- **Fewer failed GraphQL queries**: when your assistant writes a query that asks for data
  Stacklet does not have, it now gets a clear explanation and can correct the query
  itself.
- **Fresh installs start again**: installing stacklet-mcp into a new environment could
  pull in a newer, incompatible version of a library it depends on, and the server would
  not start. Installs now get a compatible version.
- **Security updates**: stacklet-mcp now requires a version of certifi, its list of
  trusted certificate authorities, that no longer trusts the compromised eMudhra
  authority. Other dependencies are updated to pick up security fixes.

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
