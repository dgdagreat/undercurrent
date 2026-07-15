"""REST endpoints backing the dashboard.

Two routes: a list of businesses with their headline score, and a per-business
detail bundle (full factor breakdown + monthly cash-flow series for the chart).
Scores are read from the cached score tables the seed script populated.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api", tags=["businesses"])

# Friendly labels for the six factor keys, used in the UI.
FACTOR_LABELS = {
    "runway": "Cash Runway (trough)",
    "revenue_stability": "Revenue Stability",
    "trend": "Growth Trend",
    "debt_service": "Debt Service Coverage",
    "receivables": "Receivables Health",
    "expense_flexibility": "Expense Flexibility",
}


def _latest_run(db: Session, business_id: int) -> models.ScoreRun | None:
    stmt = (
        select(models.ScoreRun)
        .where(models.ScoreRun.business_id == business_id)
        .order_by(models.ScoreRun.computed_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _cashflow_series(biz: models.Business) -> list[schemas.CashflowPoint]:
    """Monthly revenue / expenses / net / end-of-month balance for the chart."""
    rows = [
        dict(txn_date=t.txn_date, amount=t.amount, kind=t.kind)
        for t in biz.transactions
    ]
    df = pd.DataFrame(rows)
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["month"] = df["txn_date"].dt.to_period("M")

    revenue = df.loc[df["kind"] == "revenue"].groupby("month")["amount"].sum()
    expenses = -df.loc[df["amount"] < 0].groupby("month")["amount"].sum()

    running = biz.opening_balance + df.sort_values("txn_date").set_index("txn_date")["amount"].cumsum()
    end_balance = running.resample("ME").last().ffill()
    end_balance.index = end_balance.index.to_period("M")

    months = pd.period_range(df["month"].min(), df["month"].max(), freq="M")
    points = []
    for m in months:
        rev = float(revenue.get(m, 0.0))
        exp = float(expenses.get(m, 0.0))
        points.append(schemas.CashflowPoint(
            month=str(m), revenue=round(rev, 2), expenses=round(exp, 2),
            net=round(rev - exp, 2), end_balance=round(float(end_balance.get(m, 0.0)), 2),
        ))
    return points


def _score_out(run: models.ScoreRun) -> schemas.ScoreOut:
    factors = [
        schemas.FactorOut(
            factor_name=f.factor_name,
            label=FACTOR_LABELS.get(f.factor_name, f.factor_name),
            sub_score=f.sub_score, weight=f.weight, contribution=f.contribution,
            raw_value=f.raw_value, direction=f.direction, explanation=f.explanation,
        )
        for f in run.factors
    ]
    return schemas.ScoreOut(
        overall_score=run.overall_score, grade=run.grade, risk_tier=run.risk_tier,
        recommendation=run.recommendation, as_of=run.as_of_date, factors=factors,
    )


@router.get("/businesses", response_model=list[schemas.BusinessSummary])
def list_businesses(db: Session = Depends(get_db)):
    out = []
    for biz in db.scalars(select(models.Business).order_by(models.Business.id)):
        run = _latest_run(db, biz.id)
        if run is None:
            continue
        out.append(schemas.BusinessSummary(
            id=biz.id, name=biz.name, industry=biz.industry,
            profile_type=biz.profile_type, description=biz.description,
            overall_score=run.overall_score, grade=run.grade,
            risk_tier=run.risk_tier, recommendation=run.recommendation,
        ))
    return out


@router.get("/businesses/{business_id}", response_model=schemas.BusinessDetail)
def get_business(business_id: int, db: Session = Depends(get_db)):
    biz = db.get(models.Business, business_id)
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")
    run = _latest_run(db, business_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No score for business")

    return schemas.BusinessDetail(
        id=biz.id, name=biz.name, industry=biz.industry,
        profile_type=biz.profile_type, description=biz.description,
        founded_date=biz.founded_date, opening_balance=biz.opening_balance,
        score=_score_out(run), cashflow=_cashflow_series(biz),
    )
