"use client";

import { KeyboardEvent, MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, Job } from "@/services/api";
import { downloadWorkbook } from "@/services/export-xlsx";

const statusLabel: Record<string, string> = {
  planned: "지원예정",
  applied: "지원완료",
  document_passed: "서류합격",
  first_passed: "1차합격",
  second_passed: "2차합격",
  final_passed: "최종합격",
};

const weekDays = ["일", "월", "화", "수", "목", "금", "토"];
const pageSizeOptions = [15, 50, 100];
const originExamples = "예: 서울역, 강남역, 서울 강남구 테헤란로 123";
const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
const sortLabels = {
  match_desc: "매칭 점수 높은순",
  deadline_asc: "마감 임박순",
  deadline_desc: "마감 여유순",
  posted_desc: "시작 최신순",
  posted_asc: "시작 오래된순",
  company_asc: "회사명 가나다순",
} as const;
const scoreFilterLabels = {
  strong: "85점 이상",
  good: "65~84점",
  possible: "1~64점",
  unscored: "미분석",
} as const;
type SortKey = keyof typeof sortLabels;
type ScoreFilterKey = keyof typeof scoreFilterLabels;
type ExplorerView = "list" | "calendar" | "expired";
const allowedLocationPrefixes = ["서울", "서울특별시", "경기", "경기도", "인천", "인천광역시"];
const baseLocationOptions = [
  "서울 강남구", "서울 강동구", "서울 강북구", "서울 강서구", "서울 관악구", "서울 광진구", "서울 구로구", "서울 금천구",
  "서울 노원구", "서울 도봉구", "서울 동대문구", "서울 동작구", "서울 마포구", "서울 서대문구", "서울 서초구", "서울 성동구",
  "서울 성북구", "서울 송파구", "서울 양천구", "서울 영등포구", "서울 용산구", "서울 은평구", "서울 종로구", "서울 중구", "서울 중랑구",
  "경기 가평군", "경기 고양시", "경기 과천시", "경기 광명시", "경기 광주시", "경기 구리시", "경기 군포시", "경기 김포시",
  "경기 남양주시", "경기 동두천시", "경기 부천시", "경기 성남시", "경기 수원시", "경기 시흥시", "경기 안산시", "경기 안성시",
  "경기 안양시", "경기 양주시", "경기 양평군", "경기 여주시", "경기 연천군", "경기 오산시", "경기 용인시", "경기 의왕시",
  "경기 의정부시", "경기 이천시", "경기 파주시", "경기 평택시", "경기 포천시", "경기 하남시", "경기 화성시",
  "인천 강화군", "인천 계양구", "인천 남동구", "인천 동구", "인천 미추홀구", "인천 부평구", "인천 서구", "인천 연수구", "인천 옹진군", "인천 중구",
];
const VIEWED_JOBS_KEY = "job-radar-viewed-jobs";
const snapshotNoiseLines = new Set([
  "회원가입/로그인",
  "기업 서비스",
  "JOB 찾기",
  "합격축하금",
  "공채정보",
  "신입·인턴",
  "기업·연봉",
  "콘텐츠",
  "취업톡톡",
  "상세요강",
  "접수기간∙방법",
  "기업정보",
  "추천공고",
  "채용정보에 잘못된 내용이 있을 경우",
  "문의",
  "해주세요.",
  "로그인",
  "TOP",
  "궁금해요",
  "지도보기",
]);
const snapshotStopLines = new Set([
  "모집인원",
  "고용형태",
  "직급/직책",
  "급여",
  "근무시간",
  "근무지주소",
  "지원자격",
  "경력",
  "학력",
  "스킬",
  "우대조건",
  "기본우대",
  "접수기간 · 방법",
  "남은기간",
  "시작일",
  "마감일",
  "채용 시 마감",
  "이 기업의 취업 전략",
  "합격자소서",
  "합격자소서 더보기",
  "인적성·면접 후기",
  "면접 질문",
  "면접 후기",
  "기업 정보",
  "기업정보 더보기",
  "사원수",
  "기업구분",
  "산업(업종)",
  "위치",
]);

