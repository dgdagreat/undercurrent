import { useEffect, useMemo, useRef, useState } from "react";
import { simulateWhatIf } from "../api";
import { gradeColor, REC_COLORS, shortMonth, usd } from "../theme";
import CashflowChart from "./CashflowChart";
import ScoreGauge from "./ScoreGauge";

// One labelled slider.
function Lever({ label, hint, value, min, max, step, format, onChange }) {
  return (
    <div className="lever">
      <div className="lever__top">
        <span className="lever__label">{label}</span>
        <span className="lever__value">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {hint && <div className="lever__hint">{hint}</div>}
    </div>
  );
}

const pct = (n) => `${n > 0 ? "+" : ""}${n}%`;

// Interactive scenario tool: nudge five levers, POST to the read-only /whatif
// endpoint (debounced, abortable), and diff the returned adjusted score against
// its freshly-computed baseline. Turns the static score into "what would make
// this approvable?".
export default function WhatIfPanel({ detail, theme }) {
  // Scale the slider ranges to the business's size so they feel right whether
  // it does $40k/mo or $400k/mo.
  const avgRev = detail.cashflow.length
    ? detail.cashflow.reduce((s, p) => s + p.revenue, 0) / detail.cashflow.length
    : 20000;
  const bufMax = Math.max(10000, Math.round((avgRev * 4) / 1000) * 1000);
  const loanMax = Math.max(2000, Math.round((avgRev * 0.6) / 500) * 500);
  const troughMonth = useMemo(() => {
    if (!detail.cashflow.length) return null;
    return detail.cashflow.reduce((lo, p) =>
      p.end_balance < lo.end_balance ? p : lo
    ).month;
  }, [detail.cashflow]);

  const DEFAULTS = {
    opening_buffer_delta: 0,
    cash_injection_amount: 0,
    cash_injection_month: troughMonth,
    loan_paydown_delta: 0,
    expense_reduction_pct: 0,
    revenue_growth_pct: 0,
  };
  const [adj, setAdj] = useState(DEFAULTS);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const abortRef = useRef(null);

  const set = (patch) => setAdj((a) => ({ ...a, ...patch }));
  const reset = () => setAdj(DEFAULTS);

  const dirty =
    adj.opening_buffer_delta !== 0 ||
    adj.cash_injection_amount !== 0 ||
    adj.loan_paydown_delta !== 0 ||
    adj.expense_reduction_pct !== 0 ||
    adj.revenue_growth_pct !== 0;

  // Debounced, abortable POST whenever a lever moves. Clearing all levers clears
  // the result (back to the baseline the dashboard already shows).
  useEffect(() => {
    if (!dirty) {
      setResult(null);
      setErr(null);
      return;
    }
    const t = setTimeout(() => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setBusy(true);
      simulateWhatIf(detail.id, adj, ac.signal)
        .then((r) => {
          setResult(r);
          setErr(null);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setErr(e.message);
        })
        .finally(() => setBusy(false));
    }, 220);
    return () => clearTimeout(t);
  }, [adj, dirty, detail.id]);

  const movers = useMemo(() => {
    if (!result) return [];
    return result.adjusted.factors
      .map((af) => {
        const bf = result.baseline.factors.find(
          (f) => f.factor_name === af.factor_name
        );
        const from = bf ? bf.sub_score : af.sub_score;
        return { label: af.label, from, to: af.sub_score, delta: af.sub_score - from };
      })
      .filter((m) => Math.abs(m.delta) >= 0.1)
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  }, [result]);

  const adjusted = result?.adjusted;
  const baseline = result?.baseline;
  const scoreDelta = adjusted ? adjusted.overall_score - baseline.overall_score : 0;
  const rec = adjusted ? REC_COLORS[adjusted.recommendation] || REC_COLORS.Review : null;

  return (
    <section className="whatif">
      <div className="section-title">What-if simulator</div>
      <p className="section-sub">
        Adjust the levers to see what would change the verdict — the score
        recomputes live through the same engine, and nothing is saved.
      </p>

      <div className="whatif__grid">
        <div className="card whatif__levers">
          <div className="whatif__levers-head">
            <span className="card__title" style={{ margin: 0 }}>
              Scenario
            </span>
            {dirty && (
              <button className="whatif__reset" onClick={reset}>
                Reset
              </button>
            )}
          </div>

          <Lever
            label="Cash buffer"
            hint="Add to (or draw down) the starting cash on hand"
            value={adj.opening_buffer_delta}
            min={-bufMax}
            max={bufMax}
            step={1000}
            format={(v) => `${v >= 0 ? "+" : "−"}${usd(Math.abs(v))}`}
            onChange={(v) => set({ opening_buffer_delta: v })}
          />

          <div className="lever">
            <div className="lever__top">
              <span className="lever__label">One-off cash injection</span>
              <span className="lever__value">{usd(adj.cash_injection_amount)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={bufMax}
              step={1000}
              value={adj.cash_injection_amount}
              onChange={(e) => set({ cash_injection_amount: Number(e.target.value) })}
            />
            <div className="lever__hint">
              in{" "}
              <select
                value={adj.cash_injection_month || ""}
                onChange={(e) => set({ cash_injection_month: e.target.value })}
              >
                {detail.cashflow.map((p) => (
                  <option key={p.month} value={p.month}>
                    {shortMonth(p.month)}
                  </option>
                ))}
              </select>{" "}
              (e.g. a grant or owner contribution)
            </div>
          </div>

          <Lever
            label="Monthly loan paydown"
            hint="Left: reduce debt service · Right: pay extra principal"
            value={adj.loan_paydown_delta}
            min={-loanMax}
            max={loanMax}
            step={250}
            format={(v) =>
              v === 0 ? "no change" : `${v > 0 ? "+" : "−"}${usd(Math.abs(v))}/mo`
            }
            onChange={(v) => set({ loan_paydown_delta: v })}
          />

          <Lever
            label="Cut operating expenses"
            hint="Trim every expense line by this much"
            value={adj.expense_reduction_pct}
            min={0}
            max={40}
            step={1}
            format={(v) => `${v}%`}
            onChange={(v) => set({ expense_reduction_pct: v })}
          />

          <Lever
            label="Revenue growth assumption"
            hint="Rotate the revenue trajectory (annualized)"
            value={adj.revenue_growth_pct}
            min={-30}
            max={30}
            step={1}
            format={pct}
            onChange={(v) => set({ revenue_growth_pct: v })}
          />
        </div>

        <div className="card whatif__result">
          {!dirty ? (
            <div className="whatif__hint-empty">
              Move a lever to model a scenario. Try giving a flagged business a
              cash injection at its trough month, or trimming expenses.
            </div>
          ) : err ? (
            <div className="whatif__hint-empty">{err}</div>
          ) : !adjusted ? (
            <div className="whatif__hint-empty">Computing…</div>
          ) : (
            <div className={busy ? "whatif__live is-busy" : "whatif__live"}>
              <div className="whatif__scoreline">
                <ScoreGauge score={adjusted.overall_score} grade={adjusted.grade} />
                <div className="whatif__verdict">
                  <div
                    className="delta-chip"
                    style={{
                      background: scoreDelta >= 0 ? "var(--emerald-soft)" : "var(--red-soft)",
                      color: scoreDelta >= 0 ? "var(--emerald)" : "var(--red)",
                    }}
                  >
                    {scoreDelta >= 0 ? "▲" : "▼"} {Math.abs(scoreDelta).toFixed(1)} pts
                  </div>
                  <div className="whatif__grades">
                    <span>{baseline.grade}</span>
                    <span className="whatif__arrow">→</span>
                    <span style={{ color: gradeColor(adjusted.grade).fg }}>
                      {adjusted.grade}
                    </span>
                  </div>
                  <div
                    className="rec-badge rec-badge--sm"
                    style={{ background: rec.bg, color: rec.fg }}
                  >
                    {adjusted.recommendation}
                    {adjusted.recommendation !== baseline.recommendation && (
                      <span className="whatif__was"> (was {baseline.recommendation})</span>
                    )}
                  </div>
                </div>
              </div>

              <CashflowChart data={result.cashflow} theme={theme} />

              {movers.length > 0 && (
                <div className="whatif__movers">
                  <div className="whatif__movers-title">What moved</div>
                  {movers.map((m) => (
                    <div key={m.label} className="whatif__mover">
                      <span className="whatif__mover-label">{m.label}</span>
                      <span className="whatif__mover-nums">
                        {m.from.toFixed(0)} → {m.to.toFixed(0)}
                        <b
                          style={{
                            color: m.delta >= 0 ? "var(--emerald)" : "var(--red)",
                          }}
                        >
                          {m.delta >= 0 ? "+" : ""}
                          {m.delta.toFixed(0)}
                        </b>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
