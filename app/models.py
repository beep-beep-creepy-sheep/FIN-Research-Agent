from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3)
    allowed_domains: list[str] = Field(default_factory=list)
    include_agent_reach: bool = False
    as_of_date: str | None = None


class FinancialInputs(BaseModel):
    revenue: float | None = None
    gross_profit: float | None = None
    net_profit: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    equity_begin: float | None = None
    equity_end: float | None = None
    interest_bearing_debt: float | None = None
    cash: float | None = None


class DocumentMetadata(BaseModel):
    title: str
    source_path: str
    source_type: str = "local_file"
    issuer: str | None = None
    report_period: str | None = None
    publication_date: str | None = None
    currency: str | None = None
    unit: str | None = None
    url: str | None = None

    @classmethod
    def from_path(cls, path: Path) -> "DocumentMetadata":
        return cls(title=path.stem, source_path=str(path), source_type=path.suffix.lower().lstrip("."))


class DocumentChunk(BaseModel):
    document_id: int
    chunk_id: int
    text: str
    start_char: int
    end_char: int


class EvidenceSnippet(BaseModel):
    document_id: int
    chunk_id: int
    title: str
    source_path: str
    text: str
    score: float
    issuer: str | None = None
    report_period: str | None = None
    publication_date: str | None = None
    url: str | None = None

    @property
    def citation_label(self) -> str:
        detail = self.report_period or self.publication_date or self.source_path
        return f"{self.title} ({detail})"


class LocalResearchBrief(BaseModel):
    query: str
    generated_at: datetime
    as_of_date: date | None = None
    snippets: list[EvidenceSnippet]
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
