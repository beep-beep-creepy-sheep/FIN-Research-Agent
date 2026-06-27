from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select

from finresearch.database.models import Document, DocumentChunk, Filing
from finresearch.database.session import session_scope

PARSER_VERSION = "stage3-page-aware-v1"


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    warning: str | None = None


class FilingDocumentParser:
    def parse_filing(self, filing_id: int) -> dict[str, object]:
        with session_scope() as session:
            filing = session.get(Filing, filing_id)
            if filing is None:
                raise ValueError("filing_not_found")
            if not filing.local_path:
                raise ValueError("filing_not_downloaded")
            path = Path(filing.local_path)
            title = filing.title or path.name
            source_url = filing.canonical_url or filing.source_url

        pages, warnings, status = parse_pages(path)
        text = "\n".join(page.text for page in pages)
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with session_scope() as session:
            existing = session.scalar(select(Document).where(Document.filing_id == filing_id))
            if existing is not None and existing.parser_version == PARSER_VERSION:
                session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == existing.id))
                document = existing
            else:
                if existing is not None:
                    session.delete(existing)
                    session.flush()
                document = Document(
                    filing_id=filing_id,
                    title=title,
                    source_url=source_url,
                    local_path=str(path),
                    source_path=str(path),
                    source_type=path.suffix.lower().removeprefix(".") or "file",
                    file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                    document_type=path.suffix.lower().removeprefix(".") or "file",
                )
                session.add(document)
                session.flush()
            document.parse_status = status
            document.parser_version = PARSER_VERSION
            document.page_count = len(pages)
            document.parse_warnings = warnings
            document.content_hash = content_hash

            chunk_count = 0
            for page in pages:
                for chunk_index, (chunk, start, end) in enumerate(_chunk_page(page.text)):
                    session.add(
                        DocumentChunk(
                            document_id=document.id,
                            filing_id=filing_id,
                            chunk_index=chunk_count,
                            page_number=page.page_number,
                            section=None,
                            text=chunk,
                            search_vector=chunk.lower(),
                            start_char=start,
                            end_char=end,
                            source_url=source_url,
                            parser_version=PARSER_VERSION,
                            content_hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                        )
                    )
                    chunk_count += 1
            filing = session.get(Filing, filing_id)
            if filing is not None:
                filing.parse_status = status
            session.flush()
            return {
                "document_id": document.id,
                "filing_id": filing_id,
                "status": status,
                "parser_version": PARSER_VERSION,
                "page_count": len(pages),
                "chunks_created": chunk_count,
                "warnings": warnings,
            }


def parse_pages(path: Path) -> tuple[list[PageText], list[str], str]:
    suffix = path.suffix.lower()
    warnings: list[str] = []
    try:
        if suffix == ".pdf":
            return _parse_pdf(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return [PageText(1, "")], ["empty_text"], "ocr_required"
        return [PageText(1, text)], warnings, "parsed"
    except Exception as exc:
        return [PageText(1, "")], [f"parse_failed:{type(exc).__name__}"], "failed"


def _parse_pdf(path: Path) -> tuple[list[PageText], list[str], str]:
    warnings: list[str] = []
    try:
        from pypdf import PdfReader
    except Exception:
        text = path.read_bytes().decode("latin1", errors="ignore")
        return [PageText(1, text)], ["pypdf_not_installed_fallback_text"], "parsed_with_warnings"
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            return [PageText(1, "")], ["encrypted_pdf"], "failed"
        pages: list[PageText] = []
        for index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
                if not text.strip():
                    warnings.append(f"page_{index}_empty_text")
                pages.append(PageText(index, text))
            except Exception as exc:
                warning = f"page_{index}_parse_failed:{type(exc).__name__}"
                warnings.append(warning)
                pages.append(PageText(index, "", warning))
        if not any(page.text.strip() for page in pages):
            return pages or [PageText(1, "")], warnings + ["ocr_required"], "ocr_required"
        status = "parsed_with_warnings" if warnings else "parsed"
        return pages, warnings, status
    except Exception as exc:
        return [PageText(1, "")], [f"invalid_pdf:{type(exc).__name__}"], "failed"


def _chunk_page(text: str, *, chunk_size: int = 1200) -> list[tuple[str, int, int]]:
    if not text:
        return [("", 0, 0)]
    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append((text[start:end], start, end))
        start = end
    return chunks
