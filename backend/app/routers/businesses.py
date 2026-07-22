"""REST endpoints backing the dashboard.

Two routes: a list of businesses with their headline score, and a per-business
detail bundle (full factor breakdown + monthly cash-flow series for the chart).
Scores are read from the cached score tables the seed script populated.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..scoring import config, score_business, whatif
from ..scoring.engine import InsufficientDataError, ScoreResult
from ..services import frames_for

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


def cashflow_points_from_frame(
    tx: pd.DataFrame, opening_balance: float
) -> list[schemas.CashflowPoint]:
    """Monthly revenue / expenses / net / end-balance, clipped to the score window.

    Runs on any ledger DataFrame (a business's own, or a what-if-adjusted one).
    Balances are cumulative over the WHOLE ledger, but the series is clipped to
    the trailing `LOOKBACK_MONTHS` — the same window the scoring engine uses —
    so the chart only ever shows months that actually informed the score.
    """
    if tx is None or tx.empty:
        return []
    df = tx.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["month"] = df["txn_date"].dt.to_period("M")

    revenue = df.loc[df["kind"] == "revenue"].groupby("month")["amount"].sum()
    expenses = -df.loc[df["amount"] < 0].groupby("month")["amount"].sum()

    running = opening_balance + df.sort_values("txn_date").set_index("txn_date")["amount"].cumsum()
    end_balance = running.resample("ME").last().ffill()
    end_balance.index = end_balance.index.to_period("M")

    months = pd.period_range(df["month"].min(), df["month"].max(), freq="M")
    months = months[-config.LOOKBACK_MONTHS:]  # match the scoring window
    points = []
    for m in months:
        rev = float(revenue.get(m, 0.0))
        exp = float(expenses.get(m, 0.0))
        points.append(schemas.CashflowPoint(
            month=str(m), revenue=round(rev, 2), expenses=round(exp, 2),
            net=round(rev - exp, 2), end_balance=round(float(end_balance.get(m, 0.0)), 2),
        ))
    return points


def _cashflow_series(biz: models.Business) -> list[schemas.CashflowPoint]:
    """The chart series for a persisted business."""
    if not biz.transactions:
        return []
    tx = pd.DataFrame([
        dict(txn_date=t.txn_date, amount=t.amount, kind=t.kind)
        for t in biz.transactions
    ])
    return cashflow_points_from_frame(tx, biz.opening_balance)


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


def _score_out_from_result(result: ScoreResult) -> schemas.ScoreOut:
    """Map a freshly-computed ScoreResult (dataclass) to the API's ScoreOut."""
    factors = [
        schemas.FactorOut(
            factor_name=f.name,
            label=FACTOR_LABELS.get(f.name, f.name),
            sub_score=f.sub_score, weight=f.weight, contribution=f.contribution,
            raw_value=f.raw_value, direction=f.direction, explanation=f.explanation,
        )
        for f in result.factors
    ]
    return schemas.ScoreOut(
        overall_score=result.overall_score, grade=result.grade,
        risk_tier=result.risk_tier, recommendation=result.recommendation,
        as_of=date.fromisoformat(result.as_of), factors=factors,
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


@router.post("/businesses/{business_id}/whatif", response_model=schemas.WhatIfResponse)
def simulate_whatif(
    business_id: int, req: schemas.WhatIfRequest, db: Session = Depends(get_db)
):
    """Recompute the score under hypothetical adjustments — READ-ONLY.

    Reconstructs the ledger in memory with the levers applied, reruns the exact
    same `score_business` path, and returns both a freshly-computed baseline and
    the adjusted score so the UI can diff them. Persists nothing.
    """
    biz = db.get(models.Business, business_id)
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")

    tx, inv = frames_for(biz)
    if tx is None or tx.empty:
        raise HTTPException(status_code=422, detail="No ledger to simulate.")

    as_of = pd.to_datetime(tx["txn_date"]).max()
    adj = whatif.Adjustments(**req.model_dump())
    try:
        baseline = score_business(tx, inv, biz.opening_balance, as_of)
        tx2, opening2 = whatif.apply_adjustments(tx, biz.opening_balance, adj, as_of)
        adjusted = score_business(tx2, inv, opening2, as_of)
    except InsufficientDataError as e:
        raise HTTPException(status_code=422, detail=f"Can't score this scenario: {e}")

    return schemas.WhatIfResponse(
        baseline=_score_out_from_result(baseline),
        adjusted=_score_out_from_result(adjusted),
        cashflow=cashflow_points_from_frame(tx2, opening2),
    )
