"""Classical additive time-series decomposition, implemented from scratch.

This is the heart of the fairness argument. Instead of penalizing a business
for *any* revenue variability, we split a monthly series into:

    observed = trend + seasonal + residual

and let the factors judge the pieces that actually signal risk (the trend and
the residual) while ignoring the piece that is merely predictable (the
seasonal component). A landscaper that earns nothing in January is not
"unstable" — that swing lives entirely in the seasonal term.

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
