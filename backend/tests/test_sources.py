"""Tests for the TransactionSource seam.

The seam's value is contract enforcement: any connector that produces a
malformed ledger must fail loudly at the boundary, not corrupt scores
downstream. These tests pin that behavior.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.sources import CsvSource, LEDGER_COLUMNS, SourceError, TransactionSource


GOOD_CSV = b"""date,description,amount
2025-01-05,Client payment,8000
2025-02-04,Client payment,8400
2025-02-18,SBA loan payment,-1200
2025-03-05,Client payment,7900
"""


def test_csv_source_satisfies_the_contract():
    df = CsvSource(GOOD_CSV).validated()
    assert list(LEDGER_COLUMNS) == [c for c in LEDGER_COLUMNS if c in df.columns]
    assert len(df) == 4


def test_csv_source_wraps_parse_errors_as_source_error():
    with pytest.raises(SourceError, match="amount"):
        CsvSource(b"date,notes\n2025-01-01,hi\n").validated()


class _BuggyConnector(TransactionSource):
    """A hypothetical future connector that violates the schema."""

    def load(self) -> pd.DataFrame:
        return pd.DataFrame({"txn_date": [pd.Timestamp("2025-01-01")],
                             "amount": [100.0]})  # missing most columns


class _BadKindConnector(TransactionSource):
    def load(self) -> pd.DataFrame:
        return pd.DataFrame({
            "txn_date": [pd.Timestamp("2025-01-01")], "amount": [100.0],
            "direction": ["in"], "category": ["Sales"],
            "kind": ["mystery"], "counterparty": ["Someone"],
        })


def test_connector_missing_columns_fails_at_the_boundary():
    with pytest.raises(SourceError, match="connector bug"):
        _BuggyConnector().validated()


def test_connector_unknown_kind_fails_at_the_boundary():
    with pytest.raises(SourceError, match="mystery"):
        _BadKindConnector().validated()
