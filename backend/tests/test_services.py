"""Tests for the service layer — live re-scoring replaces the cached run.

Uses an isolated in-memory SQLite DB so it never touches the real cashflow.db.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.generators import gen_saas
from app.services import rescore, score_and_cache


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _insert(db, gen):
    biz = models.Business(
        name=gen.name, industry=gen.industry, profile_type=gen.profile_type,
        founded_date=gen.founded_date, description=gen.description,
        opening_balance=gen.opening_balance,
    )
    db.add(biz)
    db.flush()
    for t in gen.transactions:
        db.add(models.Transaction(business_id=biz.id, **t))
    for i in gen.invoices:
        db.add(models.Invoice(business_id=biz.id, **i))
    db.flush()
    db.refresh(biz)
    return biz


def test_rescore_replaces_cached_run_and_is_deterministic(db):
    biz = _insert(db, gen_saas())

    first = score_and_cache(db, biz)
    db.commit()
    assert db.query(models.ScoreRun).count() == 1
    n_factors = db.query(models.ScoreFactor).count()
    assert n_factors == len(first.factors)

    again = rescore(db, biz)
    db.commit()

    # Old run is replaced, not appended: still exactly one run + one factor set.
    assert db.query(models.ScoreRun).count() == 1
    assert db.query(models.ScoreFactor).count() == n_factors
    # Scoring is deterministic, so the recomputed values match.
    assert again.overall_score == first.overall_score
    assert again.grade == first.grade
