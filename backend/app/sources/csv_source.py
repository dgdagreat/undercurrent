"""CSV file upload — the first TransactionSource.

Thin adapter: all the actual parsing intelligence (header aliases, currency
cleanup, category inference, loan-keyword classification) lives in
`app.ingest`; this class just gives it the TransactionSource shape so the
upload endpoint consumes it through the same seam a Plaid or QuickBooks
connector would use.
"""

from __future__ import annotations

import pandas as pd

from ..ingest import IngestError, parse_transactions_csv
from .base import SourceError, TransactionSource


class CsvSource(TransactionSource):
    """A user-uploaded transactions CSV (bank export, accounting export...)."""

    def __init__(self, raw: bytes):
        self._raw = raw

    def load(self) -> pd.DataFrame:
        try:
            return parse_transactions_csv(self._raw)
        except IngestError as e:
            # Re-raise under the seam's error type so callers only ever have
            # to catch SourceError, whatever the connector.
            raise SourceError(str(e)) from e
