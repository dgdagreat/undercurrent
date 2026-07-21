import { useEffect, useState } from "react";
import { deleteBusiness, fetchBusiness, fetchBusinesses } from "./api";
import AboutPage from "./components/AboutPage";
import CashflowChart from "./components/CashflowChart";
import FactorBreakdown from "./components/FactorBreakdown";
import HomePage from "./components/HomePage";
import ScoreGauge from "./components/ScoreGauge";
import UploadPanel from "./components/UploadPanel";
import { gradeColor, REC_COLORS } from "./theme";

function Chevron({ open }) {
  return (
    <svg
      className={`chevron${open ? " chevron--open" : ""}`}
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
    >
      <path
        d="M4 6l4 4 4-4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function App() {
  const [businesses, setBusinesses] = useState([]);
  const [view, setView] = useState("home"); // home | business | about
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [showUpload, setShowUpload] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [bizOpen, setBizOpen] = useState(true); // collapsible drawer section

  const refresh = () =>
    fetchBusinesses().then(setBusinesses).catch((e) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);

  // Load detail whenever the selection changes.
  useEffect(() => {
    if (selectedId == null) return;
    setDetail(null);
    fetchBusiness(selectedId)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  // Esc dismisses whatever's on top: the upload dialog first, then the drawer.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      if (showUpload) setShowUpload(false);
      else if (navOpen) setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showUpload, navOpen]);

  const openBusiness = (id) => {
    setSelectedId(id);
    setView("business");
    setNavOpen(false);
  };

  const goto = (v) => {
    setView(v);
    setNavOpen(false);
  };

  if (error) return <div className="error">Couldn't reach the API: {error}</div>;

  return (
    <div className="app">
      {/* YouTube-style top bar: hamburger next to the wordmark. */}
      <header className="topbar">
        <button
          className="hamburger"
          onClick={() => setNavOpen((o) => !o)}
          aria-label={navOpen ? "Close menu" : "Open menu"}
          aria-expanded={navOpen}
        >
          <span />
          <span />
          <span />
        </button>
        <button className="topbar__brand" onClick={() => goto("home")}>
          Pulse <span>Cash-flow health scoring</span>
        </button>
      </header>

      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <aside className={`drawer${navOpen ? " drawer--open" : ""}`}>
        <nav className="drawer__nav">
          <button
            className={`nav-item${view === "home" ? " nav-item--active" : ""}`}
            onClick={() => goto("home")}
          >
            Home
          </button>
          <button
            className={`nav-item${view === "about" ? " nav-item--active" : ""}`}
            onClick={() => goto("about")}
          >
            About the model
          </button>
          <button
            className="nav-item"
            onClick={() => {
              setShowUpload(true);
              setNavOpen(false);
            }}
          >
            ⬆ Upload your business
          </button>
        </nav>

        <div className="drawer__divider" />

        {/* Collapsible businesses section. */}
        <button
          className="nav-section"
          onClick={() => setBizOpen((o) => !o)}
          aria-expanded={bizOpen}
        >
          Businesses ({businesses.length})
          <Chevron open={bizOpen} />
        </button>
        {bizOpen && (
          <div className="biz-list">
            {businesses.map((b) => {
              const gc = gradeColor(b.grade);
              return (
                <button
                  key={b.id}
                  className={`biz-item${
                    b.id === selectedId && view === "business" ? " active" : ""
                  }`}
                  onClick={() => openBusiness(b.id)}
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
        )}

        <div className="sidebar__foot">
          Portfolio demo · scores computed from generated or uploaded
          transaction data, not a credit bureau. No real lending decisions.
        </div>
      </aside>

      <main className="main">
        {view === "home" && (
          <HomePage
            businesses={businesses}
            onSelect={openBusiness}
            onUpload={() => setShowUpload(true)}
          />
        )}
        {view === "about" && <AboutPage onUpload={() => setShowUpload(true)} />}
        {view === "business" &&
          (!detail ? (
            <div className="loading">Loading…</div>
          ) : (
            <Dashboard
              detail={detail}
              onDelete={async () => {
                await deleteBusiness(detail.id);
                setSelectedId(null);
                setView("home");
                refresh();
              }}
            />
          ))}
      </main>

      {showUpload && (
        <UploadPanel
          onClose={() => setShowUpload(false)}
          onDone={(biz) => {
            setShowUpload(false);
            refresh();
            openBusiness(biz.id);
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
