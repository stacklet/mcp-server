# Stacklet MCP Server

Exposes toolsets for granting LLMs the powers of:

* AssetDB SQL queries (ad-hoc and saved)
* Platform GraphQL operations (and export of large datasets)
* Documentation access (in .md, for context)

Each of the toolsets has an "info" tool with useful context, available to any client which supports minimal MCP features. Asking your agent to tell you about a toolset is a fairly reliable way to get it to call the info tool and load up its context with relevant information.

## Requirements

* install tools (e.g. via `mise install`)
* install dependencies via `just install`
* configure your agent to `just run` in this directory (or copy and adjust the `.mcp.json` file when running the agent from another directory)

## Authentication

The easiest way to authenticate to your stacklet environment is to use the [stacklet-admin] tool, which is most easily installed with:

```
% uv tool install stacklet.client.platform
```

Once you've configured that, a `stacklet-admin login` will grant the MCP server access on your behalf for twelve hours.

## Server configuration

The MCP server can be configured via environment variables.

When the MCP is run from an agent, those can be set in the `"env"` section of
he `.mcp.json` file.

The following variables are available:

- `STACKLET_MCP_ASSETDB_DATASOURCE`: the datasource ID for AssetDB in Redash (default: `1`)
- `STACKLET_MCP_ASSETDB_ALLOW_SAVE`: whether to enable write operations in AssetDB (default: `false`)
- `STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS`: whether to enable executing mutations in Platform API (default: `false`)

## Development

The MCP Protocol Inspector is invaluable for peeking at the details of the protocol in use:

```
% npx @modelcontextprotocol/inspector uv run stacklet-mcp
```
