"""Serving: load the trained model and explain a single business's risk.

Kept deliberately light on imports at module load (joblib/shap are imported
lazily inside `_load`) so importing the FastAPI app doesn't drag in the whole ML
stack. The model + a SHAP TreeExplainer are built once and cached.

`predict` returns a default probability, a risk band, and the per-feature SHAP
contributions (in log-odds) that drove it — the ML analogue of the rule-based
"Why this score" panel, so the learned model is as auditable as the rules.
"""

from __future__ import annotations

import functools
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_LABELS, FEATURE_NAMES, feature_row

_log = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "model.joblib"

# Probability -> qualitative band (roughly parallel to the rule-based tiers).
_RISK_BANDS = [(0.06, "Very Low"), (0.15, "Low"), (0.30, "Moderate"),
               (0.50, "Elevated"), (1.01, "High")]


@functools.lru_cache(maxsize=1)
def _load():
    """Load the model bundle + SHAP explainer once. Returns None if untrained."""
    if not MODEL_PATH.exists():
        return None
    import joblib
    import shap

    bundle = joblib.load(MODEL_PATH)
    explainer = shap.TreeExplainer(bundle["model"])
    return bundle, explainer


def is_available() -> bool:
    return _load() is not None


def prewarm() -> None:
    """Eagerly load the model + SHAP explainer so the first /ml request is fast.

    `_load()` is where the cost lives — importing shap/scikit-learn and building
    the TreeExplainer. Calling this at app startup (ideally off the request path,
    in a thread) pays that cost once at boot instead of on the first user request.
    Never raises: if the model is untrained or loading fails, the /ml endpoint
    still falls back to its own lazy `_load()` and its existing 503.
    """
    try:
        t0 = time.perf_counter()
        if _load() is None:
            _log.info("ML prewarm skipped: no trained model at %s", MODEL_PATH)
            return
        _log.info("ML model + SHAP explainer warmed in %.2fs", time.perf_counter() - t0)
    except Exception:  # noqa: BLE001 — warm-up must never break startup
        _log.exception("ML prewarm failed; /ml will load lazily on first use")


def _band(p: float) -> str:
    for hi, label in _RISK_BANDS:
        if p < hi:
            return label
    return "High"


def predict(transactions: pd.DataFrame, invoices: pd.DataFrame | None,
            opening_balance: float, as_of=None) -> dict | None:
    """Score one business. Returns None if the model hasn't been trained yet."""
    loaded = _load()
    if loaded is None:
        return None
    bundle, explainer = loaded
    model = bundle["model"]

    row = feature_row(transactions, invoices, opening_balance, as_of)
    # A named single-row frame (not a bare ndarray) so sklearn/SHAP see the same
    # feature names the model was trained on — no "missing feature names" warning.
    X = pd.DataFrame([[row[f] for f in FEATURE_NAMES]], columns=FEATURE_NAMES)
    prob = float(model.predict_proba(X)[0, 1])

    sv = explainer.shap_values(X)
    if isinstance(sv, list):          # multiclass shap returns a list; take positive class
        sv = sv[-1]
    sv = np.asarray(sv)[0]

    contributions = sorted(
        [
            {
                "feature": f,
                "label": FEATURE_LABELS[f],
                "value": round(float(row[f]), 3),
                "shap": round(float(s), 4),
                "direction": "increases" if s > 0 else "decreases",
            }
            for f, s in zip(FEATURE_NAMES, sv)
        ],
        key=lambda d: abs(d["shap"]),
        reverse=True,
    )

    return {
        "default_prob": round(prob, 4),
        "risk_band": _band(prob),
        "base_rate": round(float(bundle.get("base_rate", 0.0)), 4),
        "roc_auc": bundle.get("roc_auc"),
        "contributions": contributions,
    }
