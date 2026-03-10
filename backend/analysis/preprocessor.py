"""Transaction preprocessing: normalize, clean, and filter input data."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Iterable

from config import EXCLUDED_STOCK_CODES, MAX_REASONABLE_QUANTITY
from models.transaction import Transaction, UserTransactions


def parse_csv_transactions(csv_text: str, customer_id: str = "") -> UserTransactions:
    """Parse transactions from a CSV string (test data format).

    Expected columns: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    transactions: list[Transaction] = []

    for row in reader:
        stock_code = row.get("StockCode", "").strip()
        if stock_code.upper() in EXCLUDED_STOCK_CODES:
            continue

        try:
            quantity = int(float(row.get("Quantity", "1")))
        except (ValueError, TypeError):
            quantity = 1

        if abs(quantity) > MAX_REASONABLE_QUANTITY:
            continue

        try:
            unit_price = float(row.get("Price", "0"))
        except (ValueError, TypeError):
            unit_price = 0.0

        try:
            dt = datetime.fromisoformat(row.get("InvoiceDate", ""))
        except (ValueError, TypeError):
            continue

        transactions.append(Transaction(
            date=dt,
            description=row.get("Description", "").strip(),
            amount=round(quantity * unit_price, 2),
            quantity=quantity,
            unit_price=unit_price,
            country=row.get("Country", "").strip(),
            invoice=row.get("Invoice", "").strip(),
            stock_code=stock_code,
        ))

    cid = customer_id
    if not cid and transactions:
        cid = str(transactions[0].invoice)

    return UserTransactions(customer_id=cid, transactions=transactions)


def parse_json_transactions(
    records: list[dict], customer_id: str = ""
) -> UserTransactions:
    """Parse transactions from a list of JSON objects (production format).

    Minimum fields: date, description, amount.
    Optional: category, merchant, quantity, country, currency, invoice, stock_code.
    """
    transactions: list[Transaction] = []

    for rec in records:
        date_str = rec.get("date") or rec.get("InvoiceDate") or rec.get("invoice_date", "")
        try:
            dt = datetime.fromisoformat(str(date_str))
        except (ValueError, TypeError):
            continue

        amount = rec.get("amount")
        if amount is None:
            qty = rec.get("quantity", rec.get("Quantity", 1))
            price = rec.get("price", rec.get("Price", rec.get("unit_price", 0)))
            try:
                amount = round(float(qty) * float(price), 2)
            except (ValueError, TypeError):
                amount = 0.0
        else:
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                amount = 0.0

        try:
            quantity = int(float(rec.get("quantity", rec.get("Quantity", 1))))
        except (ValueError, TypeError):
            quantity = 1

        if abs(quantity) > MAX_REASONABLE_QUANTITY:
            continue

        stock_code = str(rec.get("stock_code", rec.get("StockCode", ""))).strip()
        if stock_code.upper() in EXCLUDED_STOCK_CODES:
            continue

        unit_price_raw = rec.get("unit_price", rec.get("Price"))
        unit_price = None
        if unit_price_raw is not None:
            try:
                unit_price = float(unit_price_raw)
            except (ValueError, TypeError):
                pass

        transactions.append(Transaction(
            date=dt,
            description=str(rec.get("description", rec.get("Description", ""))).strip(),
            amount=amount,
            category=str(rec.get("category", "")).strip(),
            merchant=str(rec.get("merchant", "")).strip(),
            quantity=quantity,
            unit_price=unit_price,
            country=str(rec.get("country", rec.get("Country", ""))).strip(),
            currency=str(rec.get("currency", "")).strip(),
            invoice=str(rec.get("invoice", rec.get("Invoice", ""))).strip(),
            stock_code=stock_code,
        ))

    return UserTransactions(customer_id=customer_id, transactions=transactions)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    iso_raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_raw)
    except (ValueError, TypeError):
        pass

    fmts = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y/%m/%d",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).strip().lower())


