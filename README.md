# Stacklet MCP Server

Exposes toolsets for granting LLMs the powers of:

* AssetDB SQL queries (ad-hoc and saved)
* Platform GraphQL operations (and export of large datasets)
* Documentation access (in .md, for context)

Each of the toolsets has an "info" tool with useful context, available to any client which supports minimal MCP features. Asking your agent to tell you about a toolset is a fairly reliable way to get it to call the info tool and load up its context with relevant information.

## WARNING

Most Stacklet installations contain confidential data; this server largely exists to feed that data to your agent's LLM, which is generally running in a datacenter _Somewhere_. Be very confident in your understanding of all relevant data security policies before using this tool.

## FURTHER WARNING

When running with default settings, the worst an LLM can do with this tool is make ill-advised queries, which is often regrettable but generally no worse than a well-intentioned human user might do.

By enabling the `_ALLOW_` options documented below, you are granting an LLM free rein to do _anything_ you could do with Stacklet; doing so naturally bears risks proportional to your own level of access. Strongly consider authenticating as a custom Stacklet user with permissions tightly scoped to your task as an additional safeguard.

## Requirements

* install tools (e.g. via `mise install`)
* install dependencies via `just install`
* configure your agent to `just run` in this directory (or copy and adjust one of the `mcp.*.json` files when running the agent from another directory)

By default, `just install` will copy `mcp.default.json` to `.mcp.json`, which enables convenient experimentation by running [Claude Code](https://claude.com/product/claude-code)) in the project root without risk of altering saved AssetDB queries or running Platform mutations.

The `mcp.unrestricted.json` file shows how to configure the server without these guardrails; heed the warnings above.

For integration with other agents, the `mcp.*.json` files should serve as a starting point, but the [details may vary](https://gofastmcp.com/integrations/mcp-json-configuration#mcp-json-configuration-standard) by context.

## Authentication

The easiest way to authenticate to your stacklet environment is to use the [stacklet-admin](https://pypi.org/project/stacklet.client.platform/) tool, which is most easily installed with:

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
