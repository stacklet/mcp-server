# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides comprehensive tools for interacting with the Stacklet platform. The server exposes 10 tools: 2 for documentation access, 4 for querying Stacklet's cloud governance GraphQL API, and 4 for AssetDB operations.

## Architecture

The codebase follows a modular design with clear separation of concerns:

**Core Components:**
- `stacklet/mcp/mcp.py` - Main FastMCP server with tool definitions and middleware
- `stacklet/mcp/stacklet_auth.py` - Authentication credential loading (follows Terraform provider patterns)
- `stacklet/mcp/stacklet_platform.py` - Platform GraphQL client with instance-level schema caching
- `stacklet/mcp/assetdb_redash.py` - AssetDB client using Redash API for SQL queries and saved query management
- `stacklet/mcp/docs_handler.py` - Documentation file reading and listing (hardcoded to ../../../docs/src)
- `stacklet/mcp/models.py` - Pydantic models for structured responses
- `stacklet/mcp/utils.py` - Utility functions for package resources

**Authentication Flow:**
The authentication system mirrors the Stacklet Terraform provider's credential resolution:
1. Direct parameters (endpoint, access_token, identity_token)
2. Environment variables (`STACKLET_ENDPOINT`, `STACKLET_ACCESS_TOKEN`, `STACKLET_IDENTITY_TOKEN`)
3. CLI config files (`~/.stacklet/config.json`, `~/.stacklet/credentials`, `~/.stacklet/id`)

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
uv run mcp
# or: just run
# or directly: python stacklet/mcp/mcp.py
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

**AssetDB Tools:**
7. **`assetdb_sql_info`** - Key information for LLMs using AssetDB SQL tools (call this first)
8. **`assetdb_sql_query`** - Execute ad-hoc SQL queries against AssetDB
9. **`assetdb_query_list`** - List and search saved queries with pagination
10. **`assetdb_query_get`** - Get detailed information about specific saved queries

## Key Implementation Details

**Schema Caching:** The `PlatformClient` class implements instance-level caching to avoid repeated introspection queries, improving performance for schema-heavy operations.

**Session Management:** Uses FastMCP middleware (`AuthInitMiddleware`) to initialize both AssetDB and Platform clients once per session and store them in session context.

**Error Handling:** All GraphQL and SQL operations return structured responses, with network errors and JSON parsing errors handled gracefully. AssetDB supports async query polling for long-running operations.

**Credential Security:** Access tokens and identity tokens are never logged or exposed in error messages. The authentication module follows secure patterns from the official Terraform provider.

**GraphQL Integration:** Uses `graphql-core` for schema manipulation and SDL generation, enabling proper type introspection and schema documentation.

**AssetDB Integration:** Uses Redash API for SQL query execution and saved query management. Supports query timeouts (max 300s), pagination, search, and tag filtering.

## Configuration

The server requires Stacklet credentials configured through one of:
- Environment variables: `STACKLET_ENDPOINT`, `STACKLET_ACCESS_TOKEN`, and `STACKLET_IDENTITY_TOKEN`
- CLI config: `~/.stacklet/config.json` (endpoint), `~/.stacklet/credentials` (access token), and `~/.stacklet/id` (identity token)
- Direct parameter passing to functions

**External Dependencies:**
- Documentation files must be available at `../../../docs/src/` relative to the MCP server location
- Redash endpoint is derived by replacing "api." with "redash." in the platform endpoint

## Known Issues & Design Notes

**Documentation Path Dependency:** The docs handler has a hardcoded path dependency (`DOCS_ROOT = Path(__file__).parent / ".." / ".." / ".." / "docs" / "src"`) which assumes a specific directory structure outside the MCP codebase.

**AssetDB Data Source:** The AssetDB client defaults to `data_source_id=1` for the main AssetDB instance. This is hardcoded but can be overridden in function calls.

**Authentication Complexity:** Requires three different credential types (endpoint, access_token, identity_token) which must all be configured correctly for full functionality.
