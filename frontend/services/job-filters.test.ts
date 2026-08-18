import { describe, expect, it } from "vitest";

import { isAlwaysOpenDeadline, isSavedAlwaysOpenJob, matchesEmploymentFilters } from "./job-filters";

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

  it("counts only saved always-open jobs without a deadline date", () => {
    expect(isSavedAlwaysOpenJob("상시채용", null, true)).toBe(true);
    expect(isSavedAlwaysOpenJob("채용 시 마감", "", true)).toBe(true);
    expect(isSavedAlwaysOpenJob("상시채용", "2026-08-31", true)).toBe(false);
    expect(isSavedAlwaysOpenJob("상시채용", null, false)).toBe(false);
    expect(isSavedAlwaysOpenJob("2026-08-31", null, true)).toBe(false);
  });
});
