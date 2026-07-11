from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests


SEC_HEADERS = {
    "User-Agent": "MomoProAI/0.3 dbardwell9322@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}


@lru_cache(maxsize=1)
def _ticker_map() -> dict[str, dict[str, Any]]:
    response = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=SEC_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    raw = response.json()
    return {
        str(item["ticker"]).upper(): {
            "cik": str(item["cik_str"]).zfill(10),
            "title": item["title"],
        }
        for item in raw.values()
    }


def get_company_identity(symbol: str) -> dict[str, Any] | None:
    return _ticker_map().get(symbol.strip().upper())


def get_recent_filings(symbol: str, limit: int = 12) -> dict[str, Any]:
    identity = get_company_identity(symbol)
    if not identity:
        return {"status": "Unavailable", "company": None, "filings": []}

    response = requests.get(
        f'https://data.sec.gov/submissions/CIK{identity["cik"]}.json',
        headers=SEC_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    recent = payload.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    important_forms = {"8-K", "10-K", "10-Q", "S-1", "S-3", "424B5", "DEF 14A", "4"}
    filings = []
    for index, form in enumerate(forms):
        if form not in important_forms:
            continue
        accession = accessions[index]
        accession_no_dash = accession.replace("-", "")
        document = primary_docs[index]
        filings.append(
            {
                "form": form,
                "date": dates[index],
                "description": descriptions[index] or form,
                "url": (
                    f'https://www.sec.gov/Archives/edgar/data/{int(identity["cik"])}/'
                    f'{accession_no_dash}/{document}'
                ),
            }
        )
        if len(filings) >= limit:
            break

    return {
        "status": "Available",
        "company": identity["title"],
        "cik": identity["cik"],
        "filings": filings,
    }
