# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides GraphQL tools for interacting with the Stacklet platform. The server exposes 6 tools: 2 for documentation access and 4 for querying Stacklet's cloud governance API.

## Architecture

The codebase follows a modular design with clear separation of concerns:

**Core Components:**
- `stacklet/mcp/mcp.py` - Main FastMCP server with tool definitions
- `stacklet/mcp/stacklet_auth.py` - Authentication credential loading (follows Terraform provider patterns)
- `stacklet/mcp/stacklet_query.py` - GraphQL query execution
- `stacklet/mcp/stacklet_schema.py` - GraphQL schema introspection with caching
- `stacklet/mcp/docs_handler.py` - Documentation file reading and listing

**Authentication Flow:**
The authentication system mirrors the Stacklet Terraform provider's credential resolution:
1. Direct parameters (endpoint, access_token)
2. Environment variables (`STACKLET_ENDPOINT`, `STACKLET_ACCESS_TOKEN`)
3. CLI config files (`~/.stacklet/config.json`, `~/.stacklet/credentials`)

**Tool Naming Convention:**
Tools use component-based prefixes:
- `platform_*` - Tools for Stacklet's platform component
- Future: `assetdb_*` - Tools for asset database component
- Pattern: `{component}_{action}` (e.g., `platform_graphql_query`)

## Development Commands

**Install dependencies:**
```bash
uv sync
```

**Run the MCP server:**
```bash
uv run mcp
# or directly:
python stacklet/mcp/mcp.py
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

## Key Implementation Details

**Schema Caching:** The `stacklet_schema.py` module implements global caching to avoid repeated introspection queries, improving performance for schema-heavy operations.

**Error Handling:** All GraphQL operations return structured responses, with network errors and JSON parsing errors handled gracefully.

**Credential Security:** Access tokens are never logged or exposed in error messages. The authentication module follows secure patterns from the official Terraform provider.

**GraphQL Integration:** Uses `graphql-core` for schema manipulation and SDL generation, enabling proper type introspection and schema documentation.

## Configuration

The server requires Stacklet credentials configured through one of:
- Environment variables: `STACKLET_ENDPOINT` and `STACKLET_ACCESS_TOKEN`
- CLI config: `~/.stacklet/config.json` (endpoint) and `~/.stacklet/credentials` (access token)
- Direct parameter passing to functions

No additional configuration files or setup required beyond authentication credentials.
