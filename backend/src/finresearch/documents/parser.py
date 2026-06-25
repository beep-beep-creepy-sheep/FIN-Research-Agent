from __future__ import annotations

from pathlib import Path

from app.document_store import read_document_text


def parse_document_text(path: Path) -> str:
    return read_document_text(path)

