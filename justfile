# install dependencies
install:
    uv sync

# run the MCP server locally
run:
    uv run mcp

# format code
format:
    uv run ruff format
    uv run ruff check --fix

# lint code
lint:
	uv run pre-commit run --all-files
