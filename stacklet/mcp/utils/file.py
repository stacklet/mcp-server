# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import tempfile

from typing import IO, Any

from ..settings import SETTINGS


def download_file(mode: str, prefix: str, suffix: str) -> IO[Any]:
    """Create a temporary file in the configured downloads directory.

    Args:
        mode: File mode (e.g., 'w', 'wb')
        prefix: Filename prefix
        suffix: Filename suffix including extension

    Returns:
        A file handle to the created temporary file
    """
    SETTINGS.downloads_path.mkdir(parents=True, exist_ok=True)
    return tempfile.NamedTemporaryFile(
        mode=mode,
        dir=str(SETTINGS.downloads_path),
        prefix=prefix,
        suffix=suffix,
        delete=False,
    )
