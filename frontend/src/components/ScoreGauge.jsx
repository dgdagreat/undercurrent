import { gradeColor } from "../theme";

// A circular 0-100 gauge ring with the score and grade in the middle.
export default function ScoreGauge({ score, grade }) {
  const size = 180;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const { fg } = gradeColor(grade);

  return (
    <div className="gauge">
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#e2e8f0"
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
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <div className="gauge__num">
        <div className="gauge__score" style={{ color: fg }}>
          {score.toFixed(0)}
        </div>
        <div className="gauge__grade">Grade {grade} · out of 100</div>
      </div>
    </div>
  );
}
