const capitalAreaPrefixes = ["서울", "서울특별시", "경기", "경기도", "인천", "인천광역시"];

export function isCapitalAreaLocation(location: string | null | undefined) {
  const normalized = String(location ?? "").trim();
  if (!normalized) return false;
  return capitalAreaPrefixes.some((prefix) => (
    normalized === prefix
    || normalized.startsWith(`${prefix} `)
    || normalized.startsWith(`${prefix}전체`)
  ));
}
