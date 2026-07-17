"""Tunable knobs for the scoring engine.

Everything a reviewer might want to challenge lives here: the factor weights and
the benchmark thresholds each sub-score is measured against. Nothing is a magic
number buried in the math — the UI surfaces these so the score is auditable.
"""

# How many trailing months of history the score is computed over. Two full
# years lets the seasonal decomposition see ≥2 cycles, which is what separates a
# genuine trend from the seasonal swing — with only 12 months the two are
# mathematically indistinguishable and the trend factor goes blind.
LOOKBACK_MONTHS = 24

# Default factor weights (must be meaningful relative to each other; they are
# renormalized to sum to 100 across whichever factors actually apply to a
# business — e.g. receivables is dropped for a cash-only business).
WEIGHTS = {
    "runway": 25,          # surviving the trough is what actually kills these firms
    "revenue_stability": 20,
    "trend": 15,
    "debt_service": 15,
    "receivables": 15,
    "expense_flexibility": 10,
}

# Base letter-grade bands on the 0-100 overall score. We use the familiar
# school-style A/B/C/D/F scale (no "E" — a bottom grade of F reads unambiguously
# as "fail," whereas E makes people hesitate). Each 10-point band is further
# split into +/- thirds for finer granularity (see engine._grade_for); F is left
# plain, as it is on a real report card. Fields: (min_score, letter, tier, rec).
GRADE_BANDS = [
    (90, "A", "Very Low", "Approve"),
    (80, "B", "Low", "Approve"),
    (70, "C", "Moderate", "Review"),
    (60, "D", "Elevated", "Review"),
    (0, "F", "High", "Decline"),
]

# A sub-score at or above HELPED reads as a positive factor in the UI; at or
# below HURT it reads as a drag. Between the two it's roughly neutral.
DIRECTION_HELPED = 65
DIRECTION_HURT = 45
