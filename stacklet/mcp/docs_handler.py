from pathlib import Path


# Hardcoded documentation root directory
DOCS_ROOT = Path(__file__).parent / ".." / ".." / ".." / "docs" / "src"


def read_documentation_file(file_path: Path) -> str | None:
    """Read a documentation file from the docs directory

    Args:
        file_path: Relative path to the documentation file (e.g., "index_llms.md")

    Returns:
        File content as string, or None if file not found or not accessible
    """
    try:
        # Resolve the full path and ensure it's within the docs directory
        full_path = (DOCS_ROOT / file_path).resolve()

        # Security check: ensure the resolved path is within docs directory
        if not str(full_path).startswith(str(DOCS_ROOT.resolve())):
            return None

        # Check if file exists and is readable
        if not full_path.exists() or not full_path.is_file():
            return None

        # Read and return file content
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    except (OSError, IOError, UnicodeDecodeError):
        return None


def list_documentation_files() -> list[Path]:
    """List all documentation files in the docs directory

    Returns:
        List of relative file paths within the docs directory
    """
    try:
        if not DOCS_ROOT.exists():
            return []

        files = []
        for file_path in DOCS_ROOT.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() == ".md":
                relative_path = file_path.relative_to(DOCS_ROOT)
                files.append(relative_path)
        return sorted(files)

    except (OSError, IOError):
        return []
