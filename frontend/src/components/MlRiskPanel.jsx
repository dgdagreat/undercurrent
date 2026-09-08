import { useEffect, useState } from "react";
import { fetchMlPrediction } from "../api";

// The trained ML model's second opinion, shown beside the rule-based score.
// A gradient-boosting default probability + the SHAP contributions that drove
// it — the ML analogue of the rule-based "Why this score" panel. Renders
// nothing if the model artifact isn't trained (endpoint returns null).
const BAND_COLOR = {
  "Very Low": "var(--emerald)",
  Low: "#0d9488",
  Moderate: "var(--amber)",
  Elevated: "#ea580c",
  High: "var(--red)",
};

export default function MlRiskPanel({ businessId }) {
  const [ml, setMl] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | absent | error

  useEffect(() => {
    let alive = true;
    setState("loading");
    fetchMlPrediction(businessId)
      .then((data) => {
        if (!alive) return;
        if (!data) return setState("absent");
        setMl(data);
        setState("ready");
      })
      .catch(() => alive && setState("error"));
    return () => {
      alive = false;
    };
  }, [businessId]);

  // Silently hide if the model isn't trained — keeps the app fully functional
  // without the ML artifact.
  if (state === "absent") return null;

  const pct = ml ? Math.round(ml.default_prob * 100) : 0;
  const band = ml?.risk_band ?? "";
  const bandColor = BAND_COLOR[band] || "var(--slate)";

  // Scale SHAP bars relative to the largest absolute contribution shown.
  const top = ml?.contributions?.slice(0, 6) ?? [];
  const maxAbs = Math.max(...top.map((c) => Math.abs(c.shap)), 0.001);

  return (
    <>
      <div className="section-title">Machine-learning second opinion</div>
      <p className="section-sub">
        A gradient-boosting model trained on 4,000 synthetic businesses predicts
        the probability of default from the same cash-flow signals — an
        independent, learned check on the rule-based grade.{" "}
        {ml?.roc_auc != null && (
          <>Held-out ROC-AUC <b>{ml.roc_auc.toFixed(2)}</b>.</>
        )}
      </p>

      {state === "loading" && <div className="card ml-card">Scoring…</div>}
      {state === "error" && (
        <div className="card ml-card">Couldn't load the ML prediction.</div>
      )}

      {state === "ready" && (
        <div className="card ml-card">
          <div className="ml-head">
            <div className="ml-prob">
              <div className="ml-prob__num" style={{ color: bandColor }}>
                {pct}%
              </div>
              <div className="ml-prob__label">
                predicted default risk
                <span className="ml-band" style={{ color: bandColor }}>
                  {band}
                </span>
              </div>
            </div>
            <div className="ml-prob__bar">
              <div className="ml-prob__track">
                <div
                  className="ml-prob__fill"
                  style={{ width: `${pct}%`, background: bandColor }}
                />
                <div
                  className="ml-prob__base"
                  style={{ left: `${Math.round((ml.base_rate || 0) * 100)}%` }}
                  title={`Portfolio base rate ${Math.round(
                    (ml.base_rate || 0) * 100
                  )}%`}
                />
              </div>
              <div className="ml-prob__scale">
                <span>0%</span>
                <span>
                  base rate {Math.round((ml.base_rate || 0) * 100)}%
                </span>
                <span>100%</span>
              </div>
            </div>
          </div>

          <div className="ml-drivers__title">What drove this prediction (SHAP)</div>
          <div className="ml-drivers">
            {top.map((c) => {
              const up = c.direction === "increases";
              const w = (Math.abs(c.shap) / maxAbs) * 50; // half-width max
              return (
                <div className="ml-driver" key={c.feature}>
                  <div className="ml-driver__label">
                    {c.label}
                    <span className="ml-driver__val">{c.value}</span>
                  </div>
                  <div className="ml-driver__track">
                    <div className="ml-driver__center" />
                    <div
                      className="ml-driver__bar"
                      style={{
                        width: `${w}%`,
                        [up ? "left" : "right"]: "50%",
                        background: up ? "var(--red)" : "var(--emerald)",
                      }}
                    />
                  </div>
                  <div
                    className="ml-driver__dir"
                    style={{ color: up ? "var(--red)" : "var(--emerald)" }}
                  >
                    {up ? "↑ risk" : "↓ risk"}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="ml-note">
            Bars show each feature's SHAP push on the model's log-odds — red
            raises predicted risk, green lowers it. Labels are synthetic; this
            demonstrates the modeling and explainability pipeline, not a real
            credit decision.
          </p>
        </div>
      )}
    </>
  );
}
