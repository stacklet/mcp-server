# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides comprehensive tools for interacting with the Stacklet platform. The server exposes tools for documentation access, Stacklet's cloud governance GraphQL API, and AssetDB operations (with some tools conditionally enabled based on configuration).

## Architecture

The codebase follows a modular design with clear separation of concerns:

**Core Components:**
- `stacklet/mcp/mcp.py` - Main FastMCP server with tool definitions
- `stacklet/mcp/stacklet_auth.py` - Authentication credential loading
- `stacklet/mcp/utils/` - Utility functions package for tool implementations
- `stacklet/mcp/settings.py` - Server configuration and feature flags
- `stacklet/mcp/lifespan.py` - Application lifespan management

**Docs Package:**
- `stacklet/mcp/docs/client.py` - Documentation client for fetching docs from Stacklet deployment
- `stacklet/mcp/docs/tools.py` - Documentation tool implementations (docs_list, docs_read)
- `stacklet/mcp/docs/models.py` - Pydantic models for documentation responses

**Platform Package:**
- `stacklet/mcp/platform/graphql.py` - Platform GraphQL client with instance-level schema caching
- `stacklet/mcp/platform/tools.py` - Platform tool implementations (platform_graphql_info, platform_graphql_query, platform_dataset_export, etc.)
- `stacklet/mcp/platform/models.py` - Pydantic models for platform operations (ExportColumn, ExportParam, ConnectionExport, etc.)
- `stacklet/mcp/platform/graphql_info.md` - Detailed guidance for using the Platform GraphQL API

**AssetDB Package:**
- `stacklet/mcp/assetdb/redash.py` - AssetDB client using Redash API for SQL queries and saved query management
- `stacklet/mcp/assetdb/models.py` - Pydantic models specific to AssetDB (Query, User, JobStatus, QueryUpsert, etc.)
- `stacklet/mcp/assetdb/tools.py` - AssetDB tool implementations (assetdb_query_list, assetdb_sql_query, etc.)
- `stacklet/mcp/assetdb/sql_info.md` - Comprehensive guide to AssetDB structure and querying best practices

**Authentication Flow:**
The authentication system echoes the Stacklet Terraform provider's credential resolution:
1. Environment variables (`STACKLET_ENDPOINT`, `STACKLET_ACCESS_TOKEN`, `STACKLET_IDENTITY_TOKEN`)
2. Config files saved by the `stacklet-admin` CLI in `~/.stacklet`

Note: `identity_token` is required for AssetDB access via Redash authentication cookies.

**Tool Naming Convention:**
Tools use component-based prefixes:
- `platform_*` - Tools for Stacklet's platform GraphQL API
- `assetdb_*` - Tools for asset database operations (SQL queries and saved query management)
- Pattern: `{component}_{action}` (e.g., `platform_graphql_query`, `assetdb_sql_query`)

## Development Commands

**Install dependencies:**
```bash
uv sync
# or: just install
```

**Run the MCP server:**
```bash
uv run stacklet-mcp
# or: just run
```

**Development commands (via justfile):**
```bash
just format    # Format code with ruff
just lint      # Run pre-commit hooks
just test      # Run pytest with optional args
```


## MCP Tools Available

**Documentation Tools:**
1. **`docs_list`** - List all available Stacklet user documentation files
2. **`docs_read`** - Read a specific Stacklet documentation file

**Platform GraphQL Tools:**
3. **`platform_graphql_info`** - Key information for LLMs using GraphQL tools (call this first)
4. **`platform_graphql_list_types`** - List the types available in the GraphQL API
5. **`platform_graphql_get_types`** - Retrieve information about specific GraphQL types
6. **`platform_graphql_query`** - Execute GraphQL queries against Stacklet platform
7. **`platform_dataset_info`** - Guide for exporting large datasets
8. **`platform_dataset_export`** - Export full datasets from GraphQL connections to CSV format
9. **`platform_dataset_lookup`** - Check the status of dataset exports

**AssetDB Tools:**
10. **`assetdb_sql_info`** - Key information for LLMs using AssetDB SQL tools (call this first)
11. **`assetdb_sql_query`** - Execute ad-hoc SQL queries against AssetDB
12. **`assetdb_query_list`** - List and search saved queries with pagination
13. **`assetdb_query_get`** - Get detailed information about specific saved queries
14. **`assetdb_query_result`** - Get results for saved queries with caching control
15. **`assetdb_query_save`** - Create new queries or update existing ones (conditionally enabled via `STACKLET_MCP_ASSETDB_ALLOW_SAVE=true`)
16. **`assetdb_query_archive`** - Archive saved queries (conditionally enabled via `STACKLET_MCP_ASSETDB_ALLOW_ARCHIVE=true`)

