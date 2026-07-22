"""Classical additive time-series decomposition, implemented from scratch.

This is the heart of the fairness argument. Instead of penalizing a business
for *any* revenue variability, we split a monthly series into:

    observed = trend + seasonal + residual

and judge only the pieces that actually signal risk while ignoring the piece
that is merely predictable (the seasonal component). A landscaper that earns
nothing in January is not "unstable" — that swing lives in the seasonal term.

The **trend** factor uses this decomposition directly (the slope of the
deseasonalized series). The **revenue-stability** factor deliberately does NOT
use the residual — with only ~2 years of data an in-sample residual overfits
and collapses to near-zero for any series, so stability is measured
out-of-sample instead, by `predictability_cv` (does one year's monthly *shape*
predict the next?). See that function's docstring for the full rationale.

We roll our own rather than pull in statsmodels: it keeps the dependency list
tiny and makes the method transparent in a code walkthrough.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Decomposition:
    observed: pd.Series
    trend: pd.Series
    seasonal: pd.Series
    residual: pd.Series


def decompose_monthly(series: pd.Series, period: int = 12) -> Decomposition:
    """Additive decomposition of a monthly series indexed by period-end dates.

    Steps mirror the textbook moving-average method:
      1. Trend = centered rolling mean over one full period (12 months).
      2. Detrend by subtraction.
      3. Seasonal = average detrended value for each calendar month, then
         re-centered to sum to zero so it doesn't shift the overall level.
      4. Residual = observed - trend - seasonal.
    """
    series = series.sort_index()
    n = len(series)

    if n < period:
        # Not enough history for a seasonal read: treat everything as trend and
        # let downstream factors see a zero seasonal / zero residual world.
        trend = series.rolling(window=min(3, n), center=True, min_periods=1).mean()
        seasonal = pd.Series(0.0, index=series.index)
        residual = series - trend
        return Decomposition(series, trend, seasonal, residual)

    # 1. Centered moving-average trend. Even window -> average two passes so the
    #    result is centered on a month rather than a month boundary.
    trend = series.rolling(window=period, center=True, min_periods=period).mean()
    if period % 2 == 0:
        trend = trend.rolling(window=2, center=True, min_periods=1).mean()

    # 2. Detrend.
    detrended = series - trend

    # 3. Seasonal index by calendar month, averaged over the years we have.
    month_of = detrended.index.month
    seasonal_by_month = detrended.groupby(month_of).mean()
    seasonal_by_month -= seasonal_by_month.mean()  # re-center to sum ~0
    seasonal = pd.Series(
        [seasonal_by_month.get(m, 0.0) for m in series.index.month],
        index=series.index,
    )

    # 4. Residual — the unpredictable leftover we actually care about.
    residual = series - trend - seasonal

    return Decomposition(series, trend, seasonal, residual)


def deseasonalize(series: pd.Series, period: int = 12) -> pd.Series:
    """Return the series with the seasonal component removed (trend + residual)."""
    d = decompose_monthly(series, period)
    return d.observed - d.seasonal


def annualized_trend_pct(series: pd.Series, period: int = 12) -> float:
    """Slope of the deseasonalized series as an annual % of average level.

    A simple OLS fit on the deseasonalized revenue: positive means the business
    is genuinely growing once seasonality is stripped out, negative means it is
    shrinking regardless of which month you happen to look at.
    """
    deseasonal = deseasonalize(series, period).dropna()
    if len(deseasonal) < 3:
        return 0.0
    x = np.arange(len(deseasonal), dtype=float)
    y = deseasonal.to_numpy(dtype=float)
    slope = np.polyfit(x, y, 1)[0]  # change in level per month
    avg = y.mean()
    if avg == 0:
        return 0.0
    return float((slope * period) / avg * 100.0)


def predictability_cv(series: pd.Series, period: int = 12) -> float:
    """Cross-validated measure of how *unpredictable* a revenue series is.

    This is the honest version of "revenue stability." The naive approach —
    decompose the series and look at the leftover residual — overfits badly when
    you only have ~2 years of data: the seasonal component ends up fitting a
    unique value to almost every calendar month, so the residual collapses to
    near zero for *any* series, random or seasonal. That would let a business
    with pure-noise revenue masquerade as rock-stable.

    Instead we ask a question that can't be gamed by overfitting: **does one
    year's monthly shape predict the next year's?** We split the window into
    consecutive `period`-length blocks (which keeps calendar months aligned),
    normalize each year by its own mean to remove growth/level, use each year's
    shape to predict the *other* year out-of-sample, and return the residual as
    a coefficient of variation.

      - A seasonal business repeats (its October spike shows up both years) →
        each year predicts the other → tiny residual → looks stable/predictable.
      - A genuinely erratic business has no repeatable shape → the prediction
        fails → large residual → correctly flagged as volatile.

    With fewer than two full cycles we can't cross-validate seasonality, so we
    fall back to the raw coefficient of variation.
    """
    series = series.sort_index()
    mean = float(series.mean())
    if mean <= 0:
        return 1.0

    n = len(series)
    if n < 2 * period:
        return float(series.std(ddof=0) / mean)

    vals = series.to_numpy(dtype=float)[-2 * period:]
    y1, y2 = vals[:period], vals[period:]
    m1, m2 = y1.mean(), y2.mean()
    if m1 <= 0 or m2 <= 0:
        return float(series.std(ddof=0) / mean)

    # Compare the two years' *shapes*, not their absolute levels. Dividing each
    # year by its own mean removes growth and level, leaving a monthly "share"
    # profile (each sums to `period`, so the average share is 1). The average
    # absolute month-by-month disagreement between the two shapes is our
    # unpredictability score: near 0 when the pattern repeats (any shape, spiky
    # or flat), large when this year looks nothing like last year. Working in
    # share-space keeps a huge-but-repeatable seasonal peak from blowing up the
    # metric the way an absolute-level comparison would.
    shape1, shape2 = y1 / m1, y2 / m2
    return float(np.abs(shape1 - shape2).sum() / period)
