from __future__ import annotations

from pathlib import Path
from shutil import copy2

from app.document_store import hash_file


def store_document(source: Path, documents_dir: Path) -> Path:
    documents_dir.mkdir(parents=True, exist_ok=True)
    digest = hash_file(source)
    destination = documents_dir / f"{digest[:16]}{source.suffix.lower()}"
    if not destination.exists():
        copy2(source, destination)
    return destination

