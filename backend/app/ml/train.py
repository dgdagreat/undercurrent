"""Train, evaluate, and explain the default-risk model.

Pipeline:
  1. Load the labeled dataset (dataset.py output).
  2. Stratified train/test split.
  3. Fit two models: a gradient-boosting classifier (the headline model) and a
     logistic-regression baseline (interpretable reference point).
  4. Evaluate honestly on held-out data: ROC-AUC, PR-AUC, Brier score,
     calibration, and cross-validated AUC (so we're not reading noise).
  5. Explain with SHAP (global importance + a beeswarm) so the learned model is
     as auditable as the rule-based score.
  6. Persist the model bundle (for serving) + metrics.json + plots.

Run:  python -m app.ml.train
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import shap  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    brier_score_loss,
    classification_report,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from .dataset import DATASET_PATH
from .features import FEATURE_LABELS, FEATURE_NAMES

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"
PLOT_DIR = Path(__file__).resolve().parents[3] / "docs" / "ml"


def _plot_calibration(y_true, y_prob, path: Path) -> None:
    from sklearn.calibration import calibration_curve

    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="#94a3b8", label="Perfectly calibrated")
    ax.plot(mean_pred, frac_pos, "o-", color="#4f46e5", label="Model")
    ax.set_xlabel("Predicted default probability")
    ax.set_ylabel("Observed default rate")
    ax.set_title("Calibration")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_roc_pr(y_true, y_prob, path: Path) -> None:
    from sklearn.metrics import precision_recall_curve, roc_curve

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    axes[0].plot(fpr, tpr, color="#4f46e5")
    axes[0].plot([0, 1], [0, 1], "--", color="#94a3b8")
    axes[0].set(title=f"ROC (AUC={roc_auc_score(y_true, y_prob):.3f})",
                xlabel="False positive rate", ylabel="True positive rate")
    axes[1].plot(rec, prec, color="#059669")
    axes[1].axhline(np.mean(y_true), ls="--", color="#94a3b8", label="Base rate")
    axes[1].set(title=f"Precision-Recall (AP={average_precision_score(y_true, y_prob):.3f})",
                xlabel="Recall", ylabel="Precision")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def train() -> dict:
    df = pd.read_csv(DATASET_PATH)
    X = df[FEATURE_NAMES]
    y = df["default"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # Headline model: gradient boosting.
    gbm = GradientBoostingClassifier(
        n_estimators=350, max_depth=3, learning_rate=0.05, subsample=0.9, random_state=42
    )
    gbm.fit(X_train, y_train)

    # Interpretable baseline: standardized logistic regression.
    logit = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    logit.fit(X_train, y_train)

    p_test = gbm.predict_proba(X_test)[:, 1]
    p_logit = logit.predict_proba(X_test)[:, 1]

    cv = StratifiedKFold(5, shuffle=True, random_state=42)
    cv_auc = cross_val_score(gbm, X, y, cv=cv, scoring="roc_auc")

    report = classification_report(y_test, (p_test >= 0.5).astype(int), output_dict=True)

    # SHAP global importance on the test set.
    explainer = shap.TreeExplainer(gbm)
    shap_values = explainer.shap_values(X_test)
    mean_abs = np.abs(shap_values).mean(axis=0)
    importance = sorted(
        [{"feature": f, "label": FEATURE_LABELS[f], "mean_abs_shap": float(v)}
         for f, v in zip(FEATURE_NAMES, mean_abs)],
        key=lambda d: d["mean_abs_shap"], reverse=True,
    )

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    _plot_roc_pr(y_test, p_test, PLOT_DIR / "roc_pr.png")
    _plot_calibration(y_test, p_test, PLOT_DIR / "calibration.png")
    # SHAP beeswarm.
    fig = plt.figure()
    shap.summary_plot(shap_values, X_test, feature_names=[FEATURE_LABELS[f] for f in FEATURE_NAMES],
                      show=False, max_display=14)
    plt.tight_layout()
    fig.savefig(PLOT_DIR / "shap_summary.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    metrics = {
        "model": "GradientBoostingClassifier",
        "n_train": int(len(X_train)), "n_test": int(len(X_test)),
        "base_rate": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y_test, p_test)), 4),
        "pr_auc": round(float(average_precision_score(y_test, p_test)), 4),
        "brier": round(float(brier_score_loss(y_test, p_test)), 4),
        "cv_auc_mean": round(float(cv_auc.mean()), 4),
        "cv_auc_std": round(float(cv_auc.std()), 4),
        "baseline_logistic_roc_auc": round(float(roc_auc_score(y_test, p_logit)), 4),
        "precision_default": round(report["1"]["precision"], 4),
        "recall_default": round(report["1"]["recall"], 4),
        "f1_default": round(report["1"]["f1-score"], 4),
        "importance": importance,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": gbm, "features": FEATURE_NAMES, "base_rate": float(y.mean()),
         "trained_at": metrics["trained_at"], "roc_auc": metrics["roc_auc"]},
        MODEL_PATH,
    )
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    m = train()
    print(f"Trained {m['model']} on {m['n_train']:,} businesses")
    print(f"  ROC-AUC {m['roc_auc']}  (CV {m['cv_auc_mean']}±{m['cv_auc_std']})  "
          f"vs logistic {m['baseline_logistic_roc_auc']}")
    print(f"  PR-AUC {m['pr_auc']}  Brier {m['brier']}  base rate {m['base_rate']}")
    print("  Top features:", ", ".join(d["feature"] for d in m["importance"][:5]))
    print(f"  Artifacts -> {MODEL_PATH.name}, {METRICS_PATH.name}, docs/ml/*.png")
