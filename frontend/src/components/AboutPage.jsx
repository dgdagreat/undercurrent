// The methodology story, living in the product — mirrors README.md and
// backend/app/scoring/config.py. If weights change there, update here.
const FACTORS = [
  ["Cash runway (trough)", 25, "Months of expenses covered by cash at the seasonal low point — surviving the trough is what actually kills these businesses."],
  ["Revenue stability", 20, "Out-of-sample unpredictability: how badly one year's monthly shape fails to predict the next. Predictable seasonality doesn't count against you."],
  ["Growth trend", 15, "Direction of deseasonalized revenue — growing, flat, or eroding. A holiday quarter can't hide a decline."],
  ["Debt-service coverage", 15, "Operating cash flow vs. scheduled loan payments (DSCR)."],
  ["Receivables health", 15, "Days-sales-outstanding and overdue share (invoice businesses only; weight redistributes otherwise)."],
  ["Expense flexibility", 10, "How much costs flex down when revenue falls — flexible costs cushion the trough."],
];

const BANDS = [
  ["90–100", "A", "Very Low", "Approve"],
  ["80–89", "B", "Low", "Approve"],
  ["70–79", "C", "Moderate", "Review"],
  ["60–69", "D", "Elevated", "Review"],
  ["< 60", "F", "High", "Decline"],
];

export default function AboutPage({ onUpload }) {
  return (
    <div className="about">
      <h1>How Pulse scores a business</h1>

      <section className="card about__block">
        <h2>The problem</h2>
        <p>
          Most automated underwriting implicitly assumes smooth, recurring
          revenue. That quietly penalizes two big categories of healthy small
          business: <b>seasonal</b> operations (landscaping, theme parks,
          holiday retail) that earn almost nothing for months at a time, and{" "}
          <b>invoice-driven</b> firms (agencies, contractors) that get paid in
          lumps 30–90 days after the work. Their bank feeds look "volatile," so
          they get under-scored or declined — for the <i>shape</i> of their
          revenue, not its substance.
        </p>
      </section>

      <section className="card about__block">
        <h2>The fix — judge the cycle, not the month</h2>
        <p>
          Every monthly cash-flow series is decomposed into{" "}
          <code>trend + seasonal + residual</code>. The factors judge what
          actually signals risk — the underlying trend and the{" "}
          <i>unpredictable</i> variation — and ignore what's merely predictable.
          Stability is measured <b>out-of-sample</b>: does one year's monthly
          shape predict the next year's? A pumpkin patch's October spike repeats,
          so it reads as predictable; a startup's pattern-less lurching doesn't,
          so it reads as risk. Coverage is measured at the seasonal{" "}
          <b>trough</b>, so a business that banks its season to survive winter
          gets credit for it. No industry gets hard-coded leniency — the same
          math treats every ledger.
        </p>
      </section>

      <section className="card about__block">
        <h2>Six explainable factors</h2>
        <table>
          <thead>
            <tr>
              <th>Factor</th>
              <th>Weight</th>
              <th>What it measures</th>
            </tr>
          </thead>
          <tbody>
            {FACTORS.map(([name, w, what]) => (
              <tr key={name}>
                <td><b>{name}</b></td>
                <td>{w}</td>
                <td>{what}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="about__note">
          Weights renormalize over the factors that apply, and every factor
          reports its raw metric, its direction, and a plain-English sentence —
          the "Why this score" panel on each business.
        </p>
      </section>

      <section className="card about__block">
        <h2>Grades</h2>
        <table>
          <thead>
            <tr>
              <th>Score</th>
              <th>Grade</th>
              <th>Risk tier</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {BANDS.map(([s, g, t, r]) => (
              <tr key={g}>
                <td>{s}</td>
                <td><b>{g}</b></td>
                <td>{t}</td>
                <td>{r}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="about__note">
          Bands split into +/- thirds (A+ … F) for finer resolution; the verdict
          follows the base letter.
        </p>
      </section>

      <section className="card about__block">
        <h2>Try it on your own numbers</h2>
        <p>
          Upload a transactions CSV — a bank-statement download or accounting
          export works. It runs through the exact same pipeline as every sample
          here.
        </p>
        <button className="btn btn--primary" onClick={onUpload}>
          Upload a CSV
        </button>
      </section>

      <p className="about__disclaimer">
        Pulse is a portfolio demonstration. All sample businesses are fictional,
        scores are computed from generated or user-uploaded transaction data,
        and nothing here is a real credit decision or financial advice.
      </p>
    </div>
  );
}
