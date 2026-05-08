"""Pure-Python MIME type detection from buffer. Safe on Windows (no libmagic DLL)."""
from typing import Optional

import filetype


def get_mime_from_buffer(content: bytes) -> Optional[str]:
    """Guess MIME type from file content using magic numbers. Returns None if unknown."""
    if not content:
        return None
    kind = filetype.guess(content)
    return kind.mime if kind else None
