import { describe, expect, it } from "vitest";

import {
  getApplicationTone,
  getPipelineStep,
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
    expect(getApplicationTone("excluded")).toBe("inactive");
  });

  it("uses planned as the safe default", () => {
    expect(normalizeApplicationStatus(null)).toBe("planned");
    expect(normalizeApplicationStatus("unknown")).toBe("planned");
  });

  it("filters calendar jobs by application group", () => {
    expect(matchesCalendarStatusFilter("planned", "planned")).toBe(true);
    expect(matchesCalendarStatusFilter("applied", "applied")).toBe(true);
    expect(matchesCalendarStatusFilter("document_passed", "passed")).toBe(true);
    expect(matchesCalendarStatusFilter("final_passed", "passed")).toBe(true);
    expect(matchesCalendarStatusFilter("applied", "passed")).toBe(false);
  });

  it("collapses interview rounds into one pipeline step", () => {
    expect(getPipelineStep("planned")).toBe(0);
    expect(getPipelineStep("first_passed")).toBe(3);
    expect(getPipelineStep("second_passed")).toBe(3);
    expect(getPipelineStep("final_passed")).toBe(4);
  });
});
