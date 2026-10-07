## Next Release

### Features

### Changes

- **Dataset exports download with your credentials**: Stacklet now requires sign-in to
  download an export, and only the user who started it can. When the server writes files,
  `platform_dataset_lookup` and `platform_dataset_export` download the finished export with
  your token and return the local path in `full_results_saved_to`. A hosted server returns
  the link with a `download_note` telling you to open it in your signed-in browser.

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
