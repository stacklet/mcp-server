# Stacklet MCP Server

Currently extremely rudimentary:
* install tools (e.g. via `mise install`)
* `just install` to install dependencies
* requires sibling checkout of https://github.com/stacklet/docs
* expects you to have run `stacklet-admin login` recently
* otherwise configure your agent to `uv run mcp` in this directory (or copy and adjnust the `.mcp.json` file when running the agent from another directory)

When primed with e.g. "tell me about the stacklet graphql api", appears to pull in enough context to answer subsequent questions like "tell me about my stacklet deployment" by running exploratory queries, fixing its own mistakes in the process; can be cajoled into exporting datasets and downloading them locally for subsequent analysis with better-suited tools.
