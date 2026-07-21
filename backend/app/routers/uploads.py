"""Upload endpoints: bring your own business to the platform.

POST /api/uploads       — multipart CSV + a few form fields; parses, stores,
                          scores on the spot, returns the business summary.
DELETE /api/businesses/{id} — remove an uploaded business (samples are
                          protected so the demo can't be hollowed out).

Uploads run through the exact same scoring path as the seeded samples
(services.score_and_cache), so "upload a CSV" is an honest stand-in for a
production Plaid/QuickBooks feed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..ingest import IngestError, parse_transactions_csv
from ..scoring.engine import InsufficientDataError
from ..services import score_and_cache

router = APIRouter(prefix="/api", tags=["uploads"])

# profile_type marking user-uploaded businesses; drives the UI badge and the
# delete permission.
UPLOADED = "uploaded"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB is generous for a transactions CSV


@router.post("/uploads", response_model=schemas.BusinessSummary, status_code=201)
async def upload_business(
    file: UploadFile = File(...),
    name: str = Form(...),
    industry: str = Form("Uploaded"),
    opening_balance: float = Form(0.0),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB).")

    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Business name is required.")

    try:
        tx = parse_transactions_csv(raw)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e))

    biz = models.Business(
        name=name[:80],
        industry=industry.strip()[:60] or "Uploaded",
        profile_type=UPLOADED,
        founded_date=tx["txn_date"].min().date(),
        description=(
            f"Uploaded ledger: {len(tx):,} transactions covering "
            f"{tx['txn_date'].dt.to_period('M').nunique()} months "
            f"({tx['txn_date'].min():%b %Y} – {tx['txn_date'].max():%b %Y})."
        ),
        opening_balance=opening_balance,
    )
    db.add(biz)
    db.flush()

    for row in tx.itertuples(index=False):
        db.add(models.Transaction(
            business_id=biz.id, txn_date=row.txn_date.date(), amount=row.amount,
            direction=row.direction, category=row.category, kind=row.kind,
            counterparty=row.counterparty,
        ))
    db.flush()
    db.refresh(biz)

    try:
        result = score_and_cache(db, biz)
    except InsufficientDataError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Can't score this file: {e}")

    db.commit()
    return schemas.BusinessSummary(
        id=biz.id, name=biz.name, industry=biz.industry,
        profile_type=biz.profile_type, description=biz.description,
        overall_score=result.overall_score, grade=result.grade,
        risk_tier=result.risk_tier, recommendation=result.recommendation,
    )


@router.delete("/businesses/{business_id}", status_code=204)
def delete_business(business_id: int, db: Session = Depends(get_db)):
    biz = db.get(models.Business, business_id)
    if biz is None:
        raise HTTPException(status_code=404, detail="Business not found")
    if biz.profile_type != UPLOADED:
        raise HTTPException(
            status_code=403,
            detail="Sample businesses can't be deleted — only uploaded ones.",
        )
    # Score runs/factors aren't ORM-cascaded from Business, so clear them first.
    run_ids = [r.id for r in db.query(models.ScoreRun)
               .filter(models.ScoreRun.business_id == business_id)]
    if run_ids:
        db.query(models.ScoreFactor).filter(
            models.ScoreFactor.score_run_id.in_(run_ids)).delete(
            synchronize_session=False)
        db.query(models.ScoreRun).filter(
            models.ScoreRun.id.in_(run_ids)).delete(synchronize_session=False)
    db.delete(biz)  # cascades transactions + invoices via the ORM relationship
    db.commit()
