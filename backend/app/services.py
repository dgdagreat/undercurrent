"""Shared service layer: score a persisted business and cache the result.

Both the seed script and the upload endpoint need the identical
"ledger in DB -> ScoreRun + ScoreFactors in DB" step, so it lives here once.
Keeping it out of the routers means the logic stays importable and testable
without an HTTP request in sight.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from . import models
from .scoring import score_business
from .scoring.engine import ScoreResult


def frames_for(biz: models.Business):
    """Pull a business's ledger + invoices back out as DataFrames for scoring."""
    tx = pd.DataFrame([
        dict(txn_date=t.txn_date, amount=t.amount, kind=t.kind, direction=t.direction)
        for t in biz.transactions
    ])
    inv_rows = [
        dict(issued_date=i.issued_date, due_date=i.due_date,
             paid_date=i.paid_date, amount=i.amount, status=i.status)
        for i in biz.invoices
    ]
    inv = pd.DataFrame(inv_rows) if inv_rows else None
    return tx, inv


def score_and_cache(db: Session, biz: models.Business) -> ScoreResult:
    """Score `biz` from its persisted ledger and store the run + factors.

    The caller owns the transaction (commit/rollback); this only flushes so the
    new rows get ids. Raises whatever score_business raises (e.g.
    InsufficientDataError) — callers translate that for their audience.
    """
    tx, inv = frames_for(biz)
    result = score_business(tx, inv, biz.opening_balance)

    run = models.ScoreRun(
        business_id=biz.id, as_of_date=pd.Timestamp(result.as_of).date(),
        overall_score=result.overall_score, grade=result.grade,
        risk_tier=result.risk_tier, recommendation=result.recommendation,
    )
    db.add(run)
    db.flush()
    for f in result.factors:
        db.add(models.ScoreFactor(
            score_run_id=run.id, factor_name=f.name, raw_value=f.raw_value,
            sub_score=f.sub_score, weight=f.weight, contribution=f.contribution,
            direction=f.direction, explanation=f.explanation,
        ))
    return result
