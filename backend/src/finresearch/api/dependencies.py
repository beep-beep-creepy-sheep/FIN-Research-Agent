from __future__ import annotations

from pathlib import Path

from finresearch.database.session import get_library_path


def library_path() -> Path:
    return get_library_path()