Total: 14-16 tools (depending on configuration)

The actual tools available are determined by each package's `tools()` function implementation, with some tools conditionally enabled based on server configuration settings.

## Key Implementation Details

**Schema Caching:** The `PlatformClient` class implements instance-level caching to avoid repeated introspection queries, improving performance for schema-heavy operations.

**Client Management:** Both AssetDB and Platform clients use a `.get(ctx)` pattern for lazy initialization and caching in FastMCP context. Credentials are loaded once per session using `StackletCredentials.get(ctx)`.

**Error Handling:** All GraphQL and SQL operations return structured responses, with network errors and JSON parsing errors handled gracefully. AssetDB supports async query polling for long-running operations.

**Credential Security:** Access tokens and identity tokens are never logged or exposed in error messages.

**Platform Integration:** Uses GraphQL API for Stacklet platform operations. The Platform package is organized into:
- `graphql.py` - Core GraphQL client with schema caching and introspection
- `tools.py` - FastMCP tool implementations that expose platform functionality (info, list types, get types, query, dataset exports)
- `models.py` - Pydantic models for exports and GraphQL operations
Uses `graphql-core` for schema manipulation and SDL generation, enabling proper type introspection and schema documentation.

**AssetDB Integration:** Uses Redash API for SQL query execution and saved query management. The AssetDB package is organized into:
- `redash.py` - Core client with async operations and authentication
- `models.py` - Pydantic models for Redash API responses (Query, User, JobStatus, etc.)
- `tools.py` - FastMCP tool implementations that expose AssetDB functionality
Supports query timeouts (max 300s), pagination, search, and tag filtering.

## Configuration

**Stacklet Credentials:**
The server requires Stacklet credentials configured through one of:
- Environment variables: `STACKLET_ENDPOINT`, `STACKLET_ACCESS_TOKEN`, and `STACKLET_IDENTITY_TOKEN`
- CLI config: `~/.stacklet/config.json` (endpoint), `~/.stacklet/credentials` (access token), and `~/.stacklet/id` (identity token)

**Server Settings:**
Additional configuration via environment variables with `STACKLET_MCP_` prefix:
- `STACKLET_MCP_ASSETDB_DATASOURCE` (default: 1) - AssetDB data source ID
- `STACKLET_MCP_ASSETDB_ALLOW_SAVE` (default: false) - Enable query save/update functionality
- `STACKLET_MCP_ASSETDB_ALLOW_ARCHIVE` (default: false) - Enable query archiving functionality
- `STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS` (default: false) - Enable calling mutations in the Platform GraphQL API

**External Dependencies:**
- Documentation files are fetched from the live Stacklet docs service at runtime
- Redash endpoint is derived by replacing "api." with "redash." in the platform endpoint
- Docs endpoint is derived by replacing "api." with "docs." in the platform endpoint

## Known Issues & Design Notes

When you're editing code which matches one of these concerns, think extra hard about
the impact of your changes; prefer to mitigate these issues rather than further
entrench them.

**Documentation Service Dependency:** The docs client fetches documentation from a live Stacklet deployment's docs service (derived by replacing "api." with "docs." in the platform endpoint). This requires proper authentication and network access to the docs service.

**AssetDB Data Source:** The AssetDB client defaults to `data_source_id=1` for the main AssetDB instance. This is hardcoded but can be overridden in function calls
internally.

**Authentication Complexity:** Requires three different credential fields (endpoint, access_token, identity_token) which must all be configured correctly for full functionality.

**Test Coverage:** Most tests are end-to-end tool tests with mocked downstream HTTP
interactions, which is an appropriate level of abstraction for most cases in this codebase. AssetDB in particular is lacking test coverage in some areas, but most tools are well tested, and the patterns seen in the existing tests should be repeated where possible.

**Dict Returns:** Many tools and client methods should return better-structured data.

**Loose Validation:** Tool parameters in particular could often benefit from further
type annotation to encode (and advertise to clients!) expectations. Obvious examples include:
- download_format literals
- assetdb result timeout
- query_id >= 1

## Important Advice

- When running python in this project, always use "uv run python".
- When you've made code changes, verify them with "just test" and "just lint".
- You will find it useful to have access to the Redash source code as you work; this
  project talks to `https://github.com/stacklet/redash`, NOT the upstream project by
  `getredash`. Cloning that repository into a temp directory and using the filesystem
  is the most effective way to answer questions about redah implementation details.
