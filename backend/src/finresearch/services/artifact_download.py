from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

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

    def download_from_url(
        self,
        metadata: FilingMetadata,
        *,
        allowed_domains: tuple[str, ...],
        session: requests.Session | None = None,
        conditional_headers: dict[str, str] | None = None,
    ) -> DownloadedArtifact:
        url = metadata.download_url or metadata.canonical_url
        client = session or requests.Session()
        redirects = 0
        headers = {
            "User-Agent": "FinResearchAgent/0.1 official-artifact-download",
            "Accept": "application/pdf, text/html;q=0.8, */*;q=0.5",
        }
        if conditional_headers:
            headers.update(conditional_headers)
        current_url = url
        while True:
            self.validate_url(current_url, allowed_domains)
            response = client.get(
                current_url,
                headers=headers,
                stream=True,
                allow_redirects=False,
                timeout=(
                    float(os.getenv("OFFICIAL_SOURCE_REQUEST_TIMEOUT_SECONDS", "10")),
                    float(os.getenv("OFFICIAL_SOURCE_READ_TIMEOUT_SECONDS", "30")),
                ),
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                redirects += 1
                if redirects > self.limits.max_redirects:
                    response.close()
                    raise ValueError("too_many_redirects")
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ValueError("redirect_missing_location")
                current_url = urljoin(current_url, location)
                continue
            if response.status_code >= 400:
                response.close()
                raise ValueError(f"http_download_failed:{response.status_code}")
            return self._archive_response_stream(
                metadata,
                response,
                final_url=current_url,
                allowed_domains=allowed_domains,
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
                or ip.is_unspecified
                or str(ip) == "169.254.169.254"
            ):
                raise ValueError("blocked_private_or_metadata_ip")

    def _archive_response_stream(
        self,
        metadata: FilingMetadata,
        response: requests.Response,
        *,
        final_url: str,
        allowed_domains: tuple[str, ...],
    ) -> DownloadedArtifact:
        self.validate_url(final_url, allowed_domains)
        symbol = metadata.symbol.replace(".", "_")
        year = (metadata.publication_date or "unknown")[:4]
        safe_document_id = _safe_segment(metadata.source_document_id)
        raw_dir = self.settings.raw_data_dir / metadata.source_id / symbol / year / safe_document_id
        doc_dir = self.settings.documents_dir / metadata.source_id / symbol / year
        raw_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        total = 0
        prefix = b""
        fd, tmp_name = tempfile.mkstemp(prefix=".download.", dir=str(doc_dir))
        try:
            with os.fdopen(fd, "wb") as handle:
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self.limits.max_bytes:
                        raise ValueError("download_too_large")
                    if len(prefix) < 512:
                        prefix += chunk[: 512 - len(prefix)]
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())

            if _looks_like_html(prefix):
                raise ValueError("html_error_page")
            if (metadata.document_type or "").lower() == "pdf" and not prefix.startswith(b"%PDF"):
                raise ValueError("invalid_pdf_magic")
            sha256 = digest.hexdigest()
            suffix = ".pdf" if prefix.startswith(b"%PDF") else ".bin"
            final_path = doc_dir / f"{sha256}{suffix}"
            reused = final_path.exists()
            if reused:
                Path(tmp_name).unlink(missing_ok=True)
            else:
                os.replace(tmp_name, final_path)
            raw_metadata_path = raw_dir / "metadata.json"
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            raw_metadata_path.write_text(
                json.dumps(
                    {
                        "source_id": metadata.source_id,
                        "source_document_id": metadata.source_document_id,
                        "canonical_url": metadata.canonical_url,
                        "download_url": metadata.download_url,
                        "final_url": final_url,
                        "status_code": response.status_code,
                        "headers": _safe_headers(response.headers),
                        "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified"),
                        "content_length_header": response.headers.get("Content-Length"),
                        "content_type": content_type,
                        "content_length": total,
                        "sha256": sha256,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return DownloadedArtifact(
                source_id=metadata.source_id,
                source_document_id=metadata.source_document_id,
                final_path=final_path,
                raw_metadata_path=raw_metadata_path,
                sha256=sha256,
                content_type=content_type,
                content_length=total,
                file_magic=prefix[:8].decode("latin1", errors="ignore"),
                reused=reused,
            )
        finally:
            response.close()
            tmp_path = Path(tmp_name)
            if tmp_path.exists():
                tmp_path.unlink()


def _safe_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    cleaned = cleaned.strip("._")
    if not cleaned:
        raise ValueError("unsafe_path_segment")
    return cleaned[:160]


def _looks_like_html(prefix: bytes) -> bool:
    stripped = prefix.lstrip().lower()
    return stripped.startswith(b"<!doctype html") or stripped.startswith(b"<html")


def _safe_headers(headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, str]:
    blocked = {"cookie", "set-cookie", "authorization", "proxy-authorization"}
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in blocked and key.lower() in {"content-type", "content-length", "etag", "last-modified"}
    }
