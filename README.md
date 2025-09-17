# Stacklet MCP Server

Currently extremely rudimentary:
* install tools (e.g. via `mise install`)
* install dependencies via `just install`
* expects you to have run `stacklet-admin login` recently
* otherwise configure your agent to `just run` in this directory (or copy and adjust the `.mcp.json` file when running the agent from another directory)

When primed with e.g. "tell me about the stacklet graphql api", Claude appears to pull in enough context to answer subsequent questions like "tell me about my stacklet deployment" by running exploratory queries, fixing its own mistakes in the process; can be cajoled into exporting datasets and downloading them locally for subsequent analysis with better-suited tools.

When primed with e.g. "tell me about querying assetdb", and "explore the assetdb schema and tell me about it", Claude appears to generate and run sensible queries around cost and tagging use cases.


# Server configuration

The MCP server can be configured via environment variables.

When the MCP is run from an agent, those can be set in the `"env"` section of
he `.mcp.json` file.

The following variables are available:

- `STACKLET_MCP_ASSETDB_DATASOURCE`: the datasource ID for AssetDB in Redash (default: `1`)
- `STACKLET_MCP_ASSETDB_SAVE`: whether to enable write operations in assetdb (default: `false`)
