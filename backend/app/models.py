"""ORM models — the data model described in the README.

Design note: we never store a running balance. Every balance in the app is
derived by cumulatively summing signed `transactions.amount` off the account's
opening balance, so the ledger is the single source of truth and can't drift.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    # profile_type drives which generator produced it: saas | seasonal |
    # invoice | declining. Handy for the UI and for explaining the demo.
    profile_type: Mapped[str] = mapped_column(String, nullable=False)
    founded_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    opening_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Signed: inflows positive, outflows negative. `direction` is redundant but
    # makes queries and the raw ledger readable.
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)  # in | out
    category: Mapped[str] = mapped_column(String, nullable=False)
    # kind classifies cash-flow purpose so the scoring engine can separate
    # operating flows from financing/owner flows.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    # revenue | expense | loan_payment | owner_draw | transfer
    counterparty: Mapped[str] = mapped_column(String, nullable=False)

    business: Mapped["Business"] = relationship(back_populates="transactions")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # paid | outstanding

    business: Mapped["Business"] = relationship(back_populates="invoices")


class ScoreRun(Base):
    """Cached top-line result of a scoring pass, so the dashboard is snappy."""

    __tablename__ = "score_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    grade: Mapped[str] = mapped_column(String, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String, nullable=False)
    recommendation: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    factors: Mapped[list["ScoreFactor"]] = relationship(
        back_populates="score_run", cascade="all, delete-orphan"
    )


class ScoreFactor(Base):
    """One row per factor — this is what powers the 'why' breakdown panel."""

    __tablename__ = "score_factors"

    id: Mapped[int] = mapped_column(primary_key=True)
    score_run_id: Mapped[int] = mapped_column(ForeignKey("score_runs.id"), index=True)
    factor_name: Mapped[str] = mapped_column(String, nullable=False)
    raw_value: Mapped[str] = mapped_column(String, nullable=False)  # display string
    sub_score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)  # helped|hurt|neutral
    explanation: Mapped[str] = mapped_column(String, nullable=False)

    score_run: Mapped["ScoreRun"] = relationship(back_populates="factors")
