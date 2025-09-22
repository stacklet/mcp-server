# Stacklet MCP Server

This is the MCP (Model Context Protocol) server for the Stacklet environment.
It exposes toolsets for granting LLMs the powers of:

* AssetDB SQL queries (ad-hoc and saved)
* Platform GraphQL operations (and export of large datasets)
* Documentation access (in .md, for context)

Each of the toolsets has an "info" tool with useful context, available to any client which supports minimal MCP features.
Asking your agent to tell you about a toolset is a fairly reliable way to get it to call the info tool and load up its context with relevant information.

**WARNING**: most Stacklet installations contain confidential data; this server largely exists to feed that data to your agent's LLM, which is generally running in a datacenter _Somewhere_. Be very confident in your understanding of all relevant data security policies before running this server.

**FURTHER WARNING**: when running with default settings, the worst an LLM can do with this server is make ill-advised queries, which is often regrettable but generally no worse than a well-intentioned human user might do.

By enabling the `_ALLOW_` options documented below, you are granting an LLM free rein to do _anything_ you could do with Stacklet; doing so naturally bears risks proportional to your own level of access. Strongly consider authenticating as a custom Stacklet user with permissions tightly scoped to your task as an additional safeguard.


## Installation

The easiest way to get the `stacklet-mcp` binary is via `pip` or `uv`, with

```
pip install stacklet-mcp
```

or

```
uv install stacklet-mcp
```

Once installed, an agent configuration file (`.mcp.json`) can be generated with

```
stacklet-mcp agent-config generate $profile
```

where `$profile` can be either default (no edit allowed) or `unrestricted` (all edits allowed).
The configuration can be manually tweaked to just allow some edits.


## Authentication

The MCP server needs to be authenticated wtih the Stacklet environment before use.
The easiest way to authenticate to your Stacklet environment is to use the [stacklet-admin](https://pypi.org/project/stacklet.client.platform/) command, which is most easily installed with:

```
uv tool install stacklet.client.platform
```

Once you've configured that, a

```
stacklet-admin login
```

will grant the MCP server access as the authenticated user for twelve hours. Leaving aside the default blocks on saving queries and mutating platform, the server will have the same powers and restrictions as that user.


## Server configuration

The MCP server can be configured via environment variables.

When the MCP is run from an agent, those can be set in the `"env"` section of the `.mcp.json` file.

The following variables are available:

- `STACKLET_MCP_ASSETDB_DATASOURCE`: the datasource ID for AssetDB in Redash (default: `1`)
- `STACKLET_MCP_ASSETDB_ALLOW_SAVE`: whether to enable write operations in AssetDB (default: `false`)
- `STACKLET_MCP_ASSETDB_ALLOW_ARCHIVE`: whether to enable query archiving functionality in AssetDB (default: `false`)
- `STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS`: whether to enable executing mutations in Platform API (default: `false`)


## Development

For development, a few setup steps are required:


1) install required tools. The easiest way is through [Mise](https://mise.jdx.dev/):

```
mise install
```

2) install dependencies via

```
just install
```

This will also create a default`.mcp.json` (so long as there's nothing there already) with default read-only settings, which enables convenient experimentation by running e.g. [Claude Code](https://claude.com/product/claude-code)) in the project root without risk of altering saved AssetDB queries or running Platform mutations.

For alternative integrations, the `.mcp.json` file should serve as a starting point, but the details may vary by context; the best documentation for the format itself seems to be [here](https://gofastmcp.com/integrations/mcp-json-configuration#mcp-json-configuration-standard).


3) Authenticate to the deployment as described above.

4) Run the MCP server with

```
just run [options...]
```


### Inspect MCP protocol


The MCP Protocol Inspector is invaluable for peeking at the details of the protocol in use. It can be run via

```
just inspect
```
