"""Pydantic response models — the JSON contract the React app consumes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BusinessSummary(BaseModel):
    id: int
    name: str
    industry: str
    profile_type: str
    description: str
    overall_score: float
    grade: str
    risk_tier: str
    recommendation: str


class FactorOut(BaseModel):
    factor_name: str
    label: str
    sub_score: float
    weight: float
    contribution: float
    raw_value: str
    direction: str
    explanation: str


class CashflowPoint(BaseModel):
    month: str          # "YYYY-MM"
    revenue: float
    expenses: float
    net: float
    end_balance: float


class ScoreOut(BaseModel):
    overall_score: float
    grade: str
    risk_tier: str
    recommendation: str
    as_of: date
    factors: list[FactorOut]


class BusinessDetail(BaseModel):
    id: int
    name: str
    industry: str
    profile_type: str
    description: str
    founded_date: date
    opening_balance: float
    score: ScoreOut
    cashflow: list[CashflowPoint]


class WhatIfRequest(BaseModel):
    """The five what-if levers; every field defaults to a no-op."""

    opening_buffer_delta: float = 0.0
    cash_injection_amount: float = 0.0
    cash_injection_month: str | None = None
    loan_paydown_delta: float = 0.0
    expense_reduction_pct: float = 0.0
    revenue_growth_pct: float = 0.0


class WhatIfResponse(BaseModel):
    # baseline is recomputed fresh (not the cached ScoreRun) so it lines up
    # exactly with `adjusted` — same code path, same as_of — and the UI can diff
    # them cleanly.
    baseline: ScoreOut
    adjusted: ScoreOut
    cashflow: list[CashflowPoint]


class MlContribution(BaseModel):
    feature: str
    label: str
    value: float
    shap: float           # log-odds push (+ toward default, - away)
    direction: str        # "increases" | "decreases"


class MlPrediction(BaseModel):
    """The learned model's second opinion, alongside the rule-based score."""

    default_prob: float
    risk_band: str
    base_rate: float      # population default rate (for context)
    roc_auc: float | None  # the model's held-out AUC (for context)
    contributions: list[MlContribution]