def _clean_numeric(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    txt = txt.replace(",", "").replace("$", "")
    if txt.startswith("(") and txt.endswith(")"):
        txt = f"-{txt[1:-1]}"
    return txt


def _build_portfolio_alias_lookup() -> dict[str, str]:
    field_aliases: dict[str, list[str]] = {
        "customer_id": ["customer_id", "customer id", "user_id", "user id", "userid", "client_id", "account_id", "member_id", "id"],
        "date": ["date", "transaction_date", "transaction date", "invoice_date", "invoice date", "posted_date", "posted date", "timestamp", "datetime"],
        "description": ["description", "memo", "narrative", "item", "item_name", "product", "product_name"],
        "amount": ["amount", "transaction_amount", "transaction amount", "total", "value", "line_total"],
        "quantity": ["quantity", "qty", "units", "count"],
        "unit_price": ["unit_price", "unit price", "price", "item_price"],
        "country": ["country", "country_code", "region"],
        "currency": ["currency", "currency_code", "ccy"],
        "invoice": ["invoice", "invoice_id", "invoice number", "order_id", "order number", "transaction_id", "reference"],
        "stock_code": ["stock_code", "stock code", "sku", "product_code", "item_code"],
        "merchant": ["merchant", "merchant_name", "vendor", "store"],
        "category": ["category", "category_name", "segment"],
    }

    alias_lookup: dict[str, str] = {}
    for canonical, aliases in field_aliases.items():
        for alias in aliases:
            alias_lookup[_normalize_key(alias)] = canonical
    return alias_lookup


def parse_portfolio_records_with_metadata(
    records: Iterable[dict],
    default_customer_id: str = "",
) -> tuple[dict[str, UserTransactions], int, list[str]]:
    """Parse uploaded portfolio rows from any iterable and return users + metadata."""
    alias_lookup = _build_portfolio_alias_lookup()
    grouped: dict[str, list[dict]] = {}
    row_count = 0
    field_names: set[str] = set()
    for row in records:
        if not isinstance(row, dict):
            continue
        row_count += 1
        for key in row.keys():
            field_names.add(str(key))
        normalized_row: dict[str, object] = {}
        for raw_key, raw_value in row.items():
            canonical = alias_lookup.get(_normalize_key(raw_key))
            if canonical:
                normalized_row[canonical] = raw_value

        dt = _parse_datetime(normalized_row.get("date"))
        if not dt:
            continue
        normalized_row["date"] = dt.isoformat()
        normalized_row["amount"] = _clean_numeric(normalized_row.get("amount"))
        normalized_row["quantity"] = _clean_numeric(normalized_row.get("quantity"))
        normalized_row["unit_price"] = _clean_numeric(normalized_row.get("unit_price"))

        customer_id = str(normalized_row.get("customer_id") or "").strip()
        if not customer_id:
            customer_id = str(default_customer_id).strip()
        if not customer_id:
            customer_id = str(normalized_row.get("invoice") or "").strip()
        if not customer_id:
            continue

        grouped.setdefault(customer_id, []).append({
            "date": normalized_row.get("date"),
            "description": normalized_row.get("description"),
            "amount": normalized_row.get("amount"),
            "quantity": normalized_row.get("quantity"),
            "unit_price": normalized_row.get("unit_price"),
            "country": normalized_row.get("country"),
            "currency": normalized_row.get("currency"),
            "invoice": normalized_row.get("invoice"),
            "stock_code": normalized_row.get("stock_code"),
            "merchant": normalized_row.get("merchant"),
            "category": normalized_row.get("category"),
        })

    users: dict[str, UserTransactions] = {}
    for cid, txns in grouped.items():
        parsed = parse_json_transactions(txns, customer_id=cid)
        if parsed.transactions:
            users[cid] = parsed
    return users, row_count, sorted(field_names)


def parse_portfolio_records(records: list[dict], default_customer_id: str = "") -> dict[str, UserTransactions]:
    """Parse uploaded portfolio rows with flexible column naming into users map."""
    if not records:
        return {}
    users, _, _ = parse_portfolio_records_with_metadata(records, default_customer_id=default_customer_id)
    return users


def load_test_user(customer_id: str) -> UserTransactions:
    """Load a test user's CSV — tries Firestore first, falls back to disk."""
    # Try Firestore (works in production where disk data is not available)
    try:
        from profile_generator.firestore_client import fs_load_test_user_csv
        csv_text = fs_load_test_user_csv(customer_id)
        if csv_text:
            return parse_csv_transactions(csv_text, customer_id=customer_id)
    except Exception:
        pass

    # Fall back to disk (local development)
    from config import TEST_USERS_DIR
    path = TEST_USERS_DIR / f"test-user-{customer_id}.csv"
    csv_text = path.read_text(encoding="utf-8")
    return parse_csv_transactions(csv_text, customer_id=customer_id)


def clean_transactions(user_txns: UserTransactions) -> UserTransactions:
    """Remove cancellations and zero-amount transactions for analysis."""
    clean = [
        t for t in user_txns.transactions
        if not t.is_cancellation and t.amount > 0
    ]
    return UserTransactions(customer_id=user_txns.customer_id, transactions=clean)
