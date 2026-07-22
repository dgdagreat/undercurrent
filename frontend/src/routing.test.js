import { describe, expect, it } from "vitest";
import { hashForCompare, parseHash } from "./routing";

describe("parseHash", () => {
  it("defaults to home", () => {
    expect(parseHash("")).toMatchObject({ view: "home", id: null });
    expect(parseHash("#/")).toMatchObject({ view: "home" });
  });

  it("parses about", () => {
    expect(parseHash("#/about")).toMatchObject({ view: "about" });
  });

  it("parses a business id", () => {
    expect(parseHash("#/business/12")).toMatchObject({ view: "business", id: 12 });
  });

  it("parses a compare list and drops junk", () => {
    expect(parseHash("#/compare/3,7,12")).toMatchObject({
      view: "compare",
      ids: [3, 7, 12],
    });
  });

  it("round-trips the compare hash builder", () => {
    const ids = [4, 9];
    expect(parseHash(`#${hashForCompare(ids)}`).ids).toEqual(ids);
  });
});
