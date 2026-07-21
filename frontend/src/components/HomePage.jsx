import { gradeColor, REC_COLORS } from "../theme";

// Landing view: the thesis in one screen, live portfolio stats, and three
// featured businesses picked dynamically (so uploads participate too).
export default function HomePage({ businesses, onSelect, onUpload }) {
  if (!businesses.length) return <div className="loading">Loading…</div>;

  const avg =
    businesses.reduce((s, b) => s + b.overall_score, 0) / businesses.length;
  const byRec = { Approve: 0, Review: 0, Decline: 0 };
  businesses.forEach((b) => {
    byRec[b.recommendation] = (byRec[b.recommendation] || 0) + 1;
  });

  // Grade distribution by base letter.
  const letters = ["A", "B", "C", "D", "F"];
  const dist = letters.map((L) => ({
    letter: L,
    count: businesses.filter((b) => b.grade[0] === L).length,
  }));
  const maxCount = Math.max(...dist.map((d) => d.count), 1);

  // Featured: strongest, closest to the Review line, weakest.
  const sorted = [...businesses].sort((a, b) => b.overall_score - a.overall_score);
  const strongest = sorted[0];
  const weakest = sorted[sorted.length - 1];
  const bubble = [...businesses].sort(
    (a, b) => Math.abs(a.overall_score - 70) - Math.abs(b.overall_score - 70)
  )[0];
  const featured = [
    { label: "Strongest", biz: strongest },
    { label: "On the bubble", biz: bubble },
    { label: "Highest risk", biz: weakest },
  ];

  return (
    <div className="home">
      <section className="hero">
        <h1>
          Cash-flow underwriting that's <em>fair</em> to seasonal businesses
        </h1>
        <p>
          Traditional models assume smooth recurring revenue, so they under-score
          landscapers, theme parks, and invoice-driven agencies whose money moves
          in waves. Undercurrent scores the <b>whole cycle</b> — it strips out
          predictable seasonality before judging stability, measures cash at the
          seasonal trough, and explains every point of the score.
        </p>
        <div className="hero__actions">
          <button className="btn btn--primary" onClick={() => onSelect(strongest.id)}>
            Explore a scored business
          </button>
          <button className="btn btn--ghost" onClick={onUpload}>
            Upload your own CSV
          </button>
        </div>
      </section>

      <section className="stat-grid">
        <div className="card stat">
          <div className="stat__num">{businesses.length}</div>
          <div className="stat__label">Businesses scored</div>
        </div>
        <div className="card stat">
          <div className="stat__num">{avg.toFixed(1)}</div>
          <div className="stat__label">Average score</div>
        </div>
        {["Approve", "Review", "Decline"].map((rec) => (
          <div className="card stat" key={rec}>
            <div className="stat__num" style={{ color: REC_COLORS[rec].fg }}>
              {byRec[rec] || 0}
            </div>
            <div className="stat__label">{rec}</div>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="card__title">Grade distribution</div>
        <div className="dist">
          {dist.map(({ letter, count }) => {
            const gc = gradeColor(letter);
            return (
              <div className="dist__row" key={letter}>
                <span className="dist__letter" style={{ color: gc.fg }}>
                  {letter}
                </span>
                <div className="dist__track">
                  <div
                    className="dist__fill"
                    style={{
                      width: `${(count / maxCount) * 100}%`,
                      background: gc.fg,
                    }}
                  />
                </div>
                <span className="dist__count">{count}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <div className="section-title">Worth a look</div>
        <p className="section-sub">
          Three ends of the portfolio — click through for the full
          factor-by-factor explanation.
        </p>
        <div className="feature-grid">
          {featured.map(({ label, biz }) => {
            const gc = gradeColor(biz.grade);
            const rc = REC_COLORS[biz.recommendation] || REC_COLORS.Review;
            return (
              <button
                key={label}
                className="card feature"
                onClick={() => onSelect(biz.id)}
              >
                <div className="feature__label">{label}</div>
                <div className="feature__head">
                  <div>
                    <div className="feature__name">{biz.name}</div>
                    <div className="feature__industry">{biz.industry}</div>
                  </div>
                  <div
                    className="biz-item__grade"
                    style={{ background: gc.bg, color: gc.fg }}
                  >
                    {biz.grade}
                  </div>
                </div>
                <div className="feature__meta">
                  <span>{biz.overall_score.toFixed(1)} / 100</span>
                  <span style={{ color: rc.fg, fontWeight: 700 }}>
                    {biz.recommendation}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
