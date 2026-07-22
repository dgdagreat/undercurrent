import { describe, expect, it } from "vitest";
import { gradeColor, REC_COLORS, scoreColor, shortMonth, usd } from "./theme";

describe("gradeColor", () => {
  it("colors +/- grades by their base letter (the bug we fixed)", () => {
    // "A+", "A", "A-" must all resolve to the same (A) color, not fall through.
    expect(gradeColor("A+")).toEqual(gradeColor("A"));
    expect(gradeColor("A-")).toEqual(gradeColor("A"));
    expect(gradeColor("D+")).toEqual(gradeColor("D"));
  });

  it("resolves F (the renamed bottom grade)", () => {
    expect(gradeColor("F")).toBeTruthy();
    expect(gradeColor("F")).not.toEqual(gradeColor("A"));
  });
});

describe("formatting + palettes", () => {
  it("usd formats whole dollars", () => {
    expect(usd(1234)).toBe("$1,234");
  });

  it("shortMonth renders a friendly label", () => {
    expect(shortMonth("2025-03")).toMatch(/Mar/);
  });

  it("scoreColor is greener for high scores than low", () => {
    expect(scoreColor(90)).not.toEqual(scoreColor(20));
  });

  it("every recommendation has a color", () => {
    for (const rec of ["Approve", "Review", "Decline"]) {
      expect(REC_COLORS[rec]).toBeTruthy();
    }
  });
});
