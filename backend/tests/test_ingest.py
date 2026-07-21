"""Tests for CSV ingestion — the messy-data handling the upload feature claims.

Each test feeds parse_transactions_csv the kind of file a real business would
actually export (QuickBooks-ish with categories, a bare bank statement, messy
currency formatting) and asserts we either parse it faithfully or fail with a
message a human can act on.
"""

from __future__ import annotations

import pytest

from app.ingest import IngestError, parse_transactions_csv


def _csv(text: str) -> bytes:
    """Dedent a triple-quoted CSV literal into bytes."""
    lines = [ln.strip() for ln in text.strip().splitlines()]
    return ("\n".join(lines)).encode()


BANK_EXPORT = _csv("""
    Posting Date,Description,Amount
    2025-01-05,Stripe payout,8000
    2025-01-20,"Payroll run",-5200
    2025-02-04,Stripe payout,8400
    2025-02-18,SBA loan payment,-1200
    2025-03-05,Stripe payout,7900
    2025-03-15,Office rent,-2000
""")


def test_parses_bare_bank_export_without_category_column():
    df = parse_transactions_csv(BANK_EXPORT)
    assert len(df) == 6
    # Sign-based inference: inflows -> revenue, outflows -> expense.
    assert (df.loc[df.amount > 0, "kind"] == "revenue").all()
    assert set(df.columns) >= {"txn_date", "amount", "direction", "kind",
                               "category", "counterparty"}


def test_loan_keyword_reclassifies_bare_export_rows():
    df = parse_transactions_csv(BANK_EXPORT)
    loan_rows = df[df["kind"] == "loan_payment"]
    assert len(loan_rows) == 1
    assert "SBA" in loan_rows.iloc[0]["counterparty"]


def test_category_column_wins_over_inference():
    df = parse_transactions_csv(_csv("""
        date,amount,category,description
        2025-01-01,5000,Income,Client payment
        2025-01-15,-900,Loan,Truck note
        2025-02-01,5100,Income,Client payment
        2025-02-15,-800,Expense,Fuel
        2025-03-01,5200,Income,Client payment
    """))
    assert (df.loc[df.amount > 0, "kind"] == "revenue").all()
    assert df.loc[df["counterparty"] == "Truck note", "kind"].iloc[0] == "loan_payment"


def test_currency_formatting_and_parens_negatives():
    df = parse_transactions_csv(_csv("""
        Date,Amount
        2025-01-01,"$1,234.56"
        2025-02-01,(500)
        2025-03-01,"$2,000.00"
    """))
    assert df["amount"].tolist() == [1234.56, -500.0, 2000.0]
    assert df["direction"].tolist() == ["in", "out", "in"]


def test_missing_amount_column_is_a_clear_error():
    with pytest.raises(IngestError, match="amount"):
        parse_transactions_csv(_csv("""
            date,description
            2025-01-01,hello
        """))


def test_bad_date_reports_the_row():
    with pytest.raises(IngestError, match="Row 3"):
        parse_transactions_csv(_csv("""
            date,amount
            2025-01-01,100
            not-a-date,200
            2025-03-01,300
        """))


def test_too_little_history_is_rejected():
    with pytest.raises(IngestError, match="3 months"):
        parse_transactions_csv(_csv("""
            date,amount
            2025-01-01,100
            2025-01-15,-50
        """))


def test_non_csv_bytes_rejected():
    with pytest.raises(IngestError):
        parse_transactions_csv(b"\x00\x01\x02 not a csv at all")
