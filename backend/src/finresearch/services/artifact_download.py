from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from finresearch.data_sources.official import DownloadedArtifact, FilingMetadata
from finresearch.settings import get_settings


@dataclass(frozen=True)
class DownloadLimits:
    max_bytes: int
    max_redirects: int = 3


class ArtifactDownloadService:
    def __init__(self, *, max_bytes: int | None = None) -> None:
        self.settings = get_settings()
        self.limits = DownloadLimits(
            max_bytes=max_bytes or int(os.getenv("OFFICIAL_SOURCE_MAX_DOWNLOAD_BYTES", "52428800"))
        )

    def archive_bytes(
        self,
        metadata: FilingMetadata,
        content: bytes,
        *,
        allowed_domains: tuple[str, ...],
        content_type: str = "application/pdf",
    ) -> DownloadedArtifact:
        self.validate_url(metadata.download_url or metadata.canonical_url, allowed_domains)
        if len(content) > self.limits.max_bytes:
            raise ValueError("download_too_large")
        file_magic = content[:8].decode("latin1", errors="ignore")
        if (metadata.document_type or "").lower() == "pdf" and not content.startswith(b"%PDF"):
            raise ValueError("invalid_pdf_magic")

        digest = hashlib.sha256(content).hexdigest()
        symbol = metadata.symbol.replace(".", "_")
        year = (metadata.publication_date or "unknown")[:4]
        safe_document_id = _safe_segment(metadata.source_document_id)
        raw_dir = self.settings.raw_data_dir / metadata.source_id / symbol / year / safe_document_id
        doc_dir = self.settings.documents_dir / metadata.source_id / symbol / year
        raw_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = raw_dir / "metadata.json"
        suffix = ".pdf" if content.startswith(b"%PDF") else ".bin"
        final_path = doc_dir / f"{digest}{suffix}"

        metadata_payload = {
            "source_id": metadata.source_id,
            "source_document_id": metadata.source_document_id,
            "canonical_url": metadata.canonical_url,
            "download_url": metadata.download_url,
            "title": metadata.title,
            "raw_metadata": metadata.raw_metadata,
            "sha256": digest,
            "content_type": content_type,
            "content_length": len(content),
        }
        metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        reused = final_path.exists()
        if not reused:
            fd, tmp_name = tempfile.mkstemp(prefix=f".{digest}.", dir=str(doc_dir))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, final_path)
            finally:
                tmp_path = Path(tmp_name)
                if tmp_path.exists():
                    tmp_path.unlink()
        return DownloadedArtifact(
            source_id=metadata.source_id,
            source_document_id=metadata.source_document_id,
            final_path=final_path,
            raw_metadata_path=metadata_path,
            sha256=digest,
            content_type=content_type,
            content_length=len(content),
            file_magic=file_magic,
            reused=reused,
        )

    def validate_url(self, url: str, allowed_domains: tuple[str, ...]) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("blocked_url_scheme")
        if parsed.scheme != "https":
            raise ValueError("https_required_for_official_source")
        host = parsed.hostname
        if not host:
            raise ValueError("missing_url_host")
        if host.lower() not in {domain.lower() for domain in allowed_domains}:
            raise ValueError("domain_not_allowed")
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or str(ip) == "169.254.169.254"
            ):
                raise ValueError("blocked_private_or_metadata_ip")


def _safe_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    cleaned = cleaned.strip("._")
    if not cleaned:
        raise ValueError("unsafe_path_segment")
    return cleaned[:160]
