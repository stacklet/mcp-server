# Setup development environment
install:
    #!/usr/bin/env bash
    set -e

    uv sync
    if [ ! -e .mcp.json ]; then
      just agent-config
      echo "Wrote .mcp.json"
    fi

# Run the MCP server locally
run *args:
    uv run stacklet-mcp {{args}}

# Run code formatters/linters
lint:
    uv run pre-commit run --all-files

# Run tests
test *args:
    uv run pytest {{args}}

# Run tests with coverage
test-coverage *args:
    just test --cov {{args}}

# Run mcp-inspector
inspect:
    npx @modelcontextprotocol/inspector just run

# Generate agent configuration (.mcp.json)
agent-config profile="default":
    just run agent-config generate {{profile}} > .mcp.json
