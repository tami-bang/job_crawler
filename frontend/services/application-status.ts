export type ApplicationStatus =
  | "planned"
  | "applied"
  | "document_passed"
  | "first_passed"
  | "second_passed"
  | "final_passed"
  | "excluded";

export type ApplicationTone = "planned" | "progress" | "success" | "inactive";
export type CalendarStatusFilter = "all" | "planned" | "applied" | "passed";

export const applicationStatusMeta: Record<ApplicationStatus, { label: string; tone: ApplicationTone }> = {
  planned: { label: "지원예정", tone: "planned" },
  applied: { label: "지원완료", tone: "progress" },
  document_passed: { label: "서류합격", tone: "progress" },
  first_passed: { label: "1차합격", tone: "progress" },
  second_passed: { label: "2차합격", tone: "progress" },
  final_passed: { label: "최종합격", tone: "success" },
  excluded: { label: "불합격", tone: "inactive" },
};

export const selectableApplicationStatuses = (Object.keys(applicationStatusMeta) as ApplicationStatus[])
  .filter((status) => status !== "excluded");

export const applicationPipeline = [
  { label: "지원예정", statuses: ["planned"] },
  { label: "지원완료", statuses: ["applied"] },
  { label: "서류합격", statuses: ["document_passed"] },
  { label: "면접/전형", statuses: ["first_passed", "second_passed"] },
  { label: "최종합격", statuses: ["final_passed"] },
] as const;

export function normalizeApplicationStatus(status: string | null | undefined): ApplicationStatus {
  return status && status in applicationStatusMeta ? status as ApplicationStatus : "planned";
}

export function getDisplayApplicationStatus(
  status: string | null | undefined,
  isFavorite = false,
  isDisliked = false,
): ApplicationStatus {
  if (isFavorite) return normalizeApplicationStatus(status);
  if (isDisliked) return "excluded";
  return normalizeApplicationStatus(status);
}

export function getApplicationTone(status: string | null | undefined, expired = false): ApplicationTone {
  const normalized = normalizeApplicationStatus(status);
  if (expired && normalized === "planned") return "inactive";
  return applicationStatusMeta[normalized].tone;
}

export function matchesCalendarStatusFilter(
  status: string | null | undefined,
  filter: CalendarStatusFilter,
) {
  if (filter === "all") return true;
  const normalized = normalizeApplicationStatus(status);
  if (filter === "planned") return normalized === "planned";
  if (filter === "applied") return normalized === "applied";
  return normalized.endsWith("_passed");
}

export function getPipelineStep(status: string | null | undefined) {
  const normalized = normalizeApplicationStatus(status);
  return applicationPipeline.findIndex((step) => (step.statuses as readonly string[]).includes(normalized));
}
