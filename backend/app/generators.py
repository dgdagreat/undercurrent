"""Mock-data generators for four fictional small businesses.

Each generator emits a realistic-looking transaction ledger (and, where
relevant, an invoice book) using a *seeded* RNG so the demo is byte-for-byte
reproducible: clone, seed, and everyone sees the same numbers and scores.

The four profiles are chosen to stress the scoring model in different ways:

  saas      — smooth recurring revenue, the easy case (should grade A).
  seasonal  — huge but predictable revenue swings (naive models over-penalize).
  invoice   — lumpy, delayed collections (naive models call this "volatile").
  declining — gently shrinking with a thinning buffer (the borderline case
              a naive model would wave through; ours flags it for Review).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

# Fixed 24-month window so the seeded output never shifts with the wall clock.
END_DATE = date(2026, 6, 30)
MONTHS = 24


@dataclass
class GeneratedBusiness:
    name: str
    industry: str
    profile_type: str
    founded_date: date
    description: str
    opening_balance: float
    transactions: list[dict] = field(default_factory=list)
    invoices: list[dict] = field(default_factory=list)


def _month_starts(n: int, end: date) -> list[date]:
    """Return the first-of-month dates for the n months ending in `end`'s month."""
    months = []
    y, m = end.year, end.month
    for _ in range(n):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(months))


def _day(month_start: date, day: int) -> date:
    """A safe date within a month (clamps day to the month's length)."""
    last = calendar.monthrange(month_start.year, month_start.month)[1]
    return date(month_start.year, month_start.month, min(day, last))


def _tx(d, amount, direction, category, kind, counterparty) -> dict:
    return dict(
        txn_date=d, amount=round(amount, 2), direction=direction,
        category=category, kind=kind, counterparty=counterparty,
    )


# --------------------------------------------------------------------------- #
# 1. Steady SaaS                                                              #
# --------------------------------------------------------------------------- #
def gen_saas() -> GeneratedBusiness:
    rng = np.random.RandomState(11)
    months = _month_starts(MONTHS, END_DATE)
    txns: list[dict] = []
    mrr = 84_000.0
    for ms in months:
        mrr *= 1.012  # ~1.2% monthly growth
        revenue = mrr * (1 + rng.normal(0, 0.03))
        # Subscription revenue lands in two mid-cycle batches.
        txns.append(_tx(_day(ms, 2), revenue * 0.55, "in", "Subscriptions",
                        "revenue", "Stripe payouts"))
        txns.append(_tx(_day(ms, 16), revenue * 0.45, "in", "Subscriptions",
                        "revenue", "Stripe payouts"))
        # Mostly fixed cost base.
        txns.append(_tx(_day(ms, 1), -48_000, "out", "Payroll", "expense", "Gusto"))
        txns.append(_tx(_day(ms, 5), -9_000, "out", "Cloud hosting", "expense", "AWS"))
        txns.append(_tx(_day(ms, 10), -4_200, "out", "Software", "expense", "SaaS tools"))
        # A little variable marketing spend.
        txns.append(_tx(_day(ms, 12), -revenue * 0.06, "out", "Marketing",
                        "expense", "Ad networks"))
        txns.append(_tx(_day(ms, 20), -12_000, "out", "Owner distribution",
                        "owner_draw", "Owner"))
    return GeneratedBusiness(
        name="Northwind Analytics",
        industry="B2B SaaS",
        profile_type="saas",
        founded_date=date(2021, 3, 1),
        description="Subscription analytics platform with smooth recurring revenue "
                    "and predictable, mostly fixed operating costs.",
        opening_balance=210_000,
        transactions=txns,
    )


# --------------------------------------------------------------------------- #
# 2. Seasonal landscaping                                                     #
# --------------------------------------------------------------------------- #
def gen_seasonal() -> GeneratedBusiness:
    rng = np.random.RandomState(22)
    months = _month_starts(MONTHS, END_DATE)
    # Monthly seasonal multipliers (Jan..Dec): near-zero winter, summer peak.
    seasonal = {1: 0.10, 2: 0.12, 3: 0.45, 4: 0.95, 5: 1.45, 6: 1.70,
                7: 1.60, 8: 1.45, 9: 1.15, 10: 0.70, 11: 0.30, 12: 0.15}
    base = 52_000.0
    txns: list[dict] = []
    for ms in months:
        mult = seasonal[ms.month] * (1 + rng.normal(0, 0.05))
        revenue = base * mult
        # Revenue arrives across a few jobs per month.
        for frac, day in ((0.4, 8), (0.35, 18), (0.25, 26)):
            if revenue > 0:
                txns.append(_tx(_day(ms, day), revenue * frac, "in", "Job revenue",
                                "revenue", "Residential & commercial clients"))
        # Fixed base costs run year-round.
        txns.append(_tx(_day(ms, 1), -11_500, "out", "Equipment lease & insurance",
                        "expense", "Fleet & insurance"))
        # Seasonal crew + fuel scale with the work.
        txns.append(_tx(_day(ms, 15), -revenue * 0.45, "out", "Seasonal labor",
                        "expense", "Crew payroll"))
        txns.append(_tx(_day(ms, 20), -revenue * 0.07, "out", "Fuel & materials",
                        "expense", "Suppliers"))
        # Equipment loan.
        txns.append(_tx(_day(ms, 5), -3_400, "out", "Equipment loan",
                        "loan_payment", "Equipment finance"))
    return GeneratedBusiness(
        name="Evergreen Grounds Co.",
        industry="Landscaping",
        profile_type="seasonal",
        founded_date=date(2018, 4, 1),
        description="Landscaping firm with sharp seasonal revenue — near zero in "
                    "winter, peaking in summer — that pre-funds the off-season.",
        opening_balance=95_000,
        transactions=txns,
    )


