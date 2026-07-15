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
