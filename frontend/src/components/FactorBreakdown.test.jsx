import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import FactorBreakdown from "./FactorBreakdown";

const factors = [
  {
    factor_name: "runway", label: "Cash Runway", sub_score: 80, weight: 29,
    contribution: 23, raw_value: "2.0 mo at trough", direction: "helped",
    explanation: "Healthy buffer.",
  },
  {
    factor_name: "receivables", label: "Receivables Health", sub_score: 0,
    weight: 0, contribution: 0, raw_value: "Not applicable", direction: "neutral",
    explanation: "Cash business — factor excluded.",
  },
];

describe("FactorBreakdown", () => {
  it("renders each factor and its direction", () => {
    render(<FactorBreakdown factors={factors} />);
    expect(screen.getByText("Cash Runway")).toBeInTheDocument();
    expect(screen.getByText("helped")).toBeInTheDocument();
  });

  it("marks a zero-weight factor as excluded (no bar)", () => {
    const { container } = render(<FactorBreakdown factors={factors} />);
    expect(screen.getByText("excluded")).toBeInTheDocument(); // the weight chip
    // Only the one applicable factor draws a bar fill.
    expect(container.querySelectorAll(".bar__fill")).toHaveLength(1);
  });
});
