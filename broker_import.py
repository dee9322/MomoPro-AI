from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from broker_models import BrokerExecution, BrokerImportRecord, stable_execution_id, utc_now


COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": ("symbol", "ticker", "code", "instrument", "stock"),
    "side": ("side", "action", "buy/sell", "transaction type", "type"),
    "quantity": ("filled quantity", "filled qty", "quantity", "qty", "shares", "executed quantity"),
    "price": ("average price", "avg price", "filled price", "execution price", "price", "avg. price"),
    "executed_at": ("filled time", "execution time", "filled date", "trade date", "date/time", "date", "time"),
    "order_id": ("order id", "order number", "order no", "order#"),
    "execution_id": ("execution id", "trade id", "fill id", "transaction id"),
    "status": ("status", "order status"),
    "fees": ("fees", "fee", "commission", "commissions", "transaction fee", "regulatory fees"),
    "account_id": ("account", "account id", "account number"),
    "currency": ("currency",),
}

FILLED_STATUSES = {"filled", "fully filled", "executed", "complete", "completed", "partial filled", "partially filled"}
BUY_VALUES = {"buy", "b", "bought", "buy to cover", "buytocover"}
SELL_VALUES = {"sell", "s", "sold", "sell short", "short", "sellshort"}


def _norm_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _find_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized = {_norm_header(column): column for column in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    for normalized_name, original in normalized.items():
        if any(alias in normalized_name for alias in aliases):
            return original
    return None


def _decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_dataframe(data: bytes) -> pd.DataFrame:
    text = _decode_csv_bytes(data)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        separator = dialect.delimiter
    except csv.Error:
        separator = ","
    return pd.read_csv(io.StringIO(text), sep=separator, dtype=str, keep_default_na=False)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", "."}:
        return None
    try:
        number = float(text)
        return -number if negative else number
    except ValueError:
        return None


def _datetime(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().astimezone(timezone.utc).isoformat(timespec="seconds")


def _normalize_side(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    compact = text.replace(" ", "")
    if text in BUY_VALUES or compact in BUY_VALUES:
        return "BUY"
    if text in SELL_VALUES or compact in SELL_VALUES:
        return "SELL"
    if "buy" in text:
        return "BUY"
    if "sell" in text or "short" in text:
        return "SELL"
    return None


def preview_webull_csv(data: bytes, filename: str = "webull.csv") -> dict[str, Any]:
    try:
        df = _read_dataframe(data)
    except Exception as error:
        return {"ok": False, "error": f"Could not read the CSV: {error}", "rows": [], "columns": []}

    columns = list(df.columns)
    mapping = {key: _find_column(columns, aliases) for key, aliases in COLUMN_ALIASES.items()}
    required_missing = [key for key in ("symbol", "side", "quantity", "price", "executed_at") if not mapping.get(key)]
    if required_missing:
        return {
            "ok": False,
            "error": "Missing required columns: " + ", ".join(required_missing),
            "rows": [],
            "columns": columns,
            "mapping": mapping,
        }

    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for index, row in df.iterrows():
        raw = {str(column): row.get(column, "") for column in columns}
        symbol = str(row.get(mapping["symbol"], "")).strip().upper()
        side = _normalize_side(row.get(mapping["side"]))
        quantity = _number(row.get(mapping["quantity"]))
        price = _number(row.get(mapping["price"]))
        executed_at = _datetime(row.get(mapping["executed_at"]))
        status = str(row.get(mapping.get("status"), "Filled") if mapping.get("status") else "Filled").strip()

        if mapping.get("status") and status.lower() not in FILLED_STATUSES and "fill" not in status.lower() and "execut" not in status.lower():
            skipped.append(f"Row {index + 2}: status '{status}' is not a filled execution.")
            continue
        if not symbol or not side or not quantity or quantity <= 0 or not price or price <= 0 or not executed_at:
            skipped.append(f"Row {index + 2}: missing or invalid symbol, side, quantity, price, or execution time.")
            continue

        order_id = str(row.get(mapping.get("order_id"), "") if mapping.get("order_id") else "").strip()
        execution_id = str(row.get(mapping.get("execution_id"), "") if mapping.get("execution_id") else "").strip()
        fees = _number(row.get(mapping.get("fees"))) if mapping.get("fees") else 0.0
        account_id = str(row.get(mapping.get("account_id"), "") if mapping.get("account_id") else "").strip()
        currency = str(row.get(mapping.get("currency"), "USD") if mapping.get("currency") else "USD").strip() or "USD"
        fingerprint = stable_execution_id("Webull", account_id, execution_id, order_id, symbol, side, quantity, price, executed_at)

        rows.append(
            {
                "fingerprint": fingerprint,
                "broker": "Webull",
                "account_id": account_id,
                "order_id": order_id,
                "execution_id": execution_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "price": float(price),
                "executed_at": executed_at,
                "fees": float(fees or 0.0),
                "currency": currency,
                "status": status or "Filled",
                "source_file": filename,
                "raw": raw,
            }
        )

    return {
        "ok": True,
        "error": None,
        "rows": rows,
        "columns": columns,
        "mapping": mapping,
        "skipped": skipped,
        "rows_seen": len(df),
    }


def build_import(data: bytes, filename: str, existing_fingerprints: set[str]) -> tuple[BrokerImportRecord, list[BrokerExecution]]:
    preview = preview_webull_csv(data, filename)
    if not preview.get("ok"):
        raise ValueError(preview.get("error") or "The CSV could not be imported.")

    record = BrokerImportRecord(source_file=filename, rows_seen=int(preview.get("rows_seen") or 0))
    executions: list[BrokerExecution] = []
    for item in preview.get("rows", []):
        if item["fingerprint"] in existing_fingerprints:
            record.duplicates_skipped += 1
            continue
        item["import_id"] = record.id
        executions.append(BrokerExecution(**item))
        existing_fingerprints.add(item["fingerprint"])
    record.rows_imported = len(executions)
    record.rows_skipped = len(preview.get("skipped", []))
    record.errors = list(preview.get("skipped", []))[:100]
    return record, executions
