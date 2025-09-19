from importlib import resources
from pathlib import Path
from typing import cast


def get_file_text(path: str) -> str:
    """Return a file under the stacklet/mcp package."""
    # the Traversable is always a path in practice
    return cast(Path, resources.files("stacklet") / "mcp" / path).read_text()
