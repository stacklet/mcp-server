# Stacklet MCP Server

Has useful toolsets for granting LLMs the powers of:

* AssetDB SQL queries (ad-hoc and saved)
* Platform GraphQL queries (and mutations)
* Documentation access (in .md, for context)

## Requirements

* install tools (e.g. via `mise install`)
* install dependencies via `just install`
* expects you to have run `stacklet-admin login` recently
* otherwise configure your agent to `just run` in this directory (or copy and adjust the `.mcp.json` file when running the agent from another directory)

# Server configuration

The MCP server can be configured via environment variables.

When the MCP is run from an agent, those can be set in the `"env"` section of
he `.mcp.json` file.

The following variables are available:

- `STACKLET_MCP_ASSETDB_DATASOURCE`: the datasource ID for AssetDB in Redash (default: `1`)
- `STACKLET_MCP_ASSETDB_SAVE`: whether to enable write operations in assetdb (default: `false`)

## Handy Commands

Install `stacklet-admin`:
```
uv tool install stacklet.client.platform
```

Interact manually with the server in as much detail as you desire:
```
% npx @modelcontextprotocol/inspector uv run mcp
```
