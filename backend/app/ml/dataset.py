"""Synthetic labeled-data pipeline for the risk model.

Real default outcomes don't exist for fictional businesses, so we manufacture a
*defensible* learning problem instead of a circular one:

  1. Sample a business's latent fundamentals (trend, margin, leverage, cushion,
     volatility, seasonal archetype) from realistic distributions.
  2. Build a noisy 24-month ledger from those fundamentals.
  3. Compute a latent 12-month default probability from the *clean* fundamentals
     (a documented logistic function) and draw the binary label from it —
     stochastically. Two identical-looking businesses can land on different
     outcomes, exactly as in real credit.
  4. Extract the model's features from the *noisy ledger* (features.feature_row).

The model therefore never sees the clean fundamentals — only noisy estimates of
them — and the label carries irreducible Bernoulli noise on top. That caps
achievable accuracy well below 100% and makes AUC, calibration, and SHAP all
meaningful, rather than the model trivially re-deriving a rule.

Run:  python -m app.ml.dataset          # writes app/ml/data/training.csv
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..generators import END_DATE, MONTHS, _day, _month_starts, _tx
from .features import FEATURE_NAMES, feature_row

DATA_DIR = Path(__file__).resolve().parent / "data"
DATASET_PATH = DATA_DIR / "training.csv"

# Seasonal archetypes (Jan..Dec revenue multipliers). "erratic" and "invoice"
# are handled specially below.
_ARCHETYPES = {
    "flat": {m: 1.0 for m in range(1, 13)},
    "summer": {1: .3, 2: .3, 3: .5, 4: .8, 5: 1.2, 6: 1.6, 7: 1.8, 8: 1.6, 9: 1.1, 10: .7, 11: .4, 12: .35},
    "winter": {1: 1.7, 2: 1.6, 3: 1.3, 4: .6, 5: .3, 6: .2, 7: .2, 8: .2, 9: .3, 10: .6, 11: 1.1, 12: 1.6},
    "holiday": {1: .7, 2: .7, 3: .8, 4: .85, 5: .9, 6: .9, 7: .9, 8: .9, 9: 1.0, 10: 1.15, 11: 1.5, 12: 1.7},
    "spiky": {1: .1, 2: .1, 3: .15, 4: .25, 5: .4, 6: .6, 7: .5, 8: .7, 9: 1.3, 10: 2.6, 11: .5, 12: .2},
}
_ARCHETYPE_WEIGHTS = {
    "flat": 0.28, "summer": 0.20, "winter": 0.14, "holiday": 0.14,
    "spiky": 0.10, "erratic": 0.08, "invoice": 0.06,
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _seasonal_for(name: str, month: int, rng: np.random.RandomState) -> float:
    if name == "erratic":
        return max(0.05, rng.uniform(0.1, 2.0))  # no pattern at all
    if name == "invoice":
        return 1.0  # smooth delivery; lumpiness comes from payment timing
    return _ARCHETYPES[name][month]


def _sample_business(rng: np.random.RandomState):
    """Sample fundamentals + build a noisy ledger. Returns (tx, inv, opening, fund)."""
    archetype = rng.choice(list(_ARCHETYPE_WEIGHTS), p=list(_ARCHETYPE_WEIGHTS.values()))
    base = float(np.exp(rng.normal(math.log(55_000), 0.5)))          # scale
    trend_mo = float(np.clip(rng.normal(1.0, 0.014), 0.955, 1.045))   # monthly growth
    cost_ratio = float(rng.uniform(0.32, 0.62))                       # variable cost share
    fixed_frac = float(rng.uniform(0.10, 0.45))                       # fixed cost / base rev
    has_loan = rng.random() < 0.55
    loan_frac = float(rng.uniform(0.02, 0.16)) if has_loan else 0.0   # loan / base rev
    opening_months = float(rng.uniform(0.1, 4.0))                     # cushion
    noise = float(rng.uniform(0.02, 0.08))
    if archetype == "erratic":
        noise = float(rng.uniform(0.30, 0.62))

    months = _month_starts(MONTHS, END_DATE)
    fixed_cost = fixed_frac * base
    loan_pay = loan_frac * base

    # Rough avg outflow to size the opening cushion.
    approx_out = base * (cost_ratio + fixed_frac) + loan_pay
    opening = opening_months * approx_out

    txns: list[dict] = []
    invoices: list[dict] = []
    from datetime import timedelta

    for i, ms in enumerate(months):
        growth = trend_mo ** i
        mult = _seasonal_for(archetype, ms.month, rng) * (1 + rng.normal(0, noise))
        revenue = max(0.0, base * growth * mult)

        if archetype == "invoice":
            # Deliver smoothly; pay lumpily 30-70 days later.
            n = rng.randint(4, 9)
            for _ in range(n):
                amt = revenue / n
                issued = _day(ms, int(rng.randint(2, 26)))
                terms = int(rng.choice([30, 45, 60]))
                due = issued + timedelta(days=terms)
                lag = terms + int(rng.randint(-8, 30))
                paid = issued + timedelta(days=max(12, lag))
                if paid <= END_DATE:
                    invoices.append(dict(issued_date=issued, due_date=due, paid_date=paid, amount=amt, status="paid"))
                    txns.append(_tx(paid, amt, "in", "Invoice", "revenue", "Clients"))
                else:
                    invoices.append(dict(issued_date=issued, due_date=due, paid_date=None, amount=amt, status="outstanding"))
        else:
            txns.append(_tx(_day(ms, 8), revenue * 0.5, "in", "Sales", "revenue", "Customers"))
            txns.append(_tx(_day(ms, 22), revenue * 0.5, "in", "Sales", "revenue", "Customers"))

        txns.append(_tx(_day(ms, 15), -revenue * cost_ratio, "out", "Variable costs", "expense", "Suppliers"))
        txns.append(_tx(_day(ms, 1), -fixed_cost, "out", "Fixed overhead", "expense", "Overhead"))
        if loan_pay:
            txns.append(_tx(_day(ms, 5), -loan_pay, "out", "Loan", "loan_payment", "Lender"))

    fund = dict(
        trend_annual=trend_mo ** 12 - 1.0,
        cost_ratio=cost_ratio, fixed_frac=fixed_frac,
        loan_frac=loan_frac, opening_months=opening_months, noise=noise,
        erratic=1.0 if archetype == "erratic" else 0.0,
        base=base,
    )
    inv_df = pd.DataFrame(invoices) if invoices else None
    return pd.DataFrame(txns), inv_df, opening, fund


def _clip01(x: float, hi: float = 1.0) -> float:
    return float(min(hi, max(0.0, x)))


def _default_probability(fund: dict) -> float:
    """Latent 12-month default probability from CLEAN fundamentals.

    A transparent (mostly logistic) function of the real risk drivers, plus two
    *interaction* terms — a decline is far more dangerous when the cushion is
    also thin; a thin margin is far more dangerous when the business is also
    leveraged. Those interactions are what a tree model can capture and a linear
    baseline can't, so the headline gradient-boosting model earns its edge
    honestly. The model never sees these fundamentals — only noisy ledger
    estimates of them — which caps achievable accuracy and keeps the problem
    realistic. Coefficients are tuned for a ~20% population default rate.
    """
    op_margin = 1.0 - fund["cost_ratio"] - fund["fixed_frac"]        # ~ -0.1 .. 0.5
    dscr = 12.0 if fund["loan_frac"] <= 0 else min(op_margin / fund["loan_frac"], 12.0)

    # Normalized 0..1-ish risk drivers.
    decline = _clip01(-fund["trend_annual"] / 0.30, 1.3)
    thin_cushion = _clip01((1.6 - fund["opening_months"]) / 1.6)
    low_margin = _clip01((0.16 - op_margin) / 0.30)
    bleeding = _clip01(-op_margin / 0.20)
    weak_dscr = _clip01((1.6 - min(dscr, 4.0)) / 1.6)
    leveraged = _clip01(fund["loan_frac"] / 0.12)

    risk = (
        1.6 * decline
        + 1.4 * thin_cushion
        + 1.3 * low_margin
        + 0.8 * weak_dscr
        + 2.2 * fund["noise"]
        + 0.5 * fund["erratic"]
        + 3.8 * decline * thin_cushion      # interaction: decline AND thin cushion
        + 3.2 * bleeding * leveraged        # interaction: bleeding AND leveraged
    )
    logit = -3.9 + 1.9 * risk
    return _sigmoid(logit)


def build_dataset(n: int = 4000, seed: int = 20240501) -> pd.DataFrame:
    """Generate `n` labeled businesses as a features + `default` DataFrame."""
    rng = np.random.RandomState(seed)
    rows = []
    for _ in range(n):
        tx, inv, opening, fund = _sample_business(rng)
        try:
            feats = feature_row(tx, inv, opening)
        except Exception:
            continue  # skip degenerate ledgers
        p = _default_probability(fund)
        # Bernoulli draw — the irreducible label noise.
        label = int(rng.random() < p)
        feats["default_prob_true"] = round(p, 4)  # kept for diagnostics, dropped before training
        feats["default"] = label
        rows.append(feats)
    return pd.DataFrame(rows, columns=FEATURE_NAMES + ["default_prob_true", "default"])


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = build_dataset()
    df.to_csv(DATASET_PATH, index=False)
    rate = df["default"].mean()
    print(f"Wrote {len(df):,} rows to {DATASET_PATH}")
    print(f"Default rate: {rate:.1%}  |  features: {len(FEATURE_NAMES)}")
