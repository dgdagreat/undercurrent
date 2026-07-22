import { useEffect, useMemo, useRef, useState } from "react";
import { deleteBusiness, fetchBusiness, fetchBusinesses } from "./api";
import AboutPage from "./components/AboutPage";
import CashflowChart from "./components/CashflowChart";
import ComparePage from "./components/ComparePage";
import FactorBreakdown from "./components/FactorBreakdown";
import HomePage from "./components/HomePage";
import ScoreGauge from "./components/ScoreGauge";
import UploadPanel from "./components/UploadPanel";
import WhatIfPanel from "./components/WhatIfPanel";
import { hashForCompare, parseHash } from "./routing";
import { gradeColor, REC_COLORS } from "./theme";

// Sun when we're in dark mode (click → go light), moon when in light mode.
function ThemeIcon({ dark }) {
  if (dark) {
    return (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}

function Chevron({ open }) {
  return (
    <svg className={`chevron${open ? " chevron--open" : ""}`} width="14" height="14"
      viewBox="0 0 16 16" fill="none">
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function App() {
  const initial = parseHash();
  const [businesses, setBusinesses] = useState([]);
  const [view, setView] = useState(initial.view); // home | business | about | compare
  const [selectedId, setSelectedId] = useState(initial.id);
  const [compareIds, setCompareIds] = useState(initial.ids);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [error, setError] = useState(null);
  const [showUpload, setShowUpload] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [bizOpen, setBizOpen] = useState(true);
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("uc-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  // Drawer controls: search / filter / sort + comparison staging selection.
  const [search, setSearch] = useState("");
  const [filterVerdict, setFilterVerdict] = useState("");
  const [sortBy, setSortBy] = useState("score-desc");
  const [compareSel, setCompareSel] = useState([]);

  const drawerRef = useRef(null);

  const refresh = () =>
    fetchBusinesses().then(setBusinesses).catch((e) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);

  // Apply + persist the theme; components read it via CSS vars on <html>.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("uc-theme", theme);
  }, [theme]);

  // Back/forward (and any manual hash edit) re-derives the view from the URL.
  useEffect(() => {
    const apply = () => {
      const r = parseHash();
      setView(r.view);
      setSelectedId(r.id);
      setCompareIds(r.ids);
    };
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);

  // Load detail whenever the selected business changes.
  useEffect(() => {
    setDetail(null);
    setDetailError(null);
    if (selectedId == null) return;
    fetchBusiness(selectedId)
      .then(setDetail)
      .catch((e) =>
        setDetailError(
          e.status === 404
            ? "This business doesn't exist anymore — it may have been a deleted upload."
            : "Couldn't load this business. Is the API server running?"
        )
      );
  }, [selectedId]);

  // A closed drawer must leave the keyboard tab order / a11y tree — it's only
  // translated off-screen, so without this its controls stay focusable.
  useEffect(() => {
    const el = drawerRef.current;
    if (!el) return;
    if (navOpen) el.removeAttribute("inert");
    else el.setAttribute("inert", "");
  }, [navOpen]);

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
    window.location.hash = `/business/${id}`;
    setNavOpen(false);
  };
  const goto = (v) => {
    window.location.hash = v === "about" ? "/about" : "/";
    setNavOpen(false);
  };
  const toggleCompare = (id) =>
    setCompareSel((sel) =>
      sel.includes(id) ? sel.filter((x) => x !== id) : sel.length >= 4 ? sel : [...sel, id]
    );
  const startCompare = () => {
    if (compareSel.length >= 2) {
      window.location.hash = hashForCompare(compareSel);
      setNavOpen(false);
    }
  };

  // Search + filter + sort for the drawer list.
  const visibleBiz = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = businesses.filter((b) => {
      if (q && !`${b.name} ${b.industry}`.toLowerCase().includes(q)) return false;
      if (filterVerdict && b.recommendation !== filterVerdict) return false;
      return true;
    });
    list = [...list];
    if (sortBy === "score-desc") list.sort((a, b) => b.overall_score - a.overall_score);
    else if (sortBy === "score-asc") list.sort((a, b) => a.overall_score - b.overall_score);
    else list.sort((a, b) => a.name.localeCompare(b.name));
    return list;
  }, [businesses, search, filterVerdict, sortBy]);

  if (error) return <div className="error">Couldn't reach the API: {error}</div>;

  return (
    <div className="app">
      <header className="topbar">
        <button className="hamburger" onClick={() => setNavOpen((o) => !o)}
          aria-label={navOpen ? "Close menu" : "Open menu"} aria-expanded={navOpen}>
          <span /><span /><span />
        </button>
        <button className="topbar__brand" onClick={() => goto("home")}>
          Undercurrent <span>Cash-flow health scoring</span>
        </button>
        <button className="theme-toggle"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}>
          <ThemeIcon dark={theme === "dark"} />
        </button>
      </header>

      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}

      <aside ref={drawerRef} className={`drawer${navOpen ? " drawer--open" : ""}`}>
        <nav className="drawer__nav">
          <button className={`nav-item${view === "home" ? " nav-item--active" : ""}`}
            onClick={() => goto("home")}>Home</button>
          <button className={`nav-item${view === "about" ? " nav-item--active" : ""}`}
            onClick={() => goto("about")}>About the model</button>
          <button className="nav-item"
            onClick={() => { setShowUpload(true); setNavOpen(false); }}>
            ⬆ Upload your business
          </button>
        </nav>

        <div className="drawer__divider" />

        <button className="nav-section" onClick={() => setBizOpen((o) => !o)}
          aria-expanded={bizOpen}>
          Businesses ({businesses.length})
          <Chevron open={bizOpen} />
        </button>

        {bizOpen && (
          <>
            <div className="drawer-filters">
              <input className="drawer-search" type="search" placeholder="Search…"
                value={search} onChange={(e) => setSearch(e.target.value)}
                aria-label="Search businesses" />
              <div className="drawer-filter-row">
                <select value={filterVerdict} aria-label="Filter by verdict"
                  onChange={(e) => setFilterVerdict(e.target.value)}>
                  <option value="">All verdicts</option>
                  <option>Approve</option>
                  <option>Review</option>
                  <option>Decline</option>
                </select>
                <select value={sortBy} aria-label="Sort businesses"
                  onChange={(e) => setSortBy(e.target.value)}>
                  <option value="score-desc">Score ↓</option>
                  <option value="score-asc">Score ↑</option>
                  <option value="name">Name</option>
                </select>
              </div>
            </div>

            <div className="biz-list">
              {visibleBiz.length === 0 && (
                <div className="biz-empty">No businesses match.</div>
              )}
              {visibleBiz.map((b) => {
                const gc = gradeColor(b.grade);
                const inCompare = compareSel.includes(b.id);
                return (
                  <div key={b.id}
                    className={`biz-row${b.id === selectedId && view === "business" ? " active" : ""}`}>
                    <button className="biz-item" onClick={() => openBusiness(b.id)}>
                      <div>
                        <div className="biz-item__name">{b.name}</div>
                        <div className="biz-item__industry">
                          {b.industry}
                          {b.profile_type === "uploaded" && (
                            <span className="uploaded-badge">uploaded</span>
                          )}
                        </div>
                      </div>
                      <div className="biz-item__grade" style={{ background: gc.bg, color: gc.fg }}>
                        {b.grade}
                      </div>
                    </button>
                    <button className={`biz-compare${inCompare ? " on" : ""}`}
                      onClick={() => toggleCompare(b.id)} aria-pressed={inCompare}
                      title={inCompare ? "Remove from comparison" : "Add to comparison"}>
                      ⇄
                    </button>
                  </div>
                );
              })}
            </div>

            {compareSel.length > 0 && (
              <div className="compare-tray">
                <span>{compareSel.length} to compare</span>
                <div className="compare-tray__btns">
                  <button className="tray-clear" onClick={() => setCompareSel([])}>
                    Clear
                  </button>
                  <button className="tray-go" disabled={compareSel.length < 2}
                    onClick={startCompare}>
                    Compare
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        <div className="sidebar__foot">
          Portfolio demo · scores computed from generated or uploaded
          transaction data, not a credit bureau. No real lending decisions.
        </div>
      </aside>

      <main className="main">
        {view === "home" && (
          <HomePage businesses={businesses} onSelect={openBusiness}
            onUpload={() => setShowUpload(true)} />
        )}
        {view === "about" && <AboutPage onUpload={() => setShowUpload(true)} />}
        {view === "compare" && <ComparePage ids={compareIds} onSelect={openBusiness} />}
        {view === "business" &&
          (detailError ? (
            <div className="loading">{detailError}</div>
          ) : !detail ? (
            <div className="loading">Loading…</div>
          ) : (
            <Dashboard detail={detail} theme={theme}
              onDelete={async () => {
                await deleteBusiness(detail.id);
                refresh();
                window.location.hash = "/";
              }} />
          ))}
      </main>

      {showUpload && (
        <UploadPanel onClose={() => setShowUpload(false)}
          onDone={(biz) => { setShowUpload(false); refresh(); openBusiness(biz.id); }} />
      )}
    </div>
  );
}

function Dashboard({ detail, onDelete, theme }) {
  const { score } = detail;
  const rec = REC_COLORS[score.recommendation] || REC_COLORS.Review;
  const uploaded = detail.profile_type === "uploaded";

  return (
    <>
      <div className="page-head">
        <div className="tagpair">
          <span className="chip">{detail.industry}</span>
          <span className="chip">Founded {new Date(detail.founded_date).getFullYear()}</span>
          <span className="chip">Assessed {score.as_of}</span>
          {uploaded && (
            <button className="chip chip--danger"
              onClick={() => { if (window.confirm(`Delete "${detail.name}"?`)) onDelete(); }}>
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
          <ScoreGauge key={detail.id} score={score.overall_score} grade={score.grade} />
          <div className="rec-badge" style={{ background: rec.bg, color: rec.fg }}>
            {score.recommendation}
          </div>
          <div className="risk-line">Risk tier: <b>{score.risk_tier}</b></div>
        </div>

        <div className="card">
          <div className="card__title">
            Cash Flow — {detail.cashflow.length >= 24
              ? "Trailing 24 Months"
              : `${detail.cashflow.length} Months`}
          </div>
          <CashflowChart data={detail.cashflow} theme={theme} />
        </div>
      </div>

      <div className="section-title">Why this score</div>
      <p className="section-sub">
        Each factor is scored 0–100 and weighted. Seasonal and invoice-timing
        swings are removed before judging stability, so predictable patterns
        aren't mistaken for risk.
      </p>
      <FactorBreakdown key={detail.id} factors={score.factors} />

      <WhatIfPanel key={`whatif-${detail.id}`} detail={detail} theme={theme} />
    </>
  );
}
