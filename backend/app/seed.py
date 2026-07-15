"""Rebuild the SQLite database from scratch and cache a score for each business.

Run with:  python -m app.seed   (from the backend/ directory)

Idempotent: drops and recreates every table, regenerates the seeded mock data,
then runs the scoring engine once per business and stores the result so the API
can serve it instantly.
"""

from __future__ import annotations

import pandas as pd

from . import models
from .database import Base, SessionLocal, engine
from .generators import all_businesses
from .scoring import score_business


def _to_frames(biz: models.Business):
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


def seed() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        for gen in all_businesses():
            biz = models.Business(
                name=gen.name, industry=gen.industry, profile_type=gen.profile_type,
                founded_date=gen.founded_date, description=gen.description,
                opening_balance=gen.opening_balance,
            )
            db.add(biz)
            db.flush()  # assign biz.id

            for t in gen.transactions:
                db.add(models.Transaction(business_id=biz.id, **t))
            for i in gen.invoices:
                db.add(models.Invoice(business_id=biz.id, **i))
            db.flush()
            db.refresh(biz)

            # Score it and cache the result.
            tx, inv = _to_frames(biz)
            result = score_business(tx, inv, gen.opening_balance)
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
            print(f"  {gen.name:24s} -> {result.overall_score:5.1f}  "
                  f"{result.grade}  {result.risk_tier:8s}  {result.recommendation}")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding database...")
    seed()