# --------------------------------------------------------------------------- #
# 3. Invoice-driven agency                                                    #
# --------------------------------------------------------------------------- #
def gen_invoice() -> GeneratedBusiness:
    rng = np.random.RandomState(33)
    months = _month_starts(MONTHS, END_DATE)
    txns: list[dict] = []
    invoices: list[dict] = []
    for ms in months:
        # Work is delivered smoothly: 4-6 invoices issued each month.
        n_invoices = rng.randint(4, 7)
        for _ in range(n_invoices):
            amount = float(rng.randint(9_000, 26_000))
            issued = _day(ms, int(rng.randint(2, 26)))
            terms = int(rng.choice([30, 45, 45, 60]))
            due = issued + timedelta(days=terms)
            # Payment lag: usually near terms, ~25% pay late.
            late = rng.random() < 0.25
            lag = terms + int(rng.randint(1, 22)) if late else terms - int(rng.randint(0, 8))
            paid = issued + timedelta(days=max(15, lag))
            if paid <= END_DATE:
                invoices.append(dict(issued_date=issued, due_date=due, paid_date=paid,
                                     amount=amount, status="paid"))
                txns.append(_tx(paid, amount, "in", "Client invoice", "revenue",
                                "Agency clients"))
            else:
                # Still outstanding at as-of — feeds receivables aging.
                invoices.append(dict(issued_date=issued, due_date=due, paid_date=None,
                                     amount=amount, status="outstanding"))
        # Steady operating costs regardless of when cash lands.
        txns.append(_tx(_day(ms, 1), -6_000, "out", "Office rent", "expense", "Landlord"))
        txns.append(_tx(_day(ms, 1), -30_000, "out", "Payroll", "expense", "Staff"))
        txns.append(_tx(_day(ms, 15), -22_000, "out", "Payroll", "expense", "Staff"))
        txns.append(_tx(_day(ms, 8), -3_200, "out", "Software & tools", "expense",
                        "Design/dev tools"))
    return GeneratedBusiness(
        name="Meridian Creative",
        industry="Marketing Agency",
        profile_type="invoice",
        founded_date=date(2019, 9, 1),
        description="Project-based creative agency with steady payroll but lumpy, "
                    "delayed client payments on 30-60 day terms.",
        opening_balance=155_000,
        transactions=txns,
        invoices=invoices,
    )


# --------------------------------------------------------------------------- #
# 4. Gently declining retailer (the borderline case)                          #
# --------------------------------------------------------------------------- #
def gen_declining() -> GeneratedBusiness:
    rng = np.random.RandomState(44)
    months = _month_starts(MONTHS, END_DATE)
    # Retail has a Q4 holiday bump layered on top of a slow structural decline.
    # The decline is deliberately *gentle*: each holiday season nearly papers
    # over it, so a naive month-to-month model sees a healthy business. Only the
    # deseasonalized trend reveals the erosion — which is the whole point of the
    # borderline case. It should land in "Review", not a hard decline.
    holiday = {10: 1.12, 11: 1.35, 12: 1.40}
    base = 70_000.0
    txns: list[dict] = []
    for i, ms in enumerate(months):
        base *= 0.991  # ~0.9% monthly structural decline (~-10%/yr)
        mult = holiday.get(ms.month, 1.0) * (1 + rng.normal(0, 0.05))
        revenue = base * mult
        txns.append(_tx(_day(ms, 5), revenue * 0.5, "in", "Store sales", "revenue",
                        "POS settlements"))
        txns.append(_tx(_day(ms, 20), revenue * 0.5, "in", "Store sales", "revenue",
                        "POS settlements"))
        # COGS is variable (flexes with sales); rent & payroll are rigid.
        txns.append(_tx(_day(ms, 7), -revenue * 0.55, "out", "Inventory / COGS",
                        "expense", "Wholesalers"))
        txns.append(_tx(_day(ms, 1), -8_000, "out", "Store rent", "expense", "Landlord"))
        txns.append(_tx(_day(ms, 1), -17_500, "out", "Payroll", "expense", "Staff"))
        txns.append(_tx(_day(ms, 3), -3_200, "out", "Store loan", "loan_payment",
                        "SBA loan"))
    return GeneratedBusiness(
        name="Harbor Street Goods",
        industry="Specialty Retail",
        profile_type="declining",
        founded_date=date(2016, 6, 1),
        description="Brick-and-mortar specialty retailer whose underlying sales are "
                    "slowly eroding, masked each year by a strong holiday quarter.",
        opening_balance=24_000,
        transactions=txns,
    )


def all_businesses() -> list[GeneratedBusiness]:
    return [gen_saas(), gen_seasonal(), gen_invoice(), gen_declining()]
