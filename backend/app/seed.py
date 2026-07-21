"""Rebuild the SQLite database from scratch and cache a score for each business.

Run with:  python -m app.seed   (from the backend/ directory)

Idempotent: drops and recreates every table, regenerates the seeded mock data,
then runs the scoring engine once per business and stores the result so the API
can serve it instantly.
"""

from __future__ import annotations

from . import models
from .database import Base, SessionLocal, engine
from .generators import all_businesses
from .services import score_and_cache


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

            # Score it and cache the result (same path uploads use).
            result = score_and_cache(db, biz)
            print(f"  {gen.name:24s} -> {result.overall_score:5.1f}  "
                  f"{result.grade}  {result.risk_tier:8s}  {result.recommendation}")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding database...")
    seed()
