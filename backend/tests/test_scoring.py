"""Sanity tests for the scoring engine and the fairness claim.

The headline test is `test_seasonal_not_penalized_for_seasonality`: it proves the
whole thesis — a purely seasonal revenue series must NOT be scored as unstable,
because the seasonal swing is removed before the stability factor looks at it.

Run with:  python -m pytest   (from the backend/ directory)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.generators import all_businesses
from app.scoring import score_business
from app.scoring.decompose import decompose_monthly
from app.scoring.engine import InsufficientDataError
from app.scoring.factors import _piecewise


# --------------------------------------------------------------------------- #
# Decomposition + piecewise helpers                                           #
# --------------------------------------------------------------------------- #
def test_piecewise_clamps_and_interpolates():
    pts = [(0, 0), (10, 100)]
    assert _piecewise(-5, pts) == 0        # clamp low
    assert _piecewise(15, pts) == 100      # clamp high
    assert _piecewise(5, pts) == 50        # midpoint


def test_decomposition_recovers_seasonal_pattern():
    # 24 months of a pure sine season on a flat trend -> residual ~ 0.
    idx = pd.date_range("2024-01-31", periods=24, freq="ME")
    season = 1000 * np.sin(2 * np.pi * idx.month / 12)
    series = pd.Series(5000 + season, index=idx)
    d = decompose_monthly(series)
    # Residual should be tiny relative to the seasonal amplitude.
    assert d.residual.dropna().abs().max() < 150


# --------------------------------------------------------------------------- #
# The fairness claim                                                          #
# --------------------------------------------------------------------------- #
def _monthly_revenue_txns(monthly_values, start="2024-07-31"):
    idx = pd.date_range(start, periods=len(monthly_values), freq="ME")
    rows = []
    for d, v in zip(idx, monthly_values):
        rows.append(dict(txn_date=d, amount=v, kind="revenue", direction="in"))
        rows.append(dict(txn_date=d, amount=-v * 0.7, kind="expense", direction="out"))
    return pd.DataFrame(rows)


def test_seasonal_not_penalized_for_seasonality():
    """The core thesis: a clean seasonal business must NOT be scored as unstable.

    We take a strongly seasonal revenue series and compare what a *naive*
    model (raw coefficient of variation) would conclude against what our
    decomposition-based factor concludes. The naive view sees huge volatility
    and would fail the business; ours removes the predictable seasonal swing
    and sees a stable underlying business — a high score.
    """
    months = 24
    idx = pd.date_range("2024-07-31", periods=months, freq="ME")
    seasonal_vals = 50_000 + 40_000 * np.sin(2 * np.pi * idx.month / 12)

    from app.scoring.factors import _piecewise, revenue_stability
    from app.scoring.engine import prepare_monthly

    monthly = prepare_monthly(
        _monthly_revenue_txns(seasonal_vals), 100_000, pd.Timestamp(idx[-1]))

    # What a naive raw-volatility model would score (same mapping, no decomposition).
    rev = monthly["revenue"]
    naive_cv = float(rev.std(ddof=0) / rev.mean())
    naive_score = _piecewise(
        naive_cv, [(0.05, 100), (0.15, 85), (0.30, 60), (0.50, 30), (0.80, 0)])

    # What our seasonality-aware factor scores.
    ours = revenue_stability(monthly).sub_score

    assert naive_cv > 0.4          # the raw series really is highly variable
    assert naive_score < 40        # a naive model would penalize it hard
    assert ours > 80               # ours sees a stable underlying business
    assert ours > naive_score + 40  # and the gap is large — that's the fairness win


# --------------------------------------------------------------------------- #
# End-to-end on the seeded demo businesses                                    #
# --------------------------------------------------------------------------- #
def _score_of(profile_type):
    gen = next(b for b in all_businesses() if b.profile_type == profile_type)
    tx = pd.DataFrame([
        dict(txn_date=t["txn_date"], amount=t["amount"], kind=t["kind"],
             direction=t["direction"]) for t in gen.transactions
    ])
    inv = pd.DataFrame(gen.invoices) if gen.invoices else None
    return score_business(tx, inv, gen.opening_balance)


def test_all_profiles_score_in_valid_range():
    for profile in ("saas", "seasonal", "invoice", "declining"):
        r = _score_of(profile)
        assert 0 <= r.overall_score <= 100
        assert len(r.factors) == 6


def test_saas_outscores_declining():
    assert _score_of("saas").overall_score > _score_of("declining").overall_score


def test_declining_is_the_weakest_profile():
    scores = {p: _score_of(p).overall_score for p in
              ("saas", "seasonal", "invoice", "declining")}
    assert scores["declining"] == min(scores.values())


def test_invoice_business_uses_receivables_factor():
    r = _score_of("invoice")
    receivables = next(f for f in r.factors if f.name == "receivables")
    assert receivables.weight > 0  # applicable and weighted


def test_cash_only_business_drops_receivables():
    r = _score_of("saas")
    receivables = next(f for f in r.factors if f.name == "receivables")
    assert receivables.weight == 0  # not applicable -> weight redistributed


# --------------------------------------------------------------------------- #
# Robustness: empty ledger, bad input, and breakdown ordering                 #
# --------------------------------------------------------------------------- #
def test_empty_transactions_raises_insufficient_data():
    """A business with no ledger is unscoreable, not risky — clear error, no crash."""
    empty = pd.DataFrame(columns=["txn_date", "amount", "kind", "direction"])
    with pytest.raises(InsufficientDataError):
        score_business(empty, None, 0.0)
    with pytest.raises(InsufficientDataError):
        score_business(None, None, 0.0)


def test_missing_required_column_raises_valueerror():
    bad = pd.DataFrame([{"txn_date": "2025-01-01", "amount": 100}])  # no 'kind'
    with pytest.raises(ValueError, match="required column"):
        score_business(bad, None, 0.0)


def test_breakdown_orders_hurts_before_helps_and_excludes_last():
    """The 'why this score' panel must surface drags first and excluded factors
    last — never bury a hurting factor beneath the ones that helped."""
    result = _score_of("declining")  # a borderline business with a real drag
    dirs = [f.direction for f in result.factors if f.weight > 0]
    # No 'helped' factor may appear before a 'hurt' factor.
    if "hurt" in dirs and "helped" in dirs:
        assert dirs.index("hurt") < dirs.index("helped")
    # Excluded (weight 0) factors are always at the end.
    weights = [f.weight for f in result.factors]
    zeros = [i for i, w in enumerate(weights) if w == 0]
    assert all(i >= len(weights) - len(zeros) for i in zeros)
