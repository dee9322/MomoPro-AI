from __future__ import annotations

from typing import Any

import requests


def get_fda_enforcement(company_name: str | None, limit: int = 8) -> dict[str, Any]:
    if not company_name:
        return {"status": "Unavailable", "records": []}

    search_name = company_name.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip()
    if len(search_name) < 3:
        return {"status": "Unavailable", "records": []}

    params = {
        "search": f'recalling_firm:"{search_name}"',
        "limit": limit,
        "sort": "report_date:desc",
    }
    response = requests.get(
        "https://api.fda.gov/drug/enforcement.json",
        params=params,
        timeout=20,
    )

    if response.status_code == 404:
        return {"status": "Available", "records": []}
    response.raise_for_status()

    records = []
    for item in response.json().get("results", []):
        records.append(
            {
                "report_date": item.get("report_date"),
                "classification": item.get("classification"),
                "status": item.get("status"),
                "reason": item.get("reason_for_recall"),
                "product": item.get("product_description"),
                "firm": item.get("recalling_firm"),
            }
        )

    return {"status": "Available", "records": records}
