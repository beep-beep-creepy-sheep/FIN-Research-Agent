from __future__ import annotations

import json
import re
import sqlite3
from hashlib import sha256
from collections.abc import Iterable
from pathlib import Path

from app.database import connect, migrate, table_exists
from app.models import DocumentMetadata, EvidenceSnippet


SUPPORTED_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".json"}


def read_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _read_pdf_text(path)
    raise ValueError(
        f"Unsupported file type: {suffix or '[no suffix]'}. "
        "Supported types are .txt, .md, .csv, .json, and .pdf when pypdf is installed."
    )


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires pypdf. Install it with: pip install pypdf") from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n[page {index}]\n{text}")
    return "\n".join(pages).strip()


def chunk_text(text: str, chunk_size: int = 1400, overlap: int = 180) -> list[tuple[str, int, int]]:
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n\n", start, end), normalized.rfind(". ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def tokenize(text: str) -> list[str]:
    return [item.lower() for item in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", text)]


class DocumentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        migrate(self.path)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.path)

    def add_file(
        self,
        path: Path,
        metadata: DocumentMetadata | None = None,
        *,
        replace: bool = True,
    ) -> int:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        metadata = metadata or DocumentMetadata.from_path(path)
        text = read_document_text(path)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError(f"No extractable text found in {path}")

        source_path = str(path.resolve())
        file_hash = hash_file(path)
        metadata = metadata.model_copy(update={"source_path": source_path})
        with self._connect() as db:
            if replace:
                existing = db.execute(
                    "SELECT id FROM documents WHERE source_path = ? OR file_hash = ?",
                    (source_path, file_hash),
                ).fetchall()
                for row in existing:
                    self._delete_document(db, int(row["id"]))
            cursor = db.execute(
                """
                INSERT INTO documents (
                    title, source_path, source_type, issuer, report_period, publication_date,
                    currency, unit, url, source_url, local_path, file_hash, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.title,
                    metadata.source_path,
                    metadata.source_type,
                    metadata.issuer,
                    metadata.report_period,
                    metadata.publication_date,
                    metadata.currency,
                    metadata.unit,
                    metadata.url,
                    metadata.url,
                    source_path,
                    file_hash,
                    metadata.model_dump_json(),
                ),
            )
            document_id = int(cursor.lastrowid)
            for index, (chunk, start, end) in enumerate(chunks):
                chunk_cursor = db.execute(
                    """
                    INSERT INTO chunks (
                        document_id, chunk_index, text, start_char, end_char, token_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (document_id, index, chunk, start, end, " ".join(tokenize(chunk))),
                )
                self._insert_fts(
                    db,
                    rowid=int(chunk_cursor.lastrowid),
                    text=chunk,
                    title=metadata.title,
                    issuer=metadata.issuer or "",
                )
        return document_id

    def _delete_document(self, db: sqlite3.Connection, document_id: int) -> None:
        chunk_ids = [
            int(row["id"])
            for row in db.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
        ]
        if table_exists(db, "chunks_fts"):
            for chunk_id in chunk_ids:
                db.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,))
        db.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        db.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    def _insert_fts(self, db: sqlite3.Connection, rowid: int, text: str, title: str, issuer: str) -> None:
        if not table_exists(db, "chunks_fts"):
            return
        try:
            db.execute(
                "INSERT INTO chunks_fts(rowid, text, title, issuer) VALUES (?, ?, ?, ?)",
                (rowid, text, title, issuer),
            )
        except sqlite3.DatabaseError:
            return

    def add_files(self, paths: Iterable[Path], issuer: str | None = None) -> list[int]:
        ids: list[int] = []
        for path in paths:
            metadata = DocumentMetadata.from_path(path)
            if issuer:
                metadata = metadata.model_copy(update={"issuer": issuer})
            ids.append(self.add_file(path, metadata))
        return ids

    def search(self, query: str, *, limit: int = 8) -> list[EvidenceSnippet]:
        query_terms = tokenize(query)
        if not query_terms:
            return []

        with self._connect() as db:
            rows = self._search_fts(db, query, limit)
            if not rows:
                rows = db.execute(
                    """
                    SELECT
                        d.id AS document_id,
                        d.title,
                        d.source_path,
                        d.issuer,
                        d.report_period,
                        d.publication_date,
                        d.url,
                        c.chunk_index,
                        c.text,
                        c.token_text
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    """
                ).fetchall()

        scored: list[EvidenceSnippet] = []
        for row in rows:
            token_text = row["token_text"]
            score = _score_chunk(query_terms, token_text, row["title"])
            if score <= 0:
                continue
            scored.append(
                EvidenceSnippet(
                    document_id=row["document_id"],
                    chunk_id=row["chunk_index"],
                    title=row["title"],
                    source_path=row["source_path"],
                    text=row["text"],
                    score=score,
                    issuer=row["issuer"],
                    report_period=row["report_period"],
                    publication_date=row["publication_date"],
                    url=row["url"],
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    def _search_fts(
        self, db: sqlite3.Connection, query: str, limit: int
    ) -> list[sqlite3.Row]:
        if not table_exists(db, "chunks_fts"):
            return []
        try:
            return db.execute(
                """
                SELECT
                    d.id AS document_id,
                    d.title,
                    d.source_path,
                    d.issuer,
                    d.report_period,
                    d.publication_date,
                    d.url,
                    c.chunk_index,
                    c.text,
                    c.token_text,
                    bm25(chunks_fts) * -1 AS fts_score
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (quote_fts_query(query), limit),
            ).fetchall()
        except sqlite3.DatabaseError:
            return []

    def list_documents(self) -> list[dict[str, object]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.source_path,
                    d.source_type,
                    d.issuer,
                    d.report_period,
                    d.publication_date,
                    COUNT(c.id) AS chunks
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def export_jsonl(self, output: Path) -> int:
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = self.list_documents()
        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)


def _score_chunk(query_terms: list[str], token_text: str, title: str) -> float:
    title_lower = title.lower()
    score = 0.0
    for term in query_terms:
        occurrences = token_text.count(term)
        if occurrences:
            score += 1.0 + min(occurrences, 8) * 0.25
        if term in title_lower:
            score += 0.75
    return score


def hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quote_fts_query(query: str) -> str:
    terms = tokenize(query)
    return " OR ".join(f'"{term}"' for term in terms) or '""'
