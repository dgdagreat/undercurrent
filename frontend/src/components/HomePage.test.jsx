import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "./HomePage";

const businesses = [
  { id: 1, name: "Alpha SaaS", industry: "SaaS", grade: "A", overall_score: 96, recommendation: "Approve" },
  { id: 2, name: "Beta Retail", industry: "Retail", grade: "C", overall_score: 72, recommendation: "Review" },
  { id: 3, name: "Gamma Labs", industry: "Startup", grade: "F", overall_score: 30, recommendation: "Decline" },
];

describe("HomePage stats", () => {
  it("computes count and average score", () => {
    render(<HomePage businesses={businesses} onSelect={() => {}} onUpload={() => {}} />);
    expect(screen.getByText("Businesses scored")).toBeInTheDocument();
    // (96 + 72 + 30) / 3 = 66.0
    expect(screen.getByText("66.0")).toBeInTheDocument();
  });

  it("features the strongest and weakest businesses", () => {
    render(<HomePage businesses={businesses} onSelect={() => {}} onUpload={() => {}} />);
    expect(screen.getByText("Strongest")).toBeInTheDocument();
    expect(screen.getByText("Highest risk")).toBeInTheDocument();
    expect(screen.getByText("Alpha SaaS")).toBeInTheDocument(); // strongest
    expect(screen.getByText("Gamma Labs")).toBeInTheDocument(); // weakest
  });

  it("shows an empty loading state with no data", () => {
    render(<HomePage businesses={[]} onSelect={() => {}} onUpload={() => {}} />);
    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });
});
