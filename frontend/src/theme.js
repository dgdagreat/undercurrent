// Shared color + formatting helpers so the visual language stays consistent.

export const GRADE_COLORS = {
  A: { fg: "#059669", bg: "#ecfdf5" },
  B: { fg: "#0d9488", bg: "#f0fdfa" },
  C: { fg: "#d97706", bg: "#fffbeb" },
  D: { fg: "#ea580c", bg: "#fff7ed" },
  E: { fg: "#dc2626", bg: "#fef2f2" },
};

export const REC_COLORS = {
  Approve: { fg: "#059669", bg: "#ecfdf5" },
  Review: { fg: "#d97706", bg: "#fffbeb" },
  Decline: { fg: "#dc2626", bg: "#fef2f2" },
};

// Sub-score -> bar color (red through amber to green).
export function scoreColor(score) {
  if (score >= 75) return "#059669";
  if (score >= 55) return "#0d9488";
  if (score >= 40) return "#d97706";
  return "#dc2626";
}

export function gradeColor(grade) {
  return GRADE_COLORS[grade] || GRADE_COLORS.C;
}

export const usd = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);

export const usdCompact = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);

// "2025-03" -> "Mar '25"
export function shortMonth(period) {
  const [y, m] = period.split("-");
  const d = new Date(Number(y), Number(m) - 1, 1);
  return `${d.toLocaleString("en-US", { month: "short" })} '${y.slice(2)}`;
}
