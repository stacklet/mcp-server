# Install dependencies
install:
    uv sync

# Run the MCP server locally
run:
    uv run stacklet-mcp

# Format code
format:
    uv run ruff check --fix
    uv run ruff format
    - uv run pyproject-fmt -n pyproject.toml

# Lint code
lint:
	uv run pre-commit run --all-files

# Run tests
test *args:
    uv run pytest {{args}}

# Run tests with coverage
test-coverage *args:
    just test --cov {{args}}
