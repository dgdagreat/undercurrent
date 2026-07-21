"""The TransactionSource contract.

A source's one job: produce a DataFrame of normalized ledger rows. The schema
below is the platform's lingua franca — the same shape the scoring engine and
the Transaction table already speak, so a source's output flows straight
through `services.score_and_cache` untouched.

Why an abstract class for what is currently one implementation: the seam *is*
the design statement. In production this platform would ingest from Plaid, an
accounting package, or a POS system; each of those is a `load()` implementation
plus whatever auth it needs, and nothing else changes. The contract is enforced
here (`validated()`), so a misbehaving connector fails loudly at the boundary
instead of corrupting scores downstream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

# The normalized ledger schema every source must produce:
#   txn_date     pandas Timestamp
#   amount       float, signed (positive = inflow)
#   direction    "in" | "out"  (redundant with sign; kept for readability)
#   category     display label, e.g. "Payroll"
#   kind         revenue | expense | loan_payment | owner_draw | transfer
#   counterparty display string for the UI
LEDGER_COLUMNS = ("txn_date", "amount", "direction", "category", "kind",
                  "counterparty")

_VALID_KINDS = {"revenue", "expense", "loan_payment", "owner_draw", "transfer"}


class SourceError(ValueError):
    """A user-facing problem with a source's input (bad file, failed fetch).

    Messages are shown to the user verbatim, so write them for humans.
    """


class TransactionSource(ABC):
    """Anything that can yield a normalized transaction ledger."""

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Fetch/parse and return rows in the LEDGER_COLUMNS schema.

        Raise SourceError with a human-readable message on any input problem.
        """

    def validated(self) -> pd.DataFrame:
        """load(), then enforce the contract. Call this, not load(), from app code."""
        df = self.load()
        missing = [c for c in LEDGER_COLUMNS if c not in df.columns]
        if missing:
            raise SourceError(
                f"{type(self).__name__} produced an invalid ledger — missing "
                f"column(s): {', '.join(missing)}. This is a connector bug, "
                "not a problem with your data."
            )
        bad_kinds = set(df["kind"].unique()) - _VALID_KINDS
        if bad_kinds:
            raise SourceError(
                f"{type(self).__name__} produced unknown transaction kind(s): "
                f"{', '.join(sorted(map(str, bad_kinds)))}. This is a connector "
                "bug, not a problem with your data."
            )
        return df
