from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


SEC_BASE_URL = "https://data.sec.gov"


@dataclass(frozen=True)
class SECCompanyFactsClient:
    user_agent: str
    timeout_seconds: int = 30

    def get_company_facts(self, cik: str) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{normalized}.json"
        response = requests.get(
            url,
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            },
        )
        response.raise_for_status()
        return response.json()

    def extract_us_gaap_metric(
        self,
        facts: dict[str, Any],
        metric: str,
        *,
        unit: str = "USD",
        form: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        try:
            values = facts["facts"]["us-gaap"][metric]["units"][unit]
        except KeyError:
            return []

        filtered = [item for item in values if form is None or item.get("form") == form]
        filtered.sort(key=lambda item: (item.get("end", ""), item.get("filed", "")), reverse=True)
        return filtered[:limit]


def normalize_cik(cik: str) -> str:
    digits = "".join(character for character in cik if character.isdigit())
    if not digits:
        raise ValueError("CIK must contain at least one digit")
    if len(digits) > 10:
        raise ValueError("CIK cannot be longer than 10 digits")
    return digits.zfill(10)
