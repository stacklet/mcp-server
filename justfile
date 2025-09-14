# Install dependencies
install:
    uv sync

# Run the MCP server locally
run:
    uv run mcp

# Format code
format:
    uv run ruff check --fix
    uv run ruff format

# Lint code
lint:
	uv run pre-commit run --all-files


# Run tests
test *args:
    uv run pytest {{args}}