function formatMonth(date: Date) {
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getCalendarDays(month: Date) {
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const firstDay = new Date(year, monthIndex, 1);
  const lastDate = new Date(year, monthIndex + 1, 0).getDate();
  const cells: Array<Date | null> = Array(firstDay.getDay()).fill(null);
  for (let day = 1; day <= lastDate; day += 1) cells.push(new Date(year, monthIndex, day));
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function toDateKey(date: Date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function getInitialMonth(jobs: Job[]) {
  const firstDeadline = jobs
    .map((job) => job.deadline_date)
    .filter(Boolean)
    .sort()[0];
  if (firstDeadline) return new Date(`${firstDeadline}T00:00:00`);
  return new Date();
}

function getDateTime(value: string | null | undefined, fallback: number) {
  if (!value) return fallback;
  const cleaned = value.replace(/[.]/g, "-").replace(/\([^)]*\)/g, "").trim();
  const timestamp = new Date(cleaned.length === 10 ? `${cleaned}T00:00:00` : cleaned).getTime();
  return Number.isNaN(timestamp) ? fallback : timestamp;
}

function parseDateParts(value: string | null | undefined) {
  if (!value) return null;
  const match = value.match(/(\d{4})[.-](\d{2})[.-](\d{2})/);
  if (!match) return null;
  const [, year, month, day] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (Number.isNaN(date.getTime())) return null;
  return { year, month, day, weekday: weekdays[date.getDay()] };
}

function formatPostedDate(value: string | null) {
  const parsed = parseDateParts(value);
  if (!parsed) return "시작 미정";
  return `시작 ${parsed.year}.${parsed.month}.${parsed.day}(${parsed.weekday})`;
}

function formatDeadlineDate(deadlineDate: string | null, deadline: string | null) {
  if (isAlwaysOpen(deadline)) return "상시채용";
  const parsed = parseDateParts(deadlineDate || deadline);
  const cleaned = (deadline || "").replace(/^마감\s*/, "").replace(/^마감일\s*/, "").trim();
  if (!parsed) {
    if (!cleaned || cleaned.includes("미정")) return "마감 미정";
    return `마감 ${cleaned}`;
  }
  return `마감 ${parsed.year}-${parsed.month}-${parsed.day}(${parsed.weekday})`;
}

function isAlwaysOpen(deadline: string | null | undefined) {
  return Boolean(deadline?.includes("상시"));
}

function isExpiredJob(job: Job, todayKey: string) {
  if (isAlwaysOpen(job.deadline)) return false;
  return Boolean(getEffectiveDeadlineDate(job) && getEffectiveDeadlineDate(job)! < todayKey);
}

function getEffectiveDeadlineDate(job: Job) {
  if (isAlwaysOpen(job.deadline)) return null;
  return job.deadline_date;
}

function normalizeLocationOption(location: string | null) {
  if (!location) return null;
  const tokens = location.replace(/[(),]/g, " ").split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return null;
  const [province, city] = tokens;
  if (!allowedLocationPrefixes.includes(province)) return null;
  const normalizedProvince = province.startsWith("서울") ? "서울" : province.startsWith("경기") ? "경기" : "인천";
  if (!city || city === "외") return normalizedProvince;
  return `${normalizedProvince} ${city}`;
}

function validateOriginAddress(value: string) {
  const trimmed = value.trim();
  if (trimmed.length < 2) return "출발지를 2글자 이상 입력해주세요.";
  if (!/[가-힣a-zA-Z0-9]/.test(trimmed)) return "한글 주소, 장소명, 역명 중 하나로 입력해주세요.";
  if (/^[0-9\s-]+$/.test(trimmed)) return "숫자만으로는 위치를 찾기 어려워요. 장소명이나 도로명 주소를 함께 입력해주세요.";
  if (/로|길/.test(trimmed) && !/(서울|경기|경기도|인천|시|군|구)/.test(trimmed)) {
    return "도로명만 입력하면 네이버지도에서 위치가 흔들릴 수 있어요. 예: 경기 안산시 단원구 지곡로 52 처럼 시/구까지 함께 입력해주세요.";
  }
  return "";
}

function getDestination(job: Job) {
  return job.location || job.company_name || job.title;
}

function buildNaverRouteSearchUrl(origin: string, destination: string) {
  const start = `,,${encodeURIComponent(origin.trim())},,ADDRESS_POI`;
  const goal = `,,${encodeURIComponent(destination.trim())},,ADDRESS_POI`;
  return `https://map.naver.com/p/directions/${start}/${goal}/-/transit?c=13.00,0,0,0,dh`;
}

function buildSnapshotFallback(job: Job) {
  const lines = [
    job.company_name ? `회사: ${job.company_name}` : "",
    job.location ? `지역: ${job.location}` : "",
    job.career ? `경력: ${job.career}` : "",
    job.employment_type ? `고용형태: ${job.employment_type}` : "",
    job.skill_candidates ? `기술/키워드: ${job.skill_candidates}` : "",
    job.positive_reasons.length ? `매칭 근거: ${job.positive_reasons.join(" / ")}` : "",
    job.detail_url ? `원문 URL: ${job.detail_url}` : "",
  ].filter(Boolean);

  return lines.length
    ? lines.join("\n")
    : "저장된 상세 텍스트가 아직 없습니다. 다음 상세 수집 때 원문 스냅샷을 다시 보강합니다.";
}

function cleanSnapshotLines(text: string) {
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line && !snapshotNoiseLines.has(line) && !line.includes("로그인하고 비슷한 조건"));
}

function readAfterLabel(lines: string[], label: string, maxLines = 6) {
  const index = lines.findIndex((line) => line === label);
  if (index < 0) return "";
  const values = [];
  for (const line of lines.slice(index + 1)) {
    if (snapshotStopLines.has(line)) break;
    values.push(line);
    if (values.length >= maxLines) break;
  }
  return values.join(" ");
}

function readFirstAfterLabels(lines: string[], labels: string[], maxLines = 6) {
  for (const label of labels) {
    const value = readAfterLabel(lines, label, maxLines);
    if (value) return value;
  }
  return "";
}

function isSnapshotSectionBreak(line: string) {
  return snapshotStopLines.has(line)
    || /^(20\d{2}|19\d{2})년?$/.test(line)
    || /^(상반기|하반기|신입|경력)$/.test(line);
}

function readSectionSnippet(lines: string[], labels: string[], maxChars = 220) {
  for (const label of labels) {
    const index = lines.findIndex((line) => line === label);
    if (index < 0) continue;

    const values = [];
    for (const line of lines.slice(index + 1)) {
      if (isSnapshotSectionBreak(line)) {
        if (values.length > 0) break;
        continue;
      }
      if (line.length < 3 || /^[·ㆍ∙|]+$/.test(line)) continue;
      values.push(line);
      if (values.join(" ").length >= maxChars) break;
    }

    const snippet = values.join(" ").replace(/\s+/g, " ").trim();
    if (snippet) return snippet.length > maxChars ? `${snippet.slice(0, maxChars).trim()}...` : snippet;
  }
  return "";
}

function isLongSnapshotBoundary(line: string) {
  const compact = line.replace(/\s+/g, "");
  const headings = [
    "모집요강", "모집분야", "모집인원", "고용형태", "급여", "근무시간", "근무지주소",
    "지원자격", "경력", "학력", "스킬", "핵심역량", "우대조건", "기본우대",
    "복리후생", "접수기간·방법", "접수기간∙방법", "남은기간", "시작일", "마감일",
    "이기업의취업전략", "합격자소서", "인적성·면접후기", "기업정보", "사원수",
    "기업구분", "산업(업종)", "위치", "지도보기",
  ];
  return headings.some((heading) => compact === heading || compact.startsWith(heading));
}

function readLongSection(lines: string[], labels: string[], maxChars = 3200) {
  for (const label of labels) {
    const target = label.replace(/\s+/g, "");
    const index = lines.findIndex((line) => line.replace(/\s+/g, "").includes(target));
    if (index < 0) continue;

    const values = [];
    for (const line of lines.slice(index + 1)) {
      if (isLongSnapshotBoundary(line) && values.length > 0) break;
      if (line.length < 2 || /^[·ㆍ∙|,]+$/.test(line)) continue;
      values.push(line);
      if (values.join("\n").length >= maxChars) break;
    }
    const section = values.join("\n").trim();
    if (section) return section.length > maxChars ? `${section.slice(0, maxChars).trim()}...` : section;
  }
  return "";
}

function careerRank(value: string) {
  const text = value.replace(/\s+/g, "");
  if (text === "신입") return [0, 0, value] as const;
  if (text.includes("신입") && text.includes("경력")) return [1, 0, value] as const;
  if (text.includes("경력무관") || text.includes("무관")) return [2, 0, value] as const;
  const range = text.match(/경력(\d+)\s*~\s*(\d+)년/);
  if (range) return [3, Number(range[1]), value] as const;
  const years = text.match(/경력(\d+)년/);
  if (years) return [4, Number(years[1]), value] as const;
  if (text.includes("경력")) return [5, 0, value] as const;
  return [9, 0, value] as const;
}

function compareCareerOptions(a: string, b: string) {
  const left = careerRank(a);
  const right = careerRank(b);
  return left[0] - right[0] || left[1] - right[1] || left[2].localeCompare(right[2], "ko");
}

function buildSnapshotRows(title: string, body: string) {
  const lines = cleanSnapshotLines(body);
  const rows = [
    ["공고명", title],
    ["모집분야", readAfterLabel(lines, "모집분야", 3)],
    ["고용형태", readAfterLabel(lines, "고용형태", 2)],
    ["근무시간", readAfterLabel(lines, "근무시간", 3)],
    ["근무지", readAfterLabel(lines, "근무지주소", 2)],
    ["경력", readAfterLabel(lines, "경력", 2)],
    ["학력", readAfterLabel(lines, "학력", 2)],
    ["우대조건", readFirstAfterLabels(lines, ["기본우대", "우대조건"], 4)],
    ["시작일", readAfterLabel(lines, "시작일", 1)],
    ["마감일", readAfterLabel(lines, "마감일", 2)],
    ["주요업무", readLongSection(lines, ["주요업무", "담당업무", "업무내용", "하는 일"])],
    ["자격요건", readLongSection(lines, ["자격요건", "지원자격", "필수사항", "필수요건"])],
    ["우대사항", readLongSection(lines, ["우대사항", "우대조건", "선호조건"])],
    ["지원서 작성 안내", readLongSection(lines, ["지원서는 이렇게 작성하세요", "지원서 작성", "제출서류", "접수방법", "이력서", "자기소개서"])],
    ["합격자소서", readSectionSnippet(lines, ["합격자소서", "합격자소서 더보기"])],
    ["인적성·면접 후기", readSectionSnippet(lines, ["인적성·면접 후기", "면접 질문", "면접 후기"])],
    ["사원수", readAfterLabel(lines, "사원수", 1)],
    ["담당업무", readFirstAfterLabels(lines, ["담당업무", "주요업무", "직무내용", "모집분야"], 5)],
  ].filter(([, value]) => value);
  return rows.length ? rows : [["저장 내용", lines.slice(0, 24).join(" / ")]];
}

function getEmployeeCount(job: Job) {
  if (!job.raw_detail_text) return "사원수 미정";
  const value = readAfterLabel(cleanSnapshotLines(job.raw_detail_text), "사원수", 1);
  return value ? `사원수 ${value}` : "사원수 미정";
}

function buildEmailReportBody(jobs: Job[]) {
  return [
    "JobRadar 필터 결과입니다.",
    "",
    ...jobs.slice(0, 20).map((job, index) => (
      `${index + 1}. [${job.match_score}] ${job.company_name || "회사 미상"} - ${job.title}\n${job.detail_url || ""}`
    )),
    jobs.length > 20 ? `\n외 ${jobs.length - 20}건` : "",
  ].filter(Boolean).join("\n");
}

function buildGmailComposeUrl(to: string, subjectText: string, bodyText: string) {
  const params = new URLSearchParams({
    view: "cm",
    fs: "1",
    to,
    su: subjectText,
    body: bodyText,
  });
  return `https://mail.google.com/mail/?${params.toString()}`;
}

function buildEmailReportGmailUrl(email: string, jobs: Job[]) {
  return buildGmailComposeUrl(email, `JobRadar 공고 ${jobs.length}건`, buildEmailReportBody(jobs));
}

function buildEmailReportMailto(email: string, jobs: Job[]) {
  const subject = encodeURIComponent(`JobRadar 공고 ${jobs.length}건`);
  const body = encodeURIComponent(buildEmailReportBody(jobs));
  return `mailto:${encodeURIComponent(email)}?subject=${subject}&body=${body}`;
}

function readViewedJobs() {
  if (typeof window === "undefined") return new Set<number>();
  try {
    const parsed = JSON.parse(localStorage.getItem(VIEWED_JOBS_KEY) ?? "[]") as number[];
    return new Set(parsed);
  } catch {
    return new Set<number>();
  }
}

function isString(value: string | null | undefined): value is string {
  return Boolean(value);
}

export default function JobExplorer({ favoriteOnly = false }: { favoriteOnly?: boolean }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState("");
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [scoreFilters, setScoreFilters] = useState<ScoreFilterKey[]>([]);
  const [employmentFilters, setEmploymentFilters] = useState<string[]>([]);
  const [careerFilters, setCareerFilters] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<SortKey>("posted_desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<ExplorerView>("list");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [email, setEmail] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [emailSending, setEmailSending] = useState(false);
  const [reportServerReady, setReportServerReady] = useState(false);
  const [searchFeedback, setSearchFeedback] = useState("");
  const [originAddress, setOriginAddress] = useState("");
  const [noticeModal, setNoticeModal] = useState<{ title: string; message: string; hint?: string } | null>(null);
  const [snapshotModal, setSnapshotModal] = useState<{ title: string; body: string } | null>(null);
  const [viewedJobs, setViewedJobs] = useState<Set<number>>(() => new Set());

  const loadJobs = useCallback(async (term = "", source: "initial" | "search" = "initial") => {
    setLoading(true);
    if (source === "search") setSearchFeedback("검색 중...");
    try {
      const result = await api.jobs(term, favoriteOnly);
      setJobs(result.items);
      setPage(1);
      setCalendarMonth(new Date());
      setError("");
      if (source === "search") {
        setSearchFeedback(`검색 완료 · ${result.items.length}건`);
        window.setTimeout(() => setSearchFeedback(""), 1800);
      }
    } catch {
      setError("API에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.");
      if (source === "search") setSearchFeedback("검색 실패");
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly]);

  useEffect(() => { void loadJobs(); }, [loadJobs]);
  useEffect(() => { setViewedJobs(readViewedJobs()); }, []);
  useEffect(() => {
    api.reportStatus()
      .then((status) => setReportServerReady(status.ready))
      .catch(() => setReportServerReady(false));
  }, []);

  const employmentOptions = useMemo(() => (
    Array.from(new Set(jobs.map((job) => job.employment_type).filter(Boolean))).sort() as string[]
  ), [jobs]);
  const careerOptions = useMemo(() => (
    Array.from(new Set(jobs.map((job) => job.career).filter(isString))).sort(compareCareerOptions)
  ), [jobs]);
  const locationOptions = useMemo(() => (
    Array.from(new Set([...baseLocationOptions, ...(jobs.map((job) => normalizeLocationOption(job.location)).filter(Boolean) as string[])]))
      .sort((a, b) => a.localeCompare(b, "ko"))
  ), [jobs]);

  const filteredJobs = useMemo(() => (
    jobs
      .filter((job) => {
        if (selectedLocations.length === 0) return true;
        const option = normalizeLocationOption(job.location);
        return Boolean(option && selectedLocations.includes(option));
      })
      .filter((job) => {
        if (scoreFilters.length === 0) return true;
        return scoreFilters.some((filter) => {
          if (filter === "strong") return job.match_score >= 85;
          if (filter === "good") return job.match_score >= 65 && job.match_score < 85;
          if (filter === "possible") return job.match_score > 0 && job.match_score < 65;
          return job.match_score === 0;
        });
      })
      .filter((job) => careerFilters.length === 0 || Boolean(job.career && careerFilters.includes(job.career)))
      .filter((job) => employmentFilters.length === 0 || Boolean(job.employment_type && employmentFilters.includes(job.employment_type)))
  ), [careerFilters, employmentFilters, jobs, scoreFilters, selectedLocations]);
  const todayKey = toDateKey(new Date());

  const activeFilteredJobs = useMemo(() => (
    filteredJobs.filter((job) => !isExpiredJob(job, todayKey))
  ), [filteredJobs, todayKey]);

  const expiredFilteredJobs = useMemo(() => (
    filteredJobs.filter((job) => isExpiredJob(job, todayKey))
  ), [filteredJobs, todayKey]);

  const visibleJobs = view === "expired" ? expiredFilteredJobs : activeFilteredJobs;

  const sortedJobs = useMemo(() => {
    const farFuture = 8640000000000000;
    const farPast = -8640000000000000;
    return [...visibleJobs].sort((a, b) => {
      if (sortBy === "deadline_asc") {
        return getDateTime(getEffectiveDeadlineDate(a), farFuture) - getDateTime(getEffectiveDeadlineDate(b), farFuture);
      }
      if (sortBy === "deadline_desc") {
        return getDateTime(getEffectiveDeadlineDate(b), farPast) - getDateTime(getEffectiveDeadlineDate(a), farPast);
      }
      if (sortBy === "posted_desc") {
        return getDateTime(b.posted_date, farPast) - getDateTime(a.posted_date, farPast);
      }
      if (sortBy === "posted_asc") {
        return getDateTime(a.posted_date, farFuture) - getDateTime(b.posted_date, farFuture);
      }
      if (sortBy === "company_asc") {
        return (a.company_name || "").localeCompare(b.company_name || "", "ko");
      }
      return b.match_score - a.match_score || getDateTime(b.posted_date, farPast) - getDateTime(a.posted_date, farPast);
    });
  }, [sortBy, visibleJobs]);

  useEffect(() => {
    setPage(1);
  }, [careerFilters, employmentFilters, scoreFilters, selectedLocations, sortBy, view]);

  const jobsByDeadline = useMemo(() => {
    return activeFilteredJobs.reduce<Record<string, Job[]>>((acc, job) => {
      const deadlineDate = getEffectiveDeadlineDate(job);
      if (!deadlineDate) return acc;
      acc[deadlineDate] = [...(acc[deadlineDate] ?? []), job];
      return acc;
    }, {});
  }, [activeFilteredJobs]);
  const totalPages = Math.max(1, Math.ceil(sortedJobs.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedJobs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedJobs.slice(start, start + pageSize);
  }, [currentPage, pageSize, sortedJobs]);
  const visibleStart = sortedJobs.length ? (currentPage - 1) * pageSize + 1 : 0;
  const visibleEnd = Math.min(currentPage * pageSize, sortedJobs.length);

  function updateJobState(jobId: number, update: (job: Job) => Job | null) {
    setJobs((previous) => previous.flatMap((job) => {
      if (job.id !== jobId) return [job];
      const next = update(job);
      return next ? [next] : [];
    }));
  }

  async function toggleFavorite(job: Job) {
    if (job.is_favorite) {
      await api.unfavorite(job.id);
      updateJobState(job.id, (current) => (
        favoriteOnly
          ? null
          : { ...current, is_favorite: false, favorite_memo: null, favorite_status: null }
      ));
      return;
    }

    await api.favorite(job.id);
    updateJobState(job.id, (current) => ({
      ...current,
      is_favorite: true,
      favorite_memo: current.favorite_memo ?? "",
      favorite_status: current.favorite_status ?? "planned",
    }));
  }

  async function changeStatus(job: Job, status: string) {
    await api.updateFavorite(job.id, job.favorite_memo ?? "", status);
    updateJobState(job.id, (current) => ({ ...current, favorite_status: status }));
  }

  async function changeMemo(job: Job, memo: string) {
    await api.updateFavorite(job.id, memo, job.favorite_status ?? "planned");
    updateJobState(job.id, (current) => ({ ...current, favorite_memo: memo }));
  }

  async function dislikeJob(job: Job) {
    await api.dislike(job.id);
    markViewed(job.id);
    updateJobState(job.id, () => null);
  }

  async function submitEmail() {
    if (!email.includes("@")) {
      setEmailStatus("이메일 주소를 다시 확인해주세요.");
      return;
    }

    setEmailSending(true);
    setEmailStatus("");
    try {
      if (!api.canEmailReport() || !reportServerReady) {
        window.open(buildEmailReportGmailUrl(email, sortedJobs), "_blank", "noopener,noreferrer");
        setEmailStatus("Gmail 작성창을 열었어요. REPORT_API_URL과 SMTP 값이 연결되면 첨부 리포트 자동 발송으로 전환됩니다.");
        return;
      }

      await api.emailReport(email, sortedJobs);
      setEmailStatus("엑셀 리포트를 이메일로 보냈어요.");
    } catch {
      setEmailStatus("발송 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setEmailSending(false);
    }
  }

  function handleSearch() {
    void loadJobs(search, "search");
  }

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    handleSearch();
  }

  function validateOriginForSearch() {
    const validationMessage = validateOriginAddress(originAddress);
    if (validationMessage) {
      setNoticeModal({
        title: "출발지 주소를 확인해주세요",
        message: validationMessage,
        hint: originExamples,
      });
      return false;
    }
    return true;
  }

  function handleRouteClick(event: MouseEvent<HTMLAnchorElement>, job: Job) {
    const destination = getDestination(job).trim();
    if (!destination) {
      event.preventDefault();
      setNoticeModal({
        title: "도착지 정보가 부족해요",
        message: "공고에 지역이나 회사명이 없어 네이버지도 검색어를 만들 수 없습니다.",
      });
      return;
    }
    if (!validateOriginForSearch()) {
      event.preventDefault();
      return;
    }
    markViewed(job.id);
  }

  function markViewed(jobId: number) {
    setViewedJobs((previous) => {
      const next = new Set(previous);
      next.add(jobId);
      try {
        localStorage.setItem(VIEWED_JOBS_KEY, JSON.stringify([...next]));
      } catch {
        // 브라우저 저장소가 막혀도 공고 탐색은 계속 동작합니다.
      }
      return next;
    });
  }

  async function openSnapshot(job: Job) {
    markViewed(job.id);
    try {
      const detail = await api.job(job.id);
      setSnapshotModal({
        title: `${job.company_name || "회사 미상"} · ${job.title}`,
        body: detail.raw_detail_text || buildSnapshotFallback(detail),
      });
    } catch {
      setSnapshotModal({
        title: "스냅샷을 불러오지 못했어요",
        body: "백엔드 연결 상태를 확인한 뒤 다시 시도해주세요.",
      });
    }
  }

  function toggleLocationFilter(location: string) {
    setSelectedLocations((previous) => (
      previous.includes(location)
        ? previous.filter((item) => item !== location)
        : [...previous, location]
    ));
  }

  function toggleValue<T extends string>(value: T, setter: (update: (previous: T[]) => T[]) => void) {
    setter((previous) => (
      previous.includes(value)
        ? previous.filter((item) => item !== value)
        : [...previous, value]
    ));
  }

  function renderFilterChips<T extends string>(
    label: string,
    selected: T[],
    entries: Array<[T, string]>,
    setter: (update: (previous: T[]) => T[]) => void,
  ) {
    return (
      <div className="filterGroup">
        <div>
          <span>{label}</span>
          {selected.length > 0 && <button type="button" onClick={() => setter(() => [])}>전체</button>}
        </div>
        <div className="filterChips">
          {entries.map(([value, text]) => (
            <button
              type="button"
              className={selected.includes(value) ? "active" : ""}
              onClick={() => toggleValue(value, setter)}
              key={value}
            >
              {text}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <section className="explorer">
      <div className="toolbar">
        <label className="searchBox">
          <span>⌕</span>
          <input
            aria-label="공고 검색"
            placeholder="공고명, 회사, 기술 스택 검색"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={handleSearchKeyDown}
          />
        </label>
        <button className={`scanButton ${searchFeedback ? "searching" : ""}`} onClick={handleSearch}>{searchFeedback || "검색"}</button>
        <button className="ghostButton" onClick={() => downloadWorkbook(sortedJobs)} disabled={sortedJobs.length === 0}>엑셀 받기</button>
        <button className="ghostButton accent" onClick={() => setShowEmailModal(true)} disabled={sortedJobs.length === 0}>이메일로 보내기</button>
      </div>

      <div className="commutePanel" aria-label="네이버지도 경로 검색">
        <label>
          <span>출발지 주소</span>
          <input
            placeholder={originExamples}
            value={originAddress}
            onChange={(event) => setOriginAddress(event.target.value)}
            onBlur={() => originAddress.trim() && validateOriginForSearch()}
          />
        </label>
      </div>

      <div className="locationPanel" aria-label="지역 다중 선택 필터">
        <div>
          <span>지역 다중 선택</span>
          <p>{selectedLocations.length ? `${selectedLocations.length}개 지역 선택됨` : "서울·경기·인천의 시/구 단위로 여러 지역을 선택할 수 있어요."}</p>
        </div>
        <div className="locationChips">
          {locationOptions.map((location) => (
            <button
              type="button"
              className={selectedLocations.includes(location) ? "active" : ""}
              onClick={() => toggleLocationFilter(location)}
              key={location}
            >
              {location}
            </button>
          ))}
        </div>
        {selectedLocations.length > 0 && <button type="button" className="clearFilter" onClick={() => setSelectedLocations([])}>지역 전체 해제</button>}
      </div>

      <div className="filterPanel" aria-label="공고 조건 필터">
        {renderFilterChips("매칭 점수", scoreFilters, Object.entries(scoreFilterLabels) as Array<[ScoreFilterKey, string]>, setScoreFilters)}
        {renderFilterChips("경력", careerFilters, careerOptions.map((option) => [option, option]), setCareerFilters)}
        {renderFilterChips("고용형태", employmentFilters, employmentOptions.map((option) => [option, option]), setEmploymentFilters)}
      </div>

      <div className="explorerControls">
        <div className="viewSwitch" role="tablist" aria-label="공고 보기 방식">
          <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>리스트</button>
          <button className={view === "calendar" ? "active" : ""} onClick={() => setView("calendar")}>마감 달력</button>
          <button className={view === "expired" ? "active" : ""} onClick={() => setView("expired")}>마감 {expiredFilteredJobs.length}</button>
        </div>
      </div>

      {loading && <div className="emptyState"><span className="loader" /> 데이터를 정리하고 있어요.</div>}
      {error && <div className="emptyState error">{error}</div>}
      {!loading && !error && jobs.length === 0 && (
        <div className="emptyState">아직 표시할 공고가 없어요. 샘플 데이터를 넣거나 기존 DB를 연결해주세요.</div>
      )}
      {!loading && !error && jobs.length > 0 && filteredJobs.length === 0 && (
        <div className="emptyState">현재 조건에 맞는 공고가 없어요. 필터를 조정해주세요.</div>
      )}
      {!loading && !error && filteredJobs.length > 0 && sortedJobs.length === 0 && view !== "calendar" && (
        <div className="emptyState">{view === "expired" ? "현재 조건에 마감된 공고가 없어요." : "현재 조건에 진행 중인 공고가 없어요."}</div>
      )}

      {!loading && !error && sortedJobs.length > 0 && (view === "list" || view === "expired") && (
        <>
          <div className="tableHeader">
            <span>표시 {visibleStart}-{visibleEnd} · {view === "expired" ? "마감 공고" : "진행 공고"}</span>
            <label className="tableSort"><span>{view === "expired" ? "오늘 이전 마감" : "정렬"}</span><select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortKey)}>{Object.entries(sortLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </div>
          <div className="jobList">
            {pagedJobs.map((job, index) => (
              <article className={`jobRow ${viewedJobs.has(job.id) ? "viewed" : ""} ${job.is_favorite ? "favorite" : ""}`} key={job.id} style={{ "--delay": `${index * 25}ms` } as React.CSSProperties}>
                <div className="rowScore" style={{ "--score": `${job.match_score * 3.6}deg` } as React.CSSProperties}>
                  <strong>{job.match_score}</strong>
                  <small>MATCH</small>
                </div>
                <div className="rowMain">
                  <span className="company">
                    {job.company_name || "회사 미상"}
                    {Boolean(job.reopen_count) && <b className="statusBadge reopen">{job.reopen_count}번째 다시 올라온 공고</b>}
                  </span>
                  <h3>{job.title}</h3>
                  <div className="meta">
                    <span>{job.location || "지역 미정"}</span>
                    <span>{job.career || "경력 무관"}</span>
                    <span>{job.employment_type || "고용형태 미정"}</span>
                    <span>{formatPostedDate(job.posted_date)}</span>
                    <span>{formatDeadlineDate(job.deadline_date, job.deadline)}</span>
                    <span>{getEmployeeCount(job)}</span>
                  </div>
                  <div className="commuteLine">
                    <span>이동경로: {originAddress ? `${originAddress} → ${getDestination(job)}` : "출발지 입력 후 확인"}</span>
                    <div className="mapLinks">
                      <div className="mapTooltipWrap">
                        <a
                          href={buildNaverRouteSearchUrl(originAddress, getDestination(job))}
                          target="_blank"
                          rel="noreferrer"
                          aria-describedby={`map-help-${job.id}`}
                          onClick={(event) => handleRouteClick(event, job)}
                        >
                          네이버지도 열기 ↗
                        </a>
                        <small className="mapTooltip" id={`map-help-${job.id}`} role="tooltip">
                          네이버지도 길찾기창에 입력한 출발지와 공고 주소가 들어가 있어요. 출발지 입력칸에서 Enter를 눌러 후보를 선택하고, 도착지도 후보를 적용한 뒤 길찾기를 누르면 대중교통 경로가 나옵니다.
                        </small>
                      </div>
                    </div>
                  </div>
                  <div className="keywords">
                    {job.matched_keywords.slice(0, 5).map((keyword) => <span key={keyword}>#{keyword}</span>)}
                  </div>
                  <p className="reason">{job.positive_reasons[0] || "저장된 조건을 기준으로 분석한 공고입니다."}</p>
                  {job.is_favorite && (
                    <input
                      className="memoInput"
                      aria-label="관심공고 메모"
                      defaultValue={job.favorite_memo ?? ""}
                      placeholder="지원 전 확인할 내용을 메모하세요"
                      onBlur={(event) => void changeMemo(job, event.target.value)}
                    />
                  )}
                </div>
                <div className="rowActions">
                  <button
                    aria-label={job.is_favorite ? "관심공고 해제" : "관심공고 저장"}
                    className={`favoriteButton ${job.is_favorite ? "active" : ""}`}
                    onClick={() => void toggleFavorite(job)}
                  >{job.is_favorite ? "♥ 저장됨" : "♡ 저장"}</button>
                  {!favoriteOnly && (
                    <button
                      aria-label="별로 표시하고 목록에서 숨기기"
                      className="dislikeButton"
                      onClick={() => void dislikeJob(job)}
                    >* 별로</button>
                  )}
                  {job.is_favorite && (
                    <select
                      aria-label="지원 상태"
                      value={job.favorite_status ?? "planned"}
                      onChange={(event) => void changeStatus(job, event.target.value)}
                    >
                      {Object.entries(statusLabel).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                  )}
                  {job.detail_url && <a href={job.detail_url} target="_blank" rel="noreferrer" onClick={() => markViewed(job.id)}>원문 보기 ↗</a>}
                  <button onClick={() => void openSnapshot(job)}>저장 스냅샷</button>
                </div>
              </article>
            ))}
          </div>
          <div className="pagination" aria-label="공고 페이지네이션">
            <button disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>←</button>
            <strong>{currentPage} / {totalPages}</strong>
            <button disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>→</button>
            <label className="pageSizeSelect bottom">
              <span>하단 옵션</span>
              <select
                value={pageSize}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
              >
                {pageSizeOptions.map((option) => <option key={option} value={option}>{option}개씩</option>)}
              </select>
            </label>
          </div>
        </>
      )}

      {!loading && !error && filteredJobs.length > 0 && view === "calendar" && (
        <div className="deadlineCalendar">
          <div className="calendarHeader">
            <button onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1))}>←</button>
            <strong>{formatMonth(calendarMonth)}</strong>
            <button onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))}>→</button>
          </div>
          <div className="calendarWeek">
            {weekDays.map((day) => <span key={day}>{day}</span>)}
          </div>
          <div className="calendarGrid">
            {getCalendarDays(calendarMonth).map((day, index) => {
              const dateKey = day ? toDateKey(day) : "";
              const dayJobs = dateKey ? jobsByDeadline[dateKey] ?? [] : [];
              const isToday = dateKey === todayKey;
              return (
                <div className={`calendarCell ${dayJobs.length ? "hasJobs" : ""} ${isToday ? "today" : ""}`} key={`${dateKey}-${index}`}>
                  {day && (
                    <span className="dayNumber">
                      {day.getDate()}
                      {isToday && <b>TODAY</b>}
                    </span>
                  )}
                  {dayJobs.slice(0, 3).map((job) => (
                    <a className="deadlinePill" href={job.detail_url ?? "#"} target="_blank" rel="noreferrer" key={job.id}>
                      <b>{job.match_score}</b> {job.company_name || "회사 미상"}
                    </a>
                  ))}
                  {dayJobs.length > 3 && <small className="moreJobs">+{dayJobs.length - 3}개 더</small>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {showEmailModal && (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setShowEmailModal(false)}>
          <div className="emailModal" role="dialog" aria-modal="true" aria-labelledby="email-modal-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="modalClose" aria-label="닫기" onClick={() => setShowEmailModal(false)}>×</button>
            <span className="modalKicker">REPORT EXPORT</span>
            <h3 id="email-modal-title">엑셀 결과를 이메일로 보내기</h3>
            <p>
              받을 이메일을 입력하면 현재 필터 결과를 엑셀 리포트로 정리해요.
              {reportServerReady
                ? " 지금은 발송 서버가 연결되어 있어요."
                : " 지금은 발송 서버가 아직 연결되지 않았어요. 서버가 연결되면 이 버튼으로 바로 발송됩니다."}
            </p>
            <input
              aria-label="받을 이메일"
              placeholder="name@example.com"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && void submitEmail()}
            />
            <button className="scanButton wide" onClick={() => void submitEmail()} disabled={emailSending}>
              {emailSending ? "보내는 중..." : reportServerReady ? "엑셀 리포트 보내기" : "Gmail로 열기"}
            </button>
            {emailStatus && <small>{emailStatus}</small>}
            {!reportServerReady && (
              <a className="mailFallback" href={buildEmailReportMailto(email || "name@example.com", sortedJobs)}>
                기본 메일 앱으로 열기
              </a>
            )}
          </div>
        </div>
      )}

      {noticeModal && (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setNoticeModal(null)}>
          <div className="emailModal noticeModal" role="alertdialog" aria-modal="true" aria-labelledby="notice-modal-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="modalClose" aria-label="닫기" onClick={() => setNoticeModal(null)}>×</button>
            <span className="modalKicker">CHECK REQUIRED</span>
            <h3 id="notice-modal-title">{noticeModal.title}</h3>
            <p>{noticeModal.message}</p>
            {noticeModal.hint && <small>{noticeModal.hint}</small>}
            <button className="scanButton wide" onClick={() => setNoticeModal(null)}>확인</button>
          </div>
        </div>
      )}

      {snapshotModal && (
        <div className="modalBackdrop" role="presentation" onMouseDown={() => setSnapshotModal(null)}>
          <div className="emailModal snapshotModal" role="dialog" aria-modal="true" aria-labelledby="snapshot-modal-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="modalClose" aria-label="닫기" onClick={() => setSnapshotModal(null)}>×</button>
            <span className="modalKicker">SAVED SNAPSHOT</span>
            <h3 id="snapshot-modal-title">{snapshotModal.title}</h3>
            <div className="snapshotTable">
              {buildSnapshotRows(snapshotModal.title, snapshotModal.body).map(([label, value]) => (
                <div className="snapshotRow" key={label}>
                  <strong>{label}</strong>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
