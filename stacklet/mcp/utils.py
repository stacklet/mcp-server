from importlib import resources
from pathlib import Path
from typing import cast


def get_package_file(path: str) -> Path:
    """Return a file under the stacklet/mcp package."""
    # the Traversable is always a path in practice
    return cast(Path, resources.files("stacklet") / "mcp" / path)
