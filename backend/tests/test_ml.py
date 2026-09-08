"""Tests for the ML risk model — features, labeled-data pipeline, and serving.

Kept fast: the dataset tests generate a small sample rather than the full 4,000.
The serving tests require a trained artifact (`python -m app.ml.train`); they
skip cleanly if it's absent so the suite passes on a fresh clone.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.generators import all_businesses
from app.ml import model as ml_model
from app.ml.dataset import _default_probability, build_dataset
from app.ml.features import FEATURE_NAMES, feature_row


def _frames(profile_type):
    g = next(b for b in all_businesses() if b.profile_type == profile_type)
    tx = pd.DataFrame([
        dict(txn_date=t["txn_date"], amount=t["amount"], kind=t["kind"],
             direction=t["direction"]) for t in g.transactions
    ])
    inv = pd.DataFrame(g.invoices) if g.invoices else None
    return tx, inv, g.opening_balance


# --------------------------------------------------------------------------- #
# Feature layer                                                               #
# --------------------------------------------------------------------------- #
def test_feature_row_has_full_finite_contract():
    tx, inv, ob = _frames("saas")
    row = feature_row(tx, inv, ob)
    assert list(row.keys()) == FEATURE_NAMES          # exact schema, in order
    assert all(math.isfinite(v) for v in row.values())


def test_features_are_deterministic():
    """Train/serve parity: the same ledger always yields the same vector."""
    tx, inv, ob = _frames("invoice")
    assert feature_row(tx, inv, ob) == feature_row(tx, inv, ob)


def test_features_separate_healthy_from_failing():
    saas = feature_row(*_frames("saas"))
    failing = feature_row(*_frames("restaurant"))
    # The failing restaurant should have a thinner trough and worse margin.
    assert saas["runway_trough_mo"] > failing["runway_trough_mo"]
    assert saas["operating_margin"] > failing["operating_margin"]


# --------------------------------------------------------------------------- #
# Labeled-data pipeline                                                       #
# --------------------------------------------------------------------------- #
def test_dataset_builds_with_sane_label_rate():
    df = build_dataset(n=300, seed=7)
    assert set(FEATURE_NAMES).issubset(df.columns)
    assert "default" in df.columns
    assert 0.08 < df["default"].mean() < 0.40      # not degenerate
    assert df[FEATURE_NAMES].notna().all().all()   # no NaN leaks into features


def test_default_probability_responds_to_fundamentals():
    healthy = dict(trend_annual=0.10, cost_ratio=0.40, fixed_frac=0.15,
                   loan_frac=0.02, opening_months=3.0, noise=0.04, erratic=0.0)
    risky = dict(trend_annual=-0.25, cost_ratio=0.55, fixed_frac=0.35,
                 loan_frac=0.14, opening_months=0.3, noise=0.10, erratic=0.0)
    assert _default_probability(risky) > _default_probability(healthy)
    assert 0.0 <= _default_probability(healthy) <= 1.0


# --------------------------------------------------------------------------- #
# Serving (needs a trained artifact)                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not ml_model.is_available(), reason="model not trained")
def test_predict_shape_and_bounds():
    r = ml_model.predict(*_frames("saas"))
    assert 0.0 <= r["default_prob"] <= 1.0
    assert r["risk_band"] in {"Very Low", "Low", "Moderate", "Elevated", "High"}
    assert len(r["contributions"]) == len(FEATURE_NAMES)
    # contributions sorted by |shap| descending
    mags = [abs(c["shap"]) for c in r["contributions"]]
    assert mags == sorted(mags, reverse=True)


@pytest.mark.skipif(not ml_model.is_available(), reason="model not trained")
def test_ml_ranks_failing_above_healthy():
    healthy = ml_model.predict(*_frames("fireworks"))["default_prob"]
    failing = ml_model.predict(*_frames("collections"))["default_prob"]
    assert failing > healthy
