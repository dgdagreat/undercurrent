"""What-if adjustments: reshape a ledger in memory, then rescore it.

The what-if simulator lets a reviewer ask "what would make this business
approvable?" by nudging five levers and watching the score move. This module is
the pure, framework-free core: it takes a transaction DataFrame + opening
balance, applies the adjustments, and returns a NEW frame + balance that the
existing `score_business` can score. It never touches the database.

The modeling choices below are deliberate — each lever is designed to move the
factor it *should* move and nothing else, so the "which factors changed" panel
stays honest:

  1. Revenue growth   — rotates the revenue trajectory around the latest month
                        (latest month unchanged), so it moves the TREND factor
                        without secretly changing today's cash position.
  2. Expense cut      — scales operating-expense rows down (helps DSCR + runway).
  3. Loan paydown     — reducing debt service scales down loan_payment rows
                        (helps DSCR + runway); *extra* principal is modeled as a
                        one-off transfer OUT per month (a use of cash), so it
                        shortens runway WITHOUT inflating required debt service.
  4. Cash injection   — a one-off transfer IN (not revenue), so it lifts the
                        end-balance / runway without polluting revenue stability
                        or trend.
  5. Opening buffer   — simply shifts the starting balance.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Adjustments:
    """The five what-if levers. All default to a no-op."""

    opening_buffer_delta: float = 0.0      # (a) $ added to / removed from opening balance
    cash_injection_amount: float = 0.0     # (b) one-off inflow $
    cash_injection_month: str | None = None  # (b) "YYYY-MM"; must be within the ledger
    loan_paydown_delta: float = 0.0        # (c) $/mo: <0 reduces debt service, >0 = extra principal
    expense_reduction_pct: float = 0.0     # (d) 0..90
    revenue_growth_pct: float = 0.0        # (e) annual %, clamped to [-50, 50]


def _months_present(df: pd.DataFrame) -> pd.PeriodIndex:
    return pd.PeriodIndex(df["txn_date"].dt.to_period("M").drop_duplicates().sort_values())


def _mid_month(period: pd.Period) -> pd.Timestamp:
    """A stable day-15 timestamp inside a month, for injected rows."""
    return pd.Timestamp(period.start_time) + pd.Timedelta(days=14)


def apply_adjustments(
    tx: pd.DataFrame, opening_balance: float, adj: Adjustments, as_of: pd.Timestamp
) -> tuple[pd.DataFrame, float]:
    """Return an adjusted (transactions, opening_balance) for rescoring.

    The input frame is not mutated. Rows keep the ledger schema (txn_date,
    amount, kind, direction, ...); appended rows fill the columns the scoring
    engine reads (txn_date, amount, kind) and a best-effort direction.
    """
    df = tx.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    if df.empty:
        return df, opening_balance + adj.opening_buffer_delta

    latest = df["txn_date"].dt.to_period("M").max()

    # 1. Revenue growth — rotate the trajectory around the latest month.
    g = max(-50.0, min(50.0, adj.revenue_growth_pct)) / 100.0
    rev_mask = df["kind"] == "revenue"
    if g != 0 and rev_mask.any():
        per = df.loc[rev_mask, "txn_date"].dt.to_period("M")
        months_back = (latest.year - per.dt.year) * 12 + (latest.month - per.dt.month)
        factor = (1.0 + g) ** (-months_back / 12.0)
        df.loc[rev_mask, "amount"] = df.loc[rev_mask, "amount"] * factor

    # 2. Expense reduction — scale operating-expense rows toward zero.
    pct = max(0.0, min(90.0, adj.expense_reduction_pct)) / 100.0
    if pct > 0:
        exp_mask = df["kind"] == "expense"
        df.loc[exp_mask, "amount"] = df.loc[exp_mask, "amount"] * (1.0 - pct)

    # 3. Loan paydown.
    d = adj.loan_paydown_delta
    if d < 0:
        # Reduce required debt service. Loan rows are negative; adding |d| makes
        # them less negative, clamped at 0 (a payment can't become a receipt).
        loan_mask = df["kind"] == "loan_payment"
        if loan_mask.any():
            df.loc[loan_mask, "amount"] = (
                df.loc[loan_mask, "amount"] + abs(d)
            ).clip(upper=0.0)
    elif d > 0:
        # Extra principal = a use of cash, one transfer OUT per month. Modeled as
        # a transfer (not loan_payment) so it doesn't inflate required debt
        # service — it only draws down the cash cushion.
        extra = pd.DataFrame(
            [
                {"txn_date": _mid_month(m), "amount": -abs(d),
                 "kind": "transfer", "direction": "out"}
                for m in _months_present(df)
            ]
        )
        df = pd.concat([df, extra], ignore_index=True)

    # 4. Cash injection — a one-off transfer IN, only if the month is in-window.
    if adj.cash_injection_amount and adj.cash_injection_month:
        try:
            p = pd.Period(adj.cash_injection_month, freq="M")
        except (ValueError, TypeError):
            p = None
        months = _months_present(df)
        if p is not None and p in months:
            inj = pd.DataFrame(
                [{"txn_date": _mid_month(p), "amount": abs(adj.cash_injection_amount),
                  "kind": "transfer", "direction": "in"}]
            )
            df = pd.concat([df, inj], ignore_index=True)

    # 5. Opening buffer.
    return df, opening_balance + adj.opening_buffer_delta
