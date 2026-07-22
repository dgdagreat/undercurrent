"""Tests for the what-if simulator's adjustment model.

The whole value of the feature is that each lever moves the factor it *should*
and nothing else, so the "which factors changed" panel stays honest. These
tests assert exactly that, using a real seeded ledger.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.generators import all_businesses
from app.scoring import score_business
from app.scoring.engine import InsufficientDataError
from app.scoring.whatif import Adjustments, apply_adjustments


def _ledger(profile="declining"):
    """A real generated business's ledger (declining: has revenue, expenses, loan)."""
    g = next(b for b in all_businesses() if b.profile_type == profile)
    tx = pd.DataFrame([
        dict(txn_date=t["txn_date"], amount=t["amount"], kind=t["kind"],
             direction=t["direction"])
        for t in g.transactions
    ])
    return tx, g.opening_balance


def _score(profile="declining", adj=None):
    tx, ob = _ledger(profile)
    as_of = pd.to_datetime(tx["txn_date"]).max()
    if adj is None:
        return score_business(tx, None, ob, as_of)
    tx2, ob2 = apply_adjustments(tx, ob, adj, as_of)
    return score_business(tx2, None, ob2, as_of)


def _f(result, name):
    return next(f for f in result.factors if f.name == name)


# --------------------------------------------------------------------------- #
def test_no_op_reproduces_baseline_exactly():
    base = _score()
    same = _score(adj=Adjustments())
    assert same.overall_score == base.overall_score
    assert same.grade == base.grade
    for b, s in zip(base.factors, same.factors):
        assert (b.name, b.sub_score, b.raw_value) == (s.name, s.sub_score, s.raw_value)


def test_opening_buffer_raises_runway_only():
    base = _score()
    adj = _score(adj=Adjustments(opening_buffer_delta=120_000))
    assert _f(adj, "runway").sub_score > _f(base, "runway").sub_score
    # Nothing else's raw metric should move — only balances changed.
    for name in ("revenue_stability", "trend", "debt_service", "expense_flexibility"):
        assert _f(adj, name).raw_value == _f(base, name).raw_value


def test_cash_injection_lifts_runway_not_revenue_factors():
    tx, ob = _ledger()
    months = pd.to_datetime(tx["txn_date"]).dt.to_period("M")
    trough_month = str(months.min())  # an early month, before the buffer builds
    base = _score()
    adj = _score(adj=Adjustments(cash_injection_amount=80_000,
                                 cash_injection_month=trough_month))
    assert _f(adj, "runway").sub_score >= _f(base, "runway").sub_score
    # Injection is a transfer, not revenue — stability/trend must not move.
    assert _f(adj, "revenue_stability").raw_value == _f(base, "revenue_stability").raw_value
    assert _f(adj, "trend").raw_value == _f(base, "trend").raw_value


def test_loan_reduction_helps_dscr_and_runway():
    base = _score()
    adj = _score(adj=Adjustments(loan_paydown_delta=-2_000))
    assert _f(adj, "debt_service").sub_score >= _f(base, "debt_service").sub_score
    assert _f(adj, "runway").sub_score >= _f(base, "runway").sub_score


def test_extra_paydown_lowers_runway_but_not_debt_service_metric():
    base = _score()
    adj = _score(adj=Adjustments(loan_paydown_delta=6_000))
    # Extra principal is modeled as a transfer out: it draws down cash...
    assert _f(adj, "runway").sub_score <= _f(base, "runway").sub_score
    # ...without changing the required debt-service obligation.
    assert _f(adj, "debt_service").raw_value == _f(base, "debt_service").raw_value


def test_expense_cut_helps_dscr_and_leaves_flexibility_unchanged():
    base = _score()
    adj = _score(adj=Adjustments(expense_reduction_pct=20))
    assert _f(adj, "debt_service").sub_score >= _f(base, "debt_service").sub_score
    # A uniform scale of every expense row leaves the revenue-expense
    # correlation (and thus expense flexibility) untouched.
    assert _f(adj, "expense_flexibility").raw_value == _f(base, "expense_flexibility").raw_value


def test_revenue_growth_raises_trend():
    base = _score()
    adj = _score(adj=Adjustments(revenue_growth_pct=25))
    assert _f(adj, "trend").sub_score > _f(base, "trend").sub_score


def test_levers_clamp_and_dont_crash():
    r = _score(adj=Adjustments(expense_reduction_pct=500, revenue_growth_pct=9999,
                               loan_paydown_delta=-10_000_000))
    assert 0 <= r.overall_score <= 100


def test_wiping_out_debt_flips_to_no_debt_branch():
    r = _score(adj=Adjustments(loan_paydown_delta=-1_000_000_000))
    assert _f(r, "debt_service").raw_value == "No debt service"
    assert 0 <= r.overall_score <= 100


def test_empty_ledger_is_unscoreable():
    empty = pd.DataFrame(columns=["txn_date", "amount", "kind", "direction"])
    tx2, ob2 = apply_adjustments(empty, 0.0, Adjustments(opening_buffer_delta=5), None)
    assert tx2.empty and ob2 == 5.0
    with pytest.raises(InsufficientDataError):
        score_business(tx2, None, ob2)
