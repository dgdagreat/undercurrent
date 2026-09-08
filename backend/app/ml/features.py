"""Feature engineering — the ML model's view of a business's ledger.

The single source of truth for turning a 24-month transaction ledger into a
fixed feature vector. Both training (dataset.py) and serving (model.py) call
`feature_row`, so a business is described identically whether it's a synthetic
training example or a live one being scored — no train/serve skew.

Features deliberately reuse the same cash-flow signals the rule-based engine
computes (runway, DSCR, out-of-sample predictability, deseasonalized trend,
expense elasticity) plus a few raw aggregates the rules don't use directly
(coefficient of variation, months in overdraft, operating margin, leverage).
That overlap is intentional: it lets us ask whether a learned model, given the
same evidence, reaches the same conclusions as the hand-built rules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..scoring import decompose
from ..scoring.engine import prepare_monthly

# The feature contract: order matters (the model is trained on this order) and
# is the schema shared by training and serving. Keep additions append-only.
FEATURE_NAMES = [
    "runway_trough_mo",
    "current_runway_mo",
    "dscr",
    "debt_to_revenue",
    "operating_margin",
    "revenue_cv",
    "predictability_cv",
    "trend_pct",
    "expense_rev_corr",
    "months_negative",
    "seasonality_strength",
    "log_avg_revenue",
    "has_receivables",
    "dso_days",
]

# Human-readable labels for the UI / explanations.
FEATURE_LABELS = {
    "runway_trough_mo": "Runway at trough (months)",
    "current_runway_mo": "Current runway (months)",
    "dscr": "Debt-service coverage (DSCR)",
    "debt_to_revenue": "Debt payments ÷ revenue",
    "operating_margin": "Operating margin",
    "revenue_cv": "Raw revenue volatility",
    "predictability_cv": "Unpredictable revenue variation",
    "trend_pct": "Deseasonalized growth (%/yr)",
    "expense_rev_corr": "Expense-to-revenue elasticity",
    "months_negative": "Months in overdraft",
    "seasonality_strength": "Seasonality strength",
    "log_avg_revenue": "Business scale (log revenue)",
    "has_receivables": "Has receivables",
    "dso_days": "Days sales outstanding",
}

# Sentinel for coverage when a business carries no debt (division by zero). A
# high-but-finite value keeps tree splits well-behaved and reads as "very safe".
_NO_DEBT_DSCR = 12.0
_DSCR_CAP = 12.0


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return float(a / b) if b not in (0, 0.0) and not pd.isna(b) else default


def feature_row(
    transactions: pd.DataFrame,
    invoices: pd.DataFrame | None,
    opening_balance: float,
    as_of: pd.Timestamp | None = None,
) -> dict[str, float]:
    """Extract the fixed feature vector (as a dict in FEATURE_NAMES order)."""
    tx = transactions.copy()
    tx["txn_date"] = pd.to_datetime(tx["txn_date"])
    if as_of is None:
        as_of = tx["txn_date"].max()
    monthly = prepare_monthly(tx, opening_balance, pd.Timestamp(as_of))

    revenue = monthly["revenue"]
    opex = monthly["operating_expense"]
    outflow = monthly["total_outflow"]
    loan = monthly["loan_payment"]
    end_bal = monthly["end_balance"]

    avg_rev = float(revenue.mean())
    avg_out = float(outflow.mean())
    avg_loan = float(loan.mean())
    operating_cf = float((revenue - opex).mean())

    # Coverage / leverage.
    dscr = _NO_DEBT_DSCR if avg_loan <= 0 else min(_safe_div(operating_cf, avg_loan), _DSCR_CAP)
    debt_to_rev = _safe_div(avg_loan, avg_rev)

    # Cushion.
    runway_trough = _safe_div(float(end_bal.min()), avg_out)
    current_runway = _safe_div(float(end_bal.iloc[-1]), avg_out)
    months_negative = int((end_bal < 0).sum())

    # Profitability + volatility.
    operating_margin = _safe_div(operating_cf, avg_rev)
    revenue_cv = _safe_div(float(revenue.std(ddof=0)), avg_rev, default=0.0)
    predictability_cv = float(decompose.predictability_cv(revenue))
    trend_pct = float(decompose.annualized_trend_pct(revenue))

    # Cost elasticity (how much expenses move with revenue).
    if revenue.std(ddof=0) == 0 or opex.std(ddof=0) == 0:
        expense_corr = 0.0
    else:
        expense_corr = float(np.corrcoef(revenue, opex)[0, 1])

    # Seasonality strength: share of (seasonal+residual) variance that is the
    # repeatable seasonal component.
    d = decompose.decompose_monthly(revenue)
    seas_var = float(np.nanvar(d.seasonal.to_numpy()))
    resid_var = float(np.nanvar(d.residual.to_numpy()))
    seasonality_strength = _safe_div(seas_var, seas_var + resid_var, default=0.0)

    # Receivables (invoice businesses only).
    has_receivables = 0.0
    dso_days = 0.0
    if invoices is not None and not invoices.empty:
        inv = invoices.copy()
        inv["issued_date"] = pd.to_datetime(inv["issued_date"])
        inv["paid_date"] = pd.to_datetime(inv["paid_date"])
        paid = inv.dropna(subset=["paid_date"])
        if not paid.empty:
            has_receivables = 1.0
            dso_days = float((paid["paid_date"] - paid["issued_date"]).dt.days.mean())

    row = {
        "runway_trough_mo": runway_trough,
        "current_runway_mo": current_runway,
        "dscr": dscr,
        "debt_to_revenue": debt_to_rev,
        "operating_margin": operating_margin,
        "revenue_cv": revenue_cv,
        "predictability_cv": predictability_cv,
        "trend_pct": trend_pct,
        "expense_rev_corr": expense_corr,
        "months_negative": float(months_negative),
        "seasonality_strength": seasonality_strength,
        "log_avg_revenue": float(np.log1p(max(avg_rev, 0.0))),
        "has_receivables": has_receivables,
        "dso_days": dso_days,
    }
    # Guard against NaN/inf leaking into the model.
    return {k: (0.0 if not np.isfinite(row[k]) else round(row[k], 6)) for k in FEATURE_NAMES}


def feature_vector(*args, **kwargs) -> np.ndarray:
    """Same as feature_row but as an ordered numpy array (model input)."""
    row = feature_row(*args, **kwargs)
    return np.array([row[name] for name in FEATURE_NAMES], dtype=float)
