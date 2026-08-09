import { describe, expect, it } from "vitest";

import { isAlwaysOpenDeadline, matchesEmploymentFilters } from "./job-filters";

describe("employment and deadline filters", () => {
  it.each(["상시채용", "채용 시 마감", "채용시 마감", "수시채용"])(
    "recognizes %s as always-open",
    (deadline) => expect(isAlwaysOpenDeadline(deadline)).toBe(true),
  );

  it("hides always-open jobs until the tag is explicitly selected", () => {
    expect(matchesEmploymentFilters("상시채용", ["정규직"], [])).toBe(false);
    expect(matchesEmploymentFilters("채용 시 마감", ["정규직"], ["정규직"])).toBe(false);
    expect(matchesEmploymentFilters("상시채용", ["정규직"], ["상시채용"])).toBe(true);
  });

  it("keeps regular employment filtering for dated postings", () => {
    expect(matchesEmploymentFilters("2026.09.01", ["정규직"], [])).toBe(true);
    expect(matchesEmploymentFilters("2026.09.01", ["정규직"], ["정규직"])).toBe(true);
    expect(matchesEmploymentFilters("2026.09.01", ["계약직"], ["정규직"])).toBe(false);
  });

  it("combines always-open and employment tags as an OR condition", () => {
    expect(matchesEmploymentFilters("상시채용", ["계약직"], ["상시채용", "정규직"])).toBe(true);
    expect(matchesEmploymentFilters("2026.09.01", ["정규직"], ["상시채용", "정규직"])).toBe(true);
  });
});
