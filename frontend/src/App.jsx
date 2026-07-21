import { useEffect, useState } from "react";
import { deleteBusiness, fetchBusiness, fetchBusinesses } from "./api";
import CashflowChart from "./components/CashflowChart";
import FactorBreakdown from "./components/FactorBreakdown";
import ScoreGauge from "./components/ScoreGauge";
import UploadPanel from "./components/UploadPanel";
import { gradeColor, REC_COLORS } from "./theme";

export default function App() {
  const [businesses, setBusinesses] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [showUpload, setShowUpload] = useState(false);
  // Hamburger-toggled business drawer; starts collapsed so the report owns
  // the screen.
  const [navOpen, setNavOpen] = useState(false);

  const refresh = (selectId) =>
    fetchBusinesses()
      .then((list) => {
        setBusinesses(list);
        if (selectId != null) setSelectedId(selectId);
        else if (list.length && !list.some((b) => b.id === selectedId))
          setSelectedId(list[0].id);
      })
      .catch((e) => setError(e.message));

  // Load the business list once, then default to the first.
  useEffect(() => {
    fetchBusinesses()
      .then((list) => {
        setBusinesses(list);
        if (list.length) setSelectedId(list[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  // Load detail whenever the selection changes.
  useEffect(() => {
    if (selectedId == null) return;
    setDetail(null);
    fetchBusiness(selectedId)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  if (error) return <div className="error">Couldn't reach the API: {error}</div>;

  return (
    <div className="app">
      {/* YouTube-style top bar: hamburger lives next to the wordmark. */}
      <header className="topbar">
        <button
          className="hamburger"
          onClick={() => setNavOpen((o) => !o)}
          aria-label={navOpen ? "Close business list" : "Open business list"}
          aria-expanded={navOpen}
        >
          <span />
          <span />
          <span />
        </button>
        <div className="topbar__brand">
          Pulse <span>Cash-flow health scoring</span>
        </div>
      </header>

      {/* Dimmed backdrop while the drawer is out; click to dismiss. */}
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <aside className={`drawer${navOpen ? " drawer--open" : ""}`}>
        <div className="sidebar__label">Businesses ({businesses.length})</div>
        <div className="biz-list">
          {businesses.map((b) => {
            const gc = gradeColor(b.grade);
            return (
              <button
                key={b.id}
                className={`biz-item${b.id === selectedId ? " active" : ""}`}
                onClick={() => {
                  setSelectedId(b.id);
                  setNavOpen(false); // picked one — get out of the way
                }}
              >
                <div>
                  <div className="biz-item__name">{b.name}</div>
                  <div className="biz-item__industry">
                    {b.industry}
                    {b.profile_type === "uploaded" && (
                      <span className="uploaded-badge">uploaded</span>
                    )}
                  </div>
                </div>
                <div
                  className="biz-item__grade"
                  style={{ background: gc.bg, color: gc.fg }}
                >
                  {b.grade}
                </div>
              </button>
            );
          })}
        </div>
        <button className="btn btn--upload" onClick={() => setShowUpload(true)}>
          ⬆ Upload your business
        </button>

        <div className="sidebar__foot">
          Portfolio demo · scores computed from generated or uploaded
          transaction data, not a credit bureau. No real lending decisions.
        </div>
      </aside>

      <main className="main">
        {!detail ? (
          <div className="loading">Loading…</div>
        ) : (
          <Dashboard
            detail={detail}
            onDelete={async () => {
              await deleteBusiness(detail.id);
              refresh(null);
            }}
          />
        )}
      </main>

      {showUpload && (
        <UploadPanel
          onClose={() => setShowUpload(false)}
          onDone={(biz) => {
            setShowUpload(false);
            refresh(biz.id);
          }}
        />
      )}
    </div>
  );
}

function Dashboard({ detail, onDelete }) {
  const { score } = detail;
  const rec = REC_COLORS[score.recommendation] || REC_COLORS.Review;
  const uploaded = detail.profile_type === "uploaded";

  return (
    <>
      <div className="page-head">
        <div className="tagpair">
          <span className="chip">{detail.industry}</span>
          <span className="chip">
            Founded {new Date(detail.founded_date).getFullYear()}
          </span>
          <span className="chip">Assessed {score.as_of}</span>
          {uploaded && (
            <button
              className="chip chip--danger"
              onClick={() => {
                if (window.confirm(`Delete "${detail.name}"?`)) onDelete();
              }}
            >
              Delete upload
            </button>
          )}
        </div>
        <h1>{detail.name}</h1>
        <p>{detail.description}</p>
      </div>

      <div className="grid grid--top">
        <div className="card score-card">
          <div className="card__title">Cash-Flow Health Score</div>
          <ScoreGauge score={score.overall_score} grade={score.grade} />
          <div
            className="rec-badge"
            style={{ background: rec.bg, color: rec.fg }}
          >
            {score.recommendation}
          </div>
          <div className="risk-line">
            Risk tier: <b>{score.risk_tier}</b>
          </div>
        </div>

        <div className="card">
          <div className="card__title">Cash Flow — Trailing 24 Months</div>
          <CashflowChart data={detail.cashflow} />
        </div>
      </div>

      <div className="section-title">Why this score</div>
      <p className="section-sub">
        Each factor is scored 0–100 and weighted. Seasonal and invoice-timing
        swings are removed before judging stability, so predictable patterns
        aren't mistaken for risk.
      </p>
      <FactorBreakdown factors={score.factors} />
    </>
  );
}
