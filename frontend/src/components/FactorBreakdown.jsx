import { useEffect, useState } from "react";
import { scoreColor } from "../theme";

// The "why" panel: one row per factor with its sub-score bar, weight, a
// helped/hurt/neutral chip, and the plain-English explanation. On mount the
// bars sweep from 0 to their value, staggered top-to-bottom, so the breakdown
// reads as if it's computing in front of you. (Keyed by business in the parent,
// so it replays on every switch.)
export default function FactorBreakdown({ factors }) {
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="factors">
      {factors.map((f, i) => {
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
                    width: `${filled ? f.sub_score : 0}%`,
                    background: scoreColor(f.sub_score),
                    transitionDelay: `${i * 55}ms`,
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
