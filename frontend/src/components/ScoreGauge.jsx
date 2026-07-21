import { useEffect, useState } from "react";
import { gradeColor } from "../theme";

// A circular 0-100 gauge. On mount (and whenever the score changes) the number
// counts up from 0 and the ring sweeps to fill in lockstep — easeOutCubic, so
// it decelerates into place.
export default function ScoreGauge({ score, grade }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let raf;
    let startTs = null;
    const duration = 900;
    const from = 0;
    const tick = (ts) => {
      if (startTs === null) startTs = ts;
      const t = Math.min(1, (ts - startTs) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setValue(from + (score - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [score]);

  const size = 180;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value)) / 100;
  const { fg } = gradeColor(grade);

  return (
    <div className="gauge">
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--gauge-track)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={fg}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - pct)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="gauge__num">
        <div className="gauge__score" style={{ color: fg }}>
          {Math.round(value)}
        </div>
        <div className="gauge__grade">Grade {grade} · out of 100</div>
      </div>
    </div>
  );
}
