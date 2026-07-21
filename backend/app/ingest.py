"""CSV ingestion: turn a user-uploaded transaction export into ledger rows.

Design goal: accept the files businesses actually have. A QuickBooks export, a
raw bank-statement download, or a hand-kept spreadsheet all look slightly
different, so this module is deliberately forgiving:

  - Header names are matched flexibly ("Date"/"txn_date"/"Posting Date" all
    work; same for amount/description/category).
  - Only two columns are required: a date and a signed amount
    (positive = money in, negative = money out).
  - `category` is optional. When present it drives classification; when absent
    we infer: inflows are revenue, outflows are expenses, and a light keyword
    pass on the description catches loan payments so the debt-service factor
    still works on bare bank exports. (Real alternative-data lenders do exactly
    this kind of transaction classification on bank feeds.)

Errors are raised as IngestError with messages meant to be shown to the user
verbatim — "row 17: could not parse date '13/45/2025'" beats a stack trace.
"""

from __future__ import annotations

import io
import re

import pandas as pd

# Maximum upload we'll parse. Far above any real 24-month ledger, low enough to
# keep a bad file from tying up the demo server.
MAX_ROWS = 100_000

# Flexible header matching: canonical name -> accepted spellings (lowercased,
# non-alphanumerics stripped, so "Posting Date" == "posting_date").
_HEADER_ALIASES = {
    "txn_date": {"date", "txndate", "transactiondate", "postingdate", "postdate"},
    "amount": {"amount", "amt", "value", "transactionamount"},
    "description": {"description", "desc", "memo", "details", "name", "payee",
                    "counterparty"},
    "category": {"category", "type", "kind", "transactiontype"},
}

# Category values (from a CSV's category column) -> ledger `kind`.
_CATEGORY_TO_KIND = {
    "revenue": "revenue", "income": "revenue", "sales": "revenue",
    "deposit": "revenue",
    "expense": "expense", "expenses": "expense", "cost": "expense",
    "loan": "loan_payment", "loanpayment": "loan_payment",
    "debt": "loan_payment", "debtservice": "loan_payment",
    "ownerdraw": "owner_draw", "draw": "owner_draw", "distribution": "owner_draw",
    "transfer": "transfer",
}

# Description keywords that flag a debit as a loan payment when no category
# column exists. Deliberately conservative — false "loan" labels would
# understate DSCR, so match only unambiguous terms.
_LOAN_PATTERN = re.compile(
    r"\b(?:loan|sba|principal|debt service|equipment finance|amortization)\b",
    re.IGNORECASE,
)


class IngestError(ValueError):
    """A user-facing problem with the uploaded file (bad columns, bad rows)."""


def _canon(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower())


def _map_headers(columns) -> dict[str, str]:
    """Map canonical names -> actual column names present in the file."""
    mapped: dict[str, str] = {}
    for col in columns:
        c = _canon(str(col))
        for canonical, aliases in _HEADER_ALIASES.items():
            if c in aliases and canonical not in mapped:
                mapped[canonical] = col
    return mapped


def parse_transactions_csv(raw: bytes) -> pd.DataFrame:
    """Parse uploaded CSV bytes into the ledger schema.

    Returns a DataFrame with columns: txn_date (Timestamp), amount (float,
    signed), direction (in|out), category (str), kind (str), counterparty (str).

    Raises IngestError with a user-facing message on any problem.
    """
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise IngestError(
            "Couldn't read the file as CSV. Export your transactions as a "
            "plain .csv file and try again."
        )

    if df.empty:
        raise IngestError("The file has no transaction rows.")
    if len(df) > MAX_ROWS:
        raise IngestError(f"File too large — max {MAX_ROWS:,} rows.")

    headers = _map_headers(df.columns)
    missing = [c for c in ("txn_date", "amount") if c not in headers]
    if missing:
        raise IngestError(
            "Missing required column(s): "
            + ", ".join("date" if m == "txn_date" else m for m in missing)
            + ". The file needs at least a date column and a signed amount "
            "column (positive = money in, negative = money out)."
        )

    out = pd.DataFrame()

    # Dates — report the first offending row, not a pandas traceback.
    dates = pd.to_datetime(df[headers["txn_date"]], errors="coerce",
                           format="mixed", dayfirst=False)
    if dates.isna().any():
        bad = int(dates.isna().idxmax())
        raise IngestError(
            f"Row {bad + 2}: could not parse date "
            f"'{df[headers['txn_date']].iloc[bad]}'."
        )
    out["txn_date"] = dates

    # Amounts — strip currency formatting ("$1,234.56", "(500)" for negatives).
    amt_raw = (
        df[headers["amount"]].astype(str)
        .str.replace(r"[$,\s]", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    )
    amounts = pd.to_numeric(amt_raw, errors="coerce")
    if amounts.isna().any():
        bad = int(amounts.isna().idxmax())
        raise IngestError(
            f"Row {bad + 2}: could not parse amount "
            f"'{df[headers['amount']].iloc[bad]}'."
        )
    if (amounts == 0).all():
        raise IngestError("Every amount in the file is zero.")
    out["amount"] = amounts.astype(float).round(2)
    out["direction"] = (out["amount"] >= 0).map({True: "in", False: "out"})

    # Description → counterparty (best-effort; purely cosmetic in the UI).
    if "description" in headers:
        out["counterparty"] = (
            df[headers["description"]].fillna("Uploaded transaction").astype(str)
            .str.slice(0, 120)
        )
    else:
        out["counterparty"] = "Uploaded transaction"

    # Classification: explicit category column wins; otherwise infer.
    if "category" in headers:
        cat = df[headers["category"]].fillna("").astype(str).map(_canon)
        kind = cat.map(_CATEGORY_TO_KIND)
        # Unknown category values fall through to sign-based inference.
        kind = kind.where(kind.notna(),
                          out["direction"].map({"in": "revenue", "out": "expense"}))
        out["category"] = df[headers["category"]].fillna("Uncategorized").astype(str)
    else:
        kind = out["direction"].map({"in": "revenue", "out": "expense"})
        out["category"] = out["direction"].map(
            {"in": "Revenue", "out": "Expense"})

    # Keyword pass: outflows that look like loan payments get reclassified so
    # DSCR works even on a bare bank export. Only applies where the category
    # column didn't already say otherwise.
    looks_like_loan = (
        (out["direction"] == "out")
        & (kind == "expense")
        & out["counterparty"].str.contains(_LOAN_PATTERN)
    )
    kind = kind.mask(looks_like_loan, "loan_payment")
    out.loc[looks_like_loan, "category"] = "Loan payment"
    out["kind"] = kind

    # Sanity: enough history for a meaningful score (the engine wants trend +
    # seasonality context; 3 months is the floor for a not-embarrassing answer).
    months = out["txn_date"].dt.to_period("M").nunique()
    if months < 3:
        raise IngestError(
            f"Only {months} month(s) of history found — at least 3 months of "
            "transactions are needed to compute a meaningful score (24 is ideal)."
        )
    if not (out["amount"] > 0).any():
        raise IngestError("No inflows found — every row is an outflow.")

    return out.sort_values("txn_date").reset_index(drop=True)
