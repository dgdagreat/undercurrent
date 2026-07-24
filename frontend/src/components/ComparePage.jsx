import { useEffect, useState } from "react";
import { fetchBusiness } from "../api";
import { gradeColor, REC_COLORS, scoreColor } from "../theme";
import ScoreGauge from "./ScoreGauge";

// Canonical factor order (matches the scoring config) for the comparison rows.
const FACTOR_ORDER = [
  "runway",
  "revenue_stability",
  "trend",
  "debt_service",
  "receivables",
  "expense_flexibility",
];

// Side-by-side comparison of 2-4 businesses: gauges, verdicts, and every factor
// sub-score in one grid. Makes the fairness thesis visible — a seasonal A next
// to a SaaS A, scored by the same six factors.
export default function ComparePage({ ids, onSelect }) {
  const [details, setDetails] = useState({});
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    setLoaded(false);
    Promise.all(ids.map((id) => fetchBusiness(id).catch(() => null)))
      .then((list) => {
        if (!alive) return;
        const map = {};
        list.forEach((d) => d && (map[d.id] = d));
        setDetails(map);
        setLoaded(true);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [ids.join(",")]);

  const cols = ids.map((id) => details[id]).filter(Boolean);

  if (error) return <div className="loading">Couldn't load comparison: {error}</div>;
  if (ids.length < 2)
    return (
      <div className="loading">
        Pick 2–4 businesses to compare from the menu (the ⇄ buttons).
      </div>
    );
  if (!loaded) return <div className="loading">Loading…</div>;
  // Some ids may have failed (a deleted upload, a stale compare link).
  if (cols.length < 2)
    return (
      <div className="loading">
        Couldn't load enough of the selected businesses to compare — they may
        have been deleted. Pick 2–4 from the menu.
      </div>
    );

  // Build factor label lookup from the first business that has each factor.
  const labelFor = {};
  cols.forEach((d) =>
    d.score.factors.forEach((f) => {
      labelFor[f.factor_name] = f.label;
    })
  );

  const factorCell = (d, name) => {
    const f = d.score.factors.find((x) => x.factor_name === name);
    if (!f || f.weight === 0)
      return <span className="cmp-cell cmp-cell--na">—</span>;
    return (
      <span className="cmp-cell" style={{ color: scoreColor(f.sub_score) }}>
        {f.sub_score.toFixed(0)}
      </span>
    );
  };

  return (
    <div className="compare">
      <div className="section-title" style={{ marginTop: 20 }}>
        Comparing {cols.length} businesses
      </div>
      <p className="section-sub">
        The same six factors, side by side. Seasonal, invoice-driven, and steady
        businesses are all judged by the identical model.
      </p>

      <div
        className="compare-grid"
        style={{ gridTemplateColumns: `220px repeat(${cols.length}, 1fr)` }}
      >
        {/* Header row: gauges + verdicts */}
        <div className="compare-corner" />
        {cols.map((d) => {
          const rec = REC_COLORS[d.score.recommendation] || REC_COLORS.Review;
          return (
            <div key={d.id} className="compare-head">
              <button className="compare-name" onClick={() => onSelect(d.id)}>
                {d.name}
              </button>
              <div className="compare-industry">{d.industry}</div>
              <ScoreGauge score={d.score.overall_score} grade={d.score.grade} />
              <div
                className="rec-badge rec-badge--sm"
                style={{ background: rec.bg, color: rec.fg }}
              >
                {d.score.recommendation}
              </div>
            </div>
          );
        })}

        {/* One row per factor */}
        {FACTOR_ORDER.filter((n) => labelFor[n]).map((name) => (
          <div className="compare-row-contents" key={name} style={{ display: "contents" }}>
            <div className="compare-rowlabel">{labelFor[name]}</div>
            {cols.map((d) => (
              <div key={d.id} className="compare-datacell">
                {factorCell(d, name)}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
