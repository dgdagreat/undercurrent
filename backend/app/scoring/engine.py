"""Scoring orchestration: raw ledger in, explained score out.

`score_business` is the single public entry point. It takes plain DataFrames
(so it's trivial to test without a database), aggregates the ledger into a
monthly view, runs the six factors, renormalizes weights over whichever factors
apply, and rolls everything up into an overall score, grade, risk tier and an
Approve / Review / Decline recommendation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from . import config, factors
from .factors import FactorResult


@dataclass
class ScoredFactor:
    name: str
    sub_score: float
    weight: float          # renormalized weight actually used
    contribution: float    # sub_score * weight / 100
    raw_value: str
    direction: str
    explanation: str


@dataclass
class ScoreResult:
    overall_score: float
    grade: str
    risk_tier: str
    recommendation: str
    as_of: str
    factors: list[ScoredFactor] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


def prepare_monthly(
    transactions: pd.DataFrame, opening_balance: float, as_of: pd.Timestamp
) -> pd.DataFrame:
    """Aggregate the transaction ledger into one row per month.

    Columns: revenue, operating_expense, loan_payment, total_outflow,
    end_balance. Balances are the cumulative sum of every signed transaction, so
    they reflect the real trough — including owner draws and loan payments — not
    just operating flows.
    """
    df = transactions.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df = df.sort_values("txn_date")
    df["month"] = df["txn_date"].dt.to_period("M")

    def monthly_sum(mask, sign=1):
        s = (sign * df.loc[mask, "amount"]).groupby(df.loc[mask, "month"]).sum()
        return s

    revenue = monthly_sum(df["kind"] == "revenue")
    operating_expense = monthly_sum(df["kind"] == "expense", sign=-1)
    loan_payment = monthly_sum(df["kind"] == "loan_payment", sign=-1)
    total_outflow = monthly_sum(df["amount"] < 0, sign=-1)

    # Month-end running balance across the whole ledger.
    running = opening_balance + df.set_index("txn_date")["amount"].cumsum()
    end_balance = running.resample("ME").last().ffill()
    end_balance.index = end_balance.index.to_period("M")

    # Assemble on a continuous monthly index (fill gap months with zero flow).
    all_months = pd.period_range(df["month"].min(), df["month"].max(), freq="M")
    monthly = pd.DataFrame(index=all_months)
    monthly["revenue"] = revenue.reindex(all_months).fillna(0.0)
    monthly["operating_expense"] = operating_expense.reindex(all_months).fillna(0.0)
    monthly["loan_payment"] = loan_payment.reindex(all_months).fillna(0.0)
    monthly["total_outflow"] = total_outflow.reindex(all_months).fillna(0.0)
    monthly["end_balance"] = end_balance.reindex(all_months).ffill().bfill()

    # Use a timestamp index so decomposition can read .index.month.
    monthly.index = all_months.to_timestamp(how="end").normalize()

    # Restrict to the trailing lookback window ending in the as_of *month*.
    # Compare by month, not raw timestamp: the index holds month-END dates
    # (e.g. Jun 30) while as_of is usually a mid-month transaction date
    # (e.g. Jun 22), so a naive `index <= as_of` would silently drop the most
    # recent month — losing a full month of history and misaligning the
    # year-over-year comparison in the stability factor.
    as_of_month = as_of.to_period("M")
    monthly = monthly[monthly.index.to_period("M") <= as_of_month]
    monthly = monthly.tail(config.LOOKBACK_MONTHS)
    return monthly


def _grade_for(score: float):
    for cutoff, grade, tier, rec in config.GRADE_BANDS:
        if score >= cutoff:
            return grade, tier, rec
    return "E", "High", "Decline"


def _direction(sub_score: float) -> str:
    if sub_score >= config.DIRECTION_HELPED:
        return "helped"
    if sub_score <= config.DIRECTION_HURT:
        return "hurt"
    return "neutral"


#: Columns the scoring engine requires on the transactions frame.
REQUIRED_TX_COLUMNS = ("txn_date", "amount", "kind")


class InsufficientDataError(ValueError):
    """Raised when there isn't enough ledger history to produce a score.

    A business with no transactions isn't *risky* (a score of 0 / Decline would
    be misleading) — it's simply unscoreable. Callers should surface this as
    "insufficient data" (e.g. an HTTP 422), not as a low score or a 500.
    """


def score_business(
    transactions: pd.DataFrame,
    invoices: pd.DataFrame | None,
    opening_balance: float,
    as_of: pd.Timestamp | None = None,
) -> ScoreResult:
    """Compute the full explained score for one business.

    Raises:
        InsufficientDataError: if `transactions` is empty.
        ValueError: if `transactions` is missing a required column.
    """
    if transactions is None or transactions.empty:
        raise InsufficientDataError("no transactions to score")
    missing = [c for c in REQUIRED_TX_COLUMNS if c not in transactions.columns]
    if missing:
        raise ValueError(f"transactions missing required column(s): {missing}")

    tx = transactions.copy()
    tx["txn_date"] = pd.to_datetime(tx["txn_date"])
    if as_of is None:
        as_of = tx["txn_date"].max()
    as_of = pd.Timestamp(as_of)

    monthly = prepare_monthly(tx, opening_balance, as_of)

    inv = None
    if invoices is not None and not invoices.empty:
        inv = invoices.copy()
        for col in ("issued_date", "due_date", "paid_date"):
            inv[col] = pd.to_datetime(inv[col])

    # Run every factor.
    results: list[FactorResult] = [
        factors.revenue_stability(monthly),
        factors.runway(monthly),
        factors.debt_service(monthly),
        factors.receivables(inv, as_of),
        factors.trend(monthly),
        factors.expense_flexibility(monthly),
    ]

    # Renormalize weights across the factors that actually apply.
    applicable = [r for r in results if r.applicable]
    total_weight = sum(config.WEIGHTS[r.name] for r in applicable)
    # Defensive: five of the six factors are always applicable, so this can't
    # happen today — but guard anyway so a future refactor that makes every
    # factor conditional fails loudly instead of dividing by zero.
    if total_weight == 0:
        raise InsufficientDataError("no applicable scoring factors")

    scored: list[ScoredFactor] = []
    overall = 0.0
    for r in results:
        if not r.applicable:
            scored.append(
                ScoredFactor(
                    name=r.name, sub_score=r.sub_score, weight=0.0, contribution=0.0,
                    raw_value=r.raw_value, direction="neutral", explanation=r.explanation,
                )
            )
            continue
        weight = config.WEIGHTS[r.name] / total_weight * 100.0
        contribution = r.sub_score * weight / 100.0
        overall += contribution
        scored.append(
            ScoredFactor(
                name=r.name, sub_score=round(r.sub_score, 1), weight=round(weight, 1),
                contribution=round(contribution, 1), raw_value=r.raw_value,
                direction=_direction(r.sub_score), explanation=r.explanation,
            )
        )

    overall = round(overall, 1)
    grade, tier, rec = _grade_for(overall)

    # Order the breakdown to lead with what the reviewer needs to see first:
    # excluded (not-applicable) factors sink to the bottom; among the rest,
    # score-dragging factors surface first (hurt, then neutral, then helped),
    # and within each group the heavier-weighted factor comes first. Sorting by
    # raw contribution would do the opposite — it would bury the factors that
    # hurt the score, which are exactly the ones a "why this score" panel exists
    # to explain.
    _dir_rank = {"hurt": 0, "neutral": 1, "helped": 2}
    scored.sort(key=lambda f: (f.weight == 0, _dir_rank[f.direction], -f.weight))

    return ScoreResult(
        overall_score=overall, grade=grade, risk_tier=tier, recommendation=rec,
        as_of=as_of.date().isoformat(), factors=scored,
    )
