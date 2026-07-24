"""The six explainable factors.

Each factor is a small pure function that takes prepared monthly data (and,
where relevant, the invoice table) and returns a `FactorResult`: a 0-100
sub-score plus the raw metric and a plain-English sentence. No factor is a
black box — you can read exactly why it landed where it did.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .decompose import annualized_trend_pct, predictability_cv


@dataclass
class FactorResult:
    name: str
    sub_score: float          # 0-100
    raw_value: str            # human-readable metric, e.g. "DSO 47 days"
    explanation: str
    applicable: bool = True   # False -> weight redistributed to other factors


def _piecewise(x: float, points: list[tuple[float, float]]) -> float:
    """Linear interpolation of `x` across (input, score) breakpoints.

    `points` must be sorted ascending by input. Values outside the range clamp
    to the nearest endpoint. This is how every raw metric maps onto 0-100 —
    transparent and easy to defend, no fitted coefficients.
    """
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + t * (y1 - y0)
    return points[-1][1]


# --------------------------------------------------------------------------- #
# 1. Revenue stability — judged on the *residual*, not raw revenue.            #
# --------------------------------------------------------------------------- #
def revenue_stability(monthly: pd.DataFrame) -> FactorResult:
    revenue = monthly["revenue"]
    # How *unpredictable* is revenue once you account for a repeatable seasonal
    # shape? Measured out-of-sample (does one year predict the next?) so a
    # genuinely erratic business can't hide behind an overfit season. See
    # decompose.predictability_cv for the full rationale.
    cv = predictability_cv(revenue)

    sub = _piecewise(
        cv, [(0.05, 100), (0.20, 90), (0.40, 70), (0.60, 45), (0.85, 15), (1.20, 0)])
    return FactorResult(
        name="revenue_stability",
        sub_score=sub,
        raw_value=f"{cv * 100:.0f}% unpredictable variation",
        explanation=(
            "Predictable swings — a seasonal peak that returns every year — don't "
            "count against the business; only variation that one year fails to "
            f"predict in the next does. That unpredictable share is {cv * 100:.0f}%."
        ),
    )


# --------------------------------------------------------------------------- #
# 2. Runway — worst-case months of buffer at the cash trough.                 #
# --------------------------------------------------------------------------- #
def runway(monthly: pd.DataFrame) -> FactorResult:
    avg_expense = monthly["total_outflow"].mean()
    min_balance = monthly["end_balance"].min()

    if avg_expense <= 0:
        worst_runway = 12.0
    else:
        worst_runway = float(min_balance / avg_expense)

    # Below zero means the account went into overdraft at some point -> heavy
    # penalty. The bar for a top score is deliberately demanding: two months of
    # cushion is merely solid (80), and it takes ~5 months to earn 100. A thin
    # sub-one-month buffer scores poorly. This is what keeps a healthy-but-not-
    # exceptional business off the top of the grade curve.
    sub = _piecewise(
        worst_runway,
        [(-1.0, 0), (0.0, 22), (0.5, 42), (1.0, 58), (2.0, 80), (3.5, 93), (5.0, 100)],
    )
    dipped = "dipped into overdraft" if min_balance < 0 else "held a positive buffer"
    return FactorResult(
        name="runway",
        sub_score=sub,
        raw_value=f"{worst_runway:.1f} mo at trough",
        explanation=(
            f"At its lowest point the business {dipped}, leaving roughly "
            f"{max(worst_runway, 0):.1f} months of total monthly outflows in "
            "reserve. This is measured at the seasonal low, not the average month."
        ),
    )


# --------------------------------------------------------------------------- #
# 3. Debt-service coverage (DSCR-style).                                       #
# --------------------------------------------------------------------------- #
def debt_service(monthly: pd.DataFrame) -> FactorResult:
    operating_cf = (monthly["revenue"] - monthly["operating_expense"]).mean()
    debt = monthly["loan_payment"].mean()

    if debt <= 0:
        return FactorResult(
            name="debt_service",
            sub_score=82.0,
            raw_value="No debt service",
            explanation=(
                "The business carries no scheduled loan repayments, so operating "
                "cash flow isn't committed to debt — low risk. (Not a perfect "
                "score: with no debt there's no demonstrated coverage history.)"
            ),
        )

    dscr = float(operating_cf / debt) if debt else 0.0
    sub = _piecewise(dscr, [(0.5, 0), (1.0, 55), (1.25, 75), (1.5, 90), (2.0, 100)])
    return FactorResult(
        name="debt_service",
        sub_score=sub,
        raw_value=f"DSCR {dscr:.2f}x",
        explanation=(
            f"Operating cash flow covers scheduled debt payments {dscr:.2f} times "
            "over. Comfortably above 1.25x is the conventional healthy threshold."
        ),
    )


# --------------------------------------------------------------------------- #
# 4. Receivables health — only applies to invoice-driven businesses.          #
# --------------------------------------------------------------------------- #
def receivables(invoices: pd.DataFrame, as_of) -> FactorResult:
    if invoices is None or invoices.empty:
        return FactorResult(
            name="receivables",
            sub_score=0.0,
            raw_value="Not applicable",
            explanation=(
                "This business is paid at the point of sale, so there are no "
                "outstanding receivables to age. This factor is excluded and its "
                "weight is redistributed across the others."
            ),
            applicable=False,
        )

    paid = invoices.dropna(subset=["paid_date"]).copy()
    if paid.empty:
        dso = 90.0
    else:
        lag = (paid["paid_date"] - paid["issued_date"]).dt.days
        dso = float(lag.mean())

    # Share of still-open invoices that are past their due date.
    open_inv = invoices[invoices["paid_date"].isna()]
    overdue_value = open_inv[open_inv["due_date"] < as_of]["amount"].sum()
    total_open = open_inv["amount"].sum()
    overdue_pct = float(overdue_value / total_open) if total_open > 0 else 0.0

    dso_score = _piecewise(dso, [(30, 100), (45, 82), (60, 62), (75, 40), (90, 20)])
    # Chronic overdue balances knock points off regardless of DSO.
    penalty = _piecewise(overdue_pct, [(0.0, 0), (0.15, 8), (0.35, 22), (0.60, 40)])
    sub = max(0.0, dso_score - penalty)
    return FactorResult(
        name="receivables",
        sub_score=sub,
        raw_value=f"DSO {dso:.0f} days, {overdue_pct * 100:.0f}% overdue",
        explanation=(
            f"Invoices are collected in about {dso:.0f} days on average, with "
            f"{overdue_pct * 100:.0f}% of open balances past due. Lumpy timing is "
            "fine as long as collection is reliable — that's what this measures."
        ),
    )


# --------------------------------------------------------------------------- #
# 5. Trend — deseasonalized growth direction.                                 #
# --------------------------------------------------------------------------- #
def trend(monthly: pd.DataFrame) -> FactorResult:
    growth = annualized_trend_pct(monthly["revenue"])
    sub = _piecewise(growth, [(-40, 0), (-20, 25), (-5, 55), (0, 70), (10, 90), (25, 100)])
    word = "growing" if growth > 2 else "declining" if growth < -2 else "flat"
    return FactorResult(
        name="trend",
        sub_score=sub,
        raw_value=f"{growth:+.0f}%/yr",
        explanation=(
            f"After removing seasonality, underlying revenue is {word} at about "
            f"{growth:+.0f}% a year. Seasonality can't disguise the direction of "
            "travel here."
        ),
    )


# --------------------------------------------------------------------------- #
# 6. Expense flexibility — do costs adapt when revenue falls?                  #
# --------------------------------------------------------------------------- #
def expense_flexibility(monthly: pd.DataFrame) -> FactorResult:
    rev = monthly["revenue"]
    exp = monthly["operating_expense"]
    if rev.std(ddof=0) == 0 or exp.std(ddof=0) == 0:
        corr = 0.0
    else:
        corr = float(np.corrcoef(rev, exp)[0, 1])

    # Costs that move with revenue cushion the troughs. Fixed-cost businesses
    # take a modest hit here (weight is only 10), which is fair: they rely on
    # revenue stability instead, which they're scored on elsewhere.
    sub = _piecewise(corr, [(-0.2, 35), (0.2, 55), (0.5, 75), (0.75, 92), (0.9, 100)])
    return FactorResult(
        name="expense_flexibility",
        sub_score=sub,
        raw_value=f"{corr:.2f} cost-revenue link",
        explanation=(
            f"Expenses track revenue with a correlation of {corr:.2f}. Costs that "
            "flex down in slow periods reduce the risk of a cash squeeze during "
            "the trough."
        ),
    )
