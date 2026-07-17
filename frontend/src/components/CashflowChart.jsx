import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { shortMonth, usd, usdCompact } from "../theme";

const REVENUE = "#4f46e5";
const EXPENSE = "#cbd5e1";
const BALANCE = "#0d9488";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  // Use the full underlying data row (payload[0].payload), not the per-series
  // payload — the latter only carries the *rendered* series (revenue, expenses,
  // end_balance), so `net` (a computed field we don't draw) would be undefined
  // and render as "$NaN".
  const p = payload[0].payload;
  return (
    <div
      style={{
        background: "#0f172a",
        color: "#f8fafc",
        padding: "10px 12px",
        borderRadius: 10,
        fontSize: 12,
        lineHeight: 1.6,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{shortMonth(label)}</div>
      <div>Revenue: {usd(p.revenue)}</div>
      <div>Expenses: {usd(p.expenses)}</div>
      <div>Net: {usd(p.net)}</div>
      <div style={{ color: "#5eead4" }}>End balance: {usd(p.end_balance)}</div>
    </div>
  );
}

// Monthly revenue vs expenses (bars) with the running cash balance (line).
export default function CashflowChart({ data }) {
  return (
    <>
      <div className="legend">
        <span>
          <i style={{ background: REVENUE }} /> Revenue
        </span>
        <span>
          <i style={{ background: EXPENSE }} /> Expenses
        </span>
        <span>
          <i style={{ background: BALANCE }} /> Cash balance
        </span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 4 }}>
          <CartesianGrid vertical={false} stroke="#eef2f6" />
          <XAxis
            dataKey="month"
            tickFormatter={shortMonth}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            interval={2}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={usdCompact}
            tick={{ fontSize: 11, fill: "#94a3b8" }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "#f1f5f9" }} />
          <Bar dataKey="revenue" fill={REVENUE} radius={[3, 3, 0, 0]} barSize={9} />
          <Bar dataKey="expenses" fill={EXPENSE} radius={[3, 3, 0, 0]} barSize={9} />
          <Line
            type="monotone"
            dataKey="end_balance"
            stroke={BALANCE}
            strokeWidth={2.5}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
