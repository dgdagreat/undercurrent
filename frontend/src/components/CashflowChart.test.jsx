import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CashflowTooltip } from "./CashflowChart";

describe("CashflowTooltip", () => {
  const row = {
    month: "2025-03",
    revenue: 1000,
    expenses: 400,
    net: 600,
    end_balance: 5000,
  };

  it("reads net from the full data row, not the per-series payload", () => {
    // Recharts only puts rendered series in `payload`; `net` lives on
    // payload[0].payload. The regression this guards showed "$NaN".
    render(<CashflowTooltip active label="2025-03" payload={[{ payload: row }]} />);
    expect(screen.getByText(/Net:/).textContent).toContain("$600");
    expect(screen.queryByText(/NaN/)).toBeNull();
  });

  it("renders nothing when inactive", () => {
    const { container } = render(<CashflowTooltip active={false} payload={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
