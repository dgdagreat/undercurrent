import { scoreColor } from "../theme";

// The "why" panel: one row per factor with its sub-score bar, weight, a
// helped/hurt/neutral chip, and the plain-English explanation.
export default function FactorBreakdown({ factors }) {
  return (
    <div className="factors">
      {factors.map((f) => {
        const na = f.weight === 0;
        return (
          <div key={f.factor_name} className={`factor${na ? " factor--na" : ""}`}>
            <div className="factor__head">
              <div>
                <div className="factor__name">{f.label}</div>
                <div className="factor__raw">{f.raw_value}</div>
              </div>
              <div className="factor__meta">
                <span className="factor__weight">
                  {na ? "excluded" : `weight ${f.weight.toFixed(0)}%`}
                </span>
                <span className={`dir dir--${f.direction}`}>{f.direction}</span>
              </div>
            </div>
            {!na && (
              <div className="bar">
                <div
                  className="bar__fill"
                  style={{
                    width: `${f.sub_score}%`,
                    background: scoreColor(f.sub_score),
                  }}
                />
              </div>
            )}
            <p className="factor__explain">{f.explanation}</p>
          </div>
        );
      })}
    </div>
  );
}
