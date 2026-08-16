import { describe, expect, it } from "vitest";

import {
  getApplicationTone,
  getDisplayApplicationStatus,
  getPipelineStep,
  isCalendarEligible,
  matchesCalendarStatusFilter,
  normalizeApplicationStatus,
} from "./application-status";

describe("application status presentation", () => {
  it("maps statuses to the shared calendar and modal tones", () => {
    expect(getApplicationTone("planned")).toBe("planned");
    expect(getApplicationTone("applied")).toBe("progress");
    expect(getApplicationTone("first_passed")).toBe("progress");
    expect(getApplicationTone("final_passed")).toBe("success");
    expect(getApplicationTone("planned", true)).toBe("inactive");
    expect(getApplicationTone("applied", true)).toBe("progress");
    expect(getApplicationTone("document_passed", true)).toBe("progress");
    expect(getApplicationTone("final_passed", true)).toBe("success");
    expect(getApplicationTone("excluded")).toBe("inactive");
  });

  it("uses planned as the safe default", () => {
    expect(normalizeApplicationStatus(null)).toBe("planned");
    expect(normalizeApplicationStatus("unknown")).toBe("planned");
  });

  it("prioritizes an active favorite status over a stale disliked flag", () => {
    expect(getDisplayApplicationStatus("planned", true, true)).toBe("planned");
    expect(getDisplayApplicationStatus("applied", true, true)).toBe("applied");
    expect(getDisplayApplicationStatus(null, false, true)).toBe("excluded");
  });

  it("filters calendar jobs by application group", () => {
    expect(matchesCalendarStatusFilter("planned", "planned")).toBe(true);
    expect(matchesCalendarStatusFilter("applied", "applied")).toBe(true);
    expect(matchesCalendarStatusFilter("document_passed", "passed")).toBe(true);
    expect(matchesCalendarStatusFilter("final_passed", "passed")).toBe(true);
    expect(matchesCalendarStatusFilter("applied", "passed")).toBe(false);
  });

  it("shows only favorites in the deadline calendar", () => {
    expect(isCalendarEligible(true, false)).toBe(true);
    expect(isCalendarEligible(false, false)).toBe(false);
    expect(isCalendarEligible(false, true)).toBe(false);
    expect(isCalendarEligible(true, true)).toBe(false);
  });

  it("collapses interview rounds into one pipeline step", () => {
    expect(getPipelineStep("planned")).toBe(0);
    expect(getPipelineStep("first_passed")).toBe(3);
    expect(getPipelineStep("second_passed")).toBe(3);
    expect(getPipelineStep("final_passed")).toBe(4);
  });
});
