import pytest

from app.sec_client import SECCompanyFactsClient, normalize_cik


def test_normalize_cik() -> None:
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("CIK0000320193") == "0000320193"


def test_normalize_cik_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        normalize_cik("abc")


def test_extract_us_gaap_metric_filters_and_sorts() -> None:
    client = SECCompanyFactsClient(user_agent="test@example.com")
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"end": "2023-12-31", "filed": "2024-02-01", "form": "10-K", "val": 10},
                            {"end": "2024-12-31", "filed": "2025-02-01", "form": "10-K", "val": 12},
                            {"end": "2024-09-30", "filed": "2024-11-01", "form": "10-Q", "val": 8},
                        ]
                    }
                }
            }
        }
    }

    values = client.extract_us_gaap_metric(facts, "Revenues", form="10-K")

    assert [item["val"] for item in values] == [12, 10]
