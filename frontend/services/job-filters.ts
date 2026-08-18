export function isAlwaysOpenDeadline(deadline: string | null | undefined) {
  const normalized = (deadline ?? "").replace(/\s+/g, "");
  return ["상시채용", "상시", "채용시마감", "수시채용"].some((label) => normalized.includes(label));
}

export function isSavedAlwaysOpenJob(
  deadline: string | null | undefined,
  deadlineDate: string | null | undefined,
  isFavorite: boolean | null | undefined,
) {
  return Boolean(isFavorite && !deadlineDate && isAlwaysOpenDeadline(deadline));
}

export function matchesEmploymentFilters(
  deadline: string | null | undefined,
  employmentTokens: string[],
  selectedFilters: string[],
) {
  const alwaysOpen = isAlwaysOpenDeadline(deadline);
  const includesAlwaysOpen = selectedFilters.includes("상시채용");

  if (alwaysOpen && !includesAlwaysOpen) return false;
  if (selectedFilters.length === 0) return true;
  if (alwaysOpen && includesAlwaysOpen) return true;
  return employmentTokens.some((token) => selectedFilters.includes(token));
}
