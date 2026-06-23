"use client";

import { MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
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
const sortLabels = {
  match_desc: "매칭 점수 높은순",
  deadline_asc: "마감 임박순",
  deadline_desc: "마감 여유순",
  posted_desc: "등록 최신순",
  posted_asc: "등록 오래된순",
  company_asc: "회사명 가나다순",
} as const;
type SortKey = keyof typeof sortLabels;
const allowedLocationPrefixes = ["서울", "서울특별시", "경기", "경기도", "인천", "인천광역시"];

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

function getMailBody(fileName: string) {
  return encodeURIComponent(
    `JobRadar 공고 분석 결과를 보냅니다.\n\nGitHub Pages 데모에서는 보안상 파일 자동 첨부가 불가해서, 방금 다운로드된 ${fileName} 파일을 첨부해주세요.`,
  );
}

function validateOriginAddress(value: string) {
  const trimmed = value.trim();
  if (trimmed.length < 2) return "출발지를 2글자 이상 입력해주세요.";
  if (!/[가-힣a-zA-Z0-9]/.test(trimmed)) return "한글 주소, 장소명, 역명 중 하나로 입력해주세요.";
  if (/^[0-9\s-]+$/.test(trimmed)) return "숫자만으로는 위치를 찾기 어려워요. 장소명이나 도로명 주소를 함께 입력해주세요.";
  return "";
}

function getDestination(job: Job) {
  return job.location || job.company_name || job.title;
}

function buildNaverRouteSearchUrl(origin: string, destination: string) {
  const query = origin.trim()
    ? `${origin.trim()}에서 ${destination.trim()}까지 길찾기`
    : `${destination.trim()} 길찾기`;
  return `https://map.naver.com/p/search/${encodeURIComponent(query)}`;
}

function buildNaverPlaceSearchUrl(destination: string) {
  return `https://map.naver.com/p/search/${encodeURIComponent(destination.trim())}`;
}

export default function JobExplorer({ favoriteOnly = false }: { favoriteOnly?: boolean }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState("");
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [detailFilter, setDetailFilter] = useState("all");
  const [scoreFilter, setScoreFilter] = useState("all");
  const [employmentFilter, setEmploymentFilter] = useState("all");
  const [sortBy, setSortBy] = useState<SortKey>("match_desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"list" | "calendar">("list");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [email, setEmail] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [emailSending, setEmailSending] = useState(false);
  const [reportServerReady, setReportServerReady] = useState(false);
  const [originAddress, setOriginAddress] = useState("");
  const [noticeModal, setNoticeModal] = useState<{ title: string; message: string; hint?: string } | null>(null);

  const loadJobs = useCallback(async (term = "") => {
    setLoading(true);
    try {
      const result = await api.jobs(term, favoriteOnly);
      setJobs(result.items);
      setPage(1);
      setCalendarMonth(getInitialMonth(result.items));
      setError("");
    } catch {
      setError("API에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.");
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly]);

  useEffect(() => { void loadJobs(); }, [loadJobs]);
  useEffect(() => {
    api.reportStatus()
      .then((status) => setReportServerReady(status.ready))
      .catch(() => setReportServerReady(false));
  }, []);

  const employmentOptions = useMemo(() => (
    Array.from(new Set(jobs.map((job) => job.employment_type).filter(Boolean))).sort() as string[]
  ), [jobs]);
  const locationOptions = useMemo(() => (
    Array.from(new Set(jobs.map((job) => normalizeLocationOption(job.location)).filter(Boolean) as string[]))
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
        if (detailFilter === "all") return true;
        if (detailFilter === "success") return job.detail_status === "success";
        return job.detail_status !== "success";
      })
      .filter((job) => {
        if (scoreFilter === "all") return true;
        if (scoreFilter === "strong") return job.match_score >= 85;
        if (scoreFilter === "good") return job.match_score >= 65 && job.match_score < 85;
        if (scoreFilter === "possible") return job.match_score > 0 && job.match_score < 65;
        return job.match_score === 0;
      })
      .filter((job) => employmentFilter === "all" || job.employment_type === employmentFilter)
  ), [detailFilter, employmentFilter, jobs, scoreFilter, selectedLocations]);

  const sortedJobs = useMemo(() => {
    const farFuture = 8640000000000000;
    const farPast = -8640000000000000;
    return [...filteredJobs].sort((a, b) => {
      if (a.is_favorite !== b.is_favorite) return a.is_favorite ? -1 : 1;
      if (sortBy === "deadline_asc") {
        return getDateTime(a.deadline_date, farFuture) - getDateTime(b.deadline_date, farFuture);
      }
      if (sortBy === "deadline_desc") {
        return getDateTime(b.deadline_date, farPast) - getDateTime(a.deadline_date, farPast);
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
  }, [filteredJobs, sortBy]);

  useEffect(() => {
    setPage(1);
  }, [detailFilter, employmentFilter, scoreFilter, selectedLocations, sortBy]);

  const jobsByDeadline = useMemo(() => {
    return filteredJobs.reduce<Record<string, Job[]>>((acc, job) => {
      if (!job.deadline_date) return acc;
      acc[job.deadline_date] = [...(acc[job.deadline_date] ?? []), job];
      return acc;
    }, {});
  }, [filteredJobs]);

  const totalPages = Math.max(1, Math.ceil(sortedJobs.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedJobs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedJobs.slice(start, start + pageSize);
  }, [currentPage, pageSize, sortedJobs]);
  const matchedCount = jobs.filter((job) => job.match_score > 0).length;
  const detailedCount = jobs.filter((job) => job.detail_status === "success").length;
  const visibleStart = sortedJobs.length ? (currentPage - 1) * pageSize + 1 : 0;
  const visibleEnd = Math.min(currentPage * pageSize, sortedJobs.length);

  async function toggleFavorite(job: Job) {
    if (job.is_favorite) await api.unfavorite(job.id);
    else await api.favorite(job.id);
    await loadJobs(search);
  }

  async function changeStatus(job: Job, status: string) {
    await api.updateFavorite(job.id, job.favorite_memo ?? "", status);
    await loadJobs(search);
  }

  async function submitEmail() {
    if (!email.includes("@")) {
      setEmailStatus("이메일 주소를 다시 확인해주세요.");
      return;
    }

    setEmailSending(true);
    setEmailStatus("");
    try {
      if (api.canEmailReport()) {
        await api.emailReport(email, sortedJobs);
        setEmailStatus("엑셀 리포트를 이메일로 보냈어요.");
        return;
      }

      const file = downloadWorkbook(sortedJobs);
      window.location.href = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent("JobRadar 공고 분석 결과")}&body=${getMailBody(file.name)}`;
      setEmailStatus("정적 데모라 자동 첨부 대신 엑셀을 다운로드하고 메일 작성창을 열었어요.");
    } catch {
      setEmailStatus("발송 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setEmailSending(false);
    }
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
    }
  }

  function toggleLocationFilter(location: string) {
    setSelectedLocations((previous) => (
      previous.includes(location)
        ? previous.filter((item) => item !== location)
        : [...previous, location]
    ));
  }

  return (
    <section className="explorer">
      <div className="opsStrip" aria-label="운영 상태">
        <span><i className="liveDot" />LIVE SNAPSHOT</span>
        <span>수집 {jobs.length.toString().padStart(2, "0")}</span>
        <span>상세 {detailedCount.toString().padStart(2, "0")}</span>
        <span>매칭 {matchedCount.toString().padStart(2, "0")}</span>
        <span className={reportServerReady ? "ready" : "muted"}>
          {reportServerReady ? "메일 서버 연결됨" : "메일 서버 설정 대기"}
        </span>
        <span className="ready">네이버지도 검색 연결</span>
      </div>

      <div className="toolbar">
        <label className="searchBox">
          <span>⌕</span>
          <input
            aria-label="공고 검색"
            placeholder="공고명, 회사, 기술 스택 검색"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && void loadJobs(search)}
          />
        </label>
        <button className="scanButton" onClick={() => void loadJobs(search)}>SCAN DATA</button>
        <button className="ghostButton" onClick={() => downloadWorkbook(sortedJobs)} disabled={sortedJobs.length === 0}>엑셀 받기</button>
        <button className="ghostButton accent" onClick={() => setShowEmailModal(true)} disabled={sortedJobs.length === 0}>이메일로 보내기</button>
        <span className="resultCount">{filteredJobs.length.toString().padStart(2, "0")} / {jobs.length.toString().padStart(2, "0")} RESULTS</span>
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
        <small>공고별 버튼을 누르면 `출발지에서 도착지까지 길찾기` 검색어로 네이버지도를 새 탭에서 엽니다.</small>
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
        <label><span>수집 상태</span><select value={detailFilter} onChange={(event) => setDetailFilter(event.target.value)}><option value="all">전체</option><option value="success">상세완료</option><option value="pending">목록수집</option></select></label>
        <label><span>매칭 점수</span><select value={scoreFilter} onChange={(event) => setScoreFilter(event.target.value)}><option value="all">전체</option><option value="strong">85점 이상</option><option value="good">65~84점</option><option value="possible">1~64점</option><option value="unscored">미분석</option></select></label>
        <label><span>고용형태</span><select value={employmentFilter} onChange={(event) => setEmploymentFilter(event.target.value)}><option value="all">전체</option>{employmentOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label><span>정렬</span><select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortKey)}>{Object.entries(sortLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </div>

      <div className="explorerControls">
        <div className="viewSwitch" role="tablist" aria-label="공고 보기 방식">
          <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>리스트</button>
          <button className={view === "calendar" ? "active" : ""} onClick={() => setView("calendar")}>마감 달력</button>
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

      {!loading && !error && filteredJobs.length > 0 && view === "list" && (
        <>
          <div className="tableHeader">
            <span>표시 {visibleStart}-{visibleEnd} / 필터 결과 {filteredJobs.length} / 전체 {jobs.length}</span>
            <span>{sortLabels[sortBy]} · 관심공고 우선</span>
          </div>
          <div className="jobList">
            {pagedJobs.map((job, index) => (
              <article className="jobRow" key={job.id} style={{ "--delay": `${index * 25}ms` } as React.CSSProperties}>
                <div className="rowScore" style={{ "--score": `${job.match_score * 3.6}deg` } as React.CSSProperties}>
                  <strong>{job.match_score}</strong>
                  <small>MATCH</small>
                </div>
                <div className="rowMain">
                  <span className="company">{job.company_name || "회사 미상"} <b className={`statusBadge ${job.detail_status === "success" ? "done" : "pending"}`}>{job.detail_status === "success" ? "상세완료" : "목록수집"}</b></span>
                  <h3>{job.title}</h3>
                  <div className="meta">
                    <span>{job.location || "지역 미정"}</span>
                    <span>{job.career || "경력 무관"}</span>
                    <span>{job.employment_type || "고용형태 미정"}</span>
                    <span>등록 {job.posted_date || "미정"}</span>
                    <span>{job.deadline_date || job.deadline || "마감일 미정"}</span>
                  </div>
                  <div className="commuteLine">
                    <span>이동경로: {originAddress ? `${originAddress} → ${getDestination(job)}` : "출발지 입력 후 확인"}</span>
                    <div className="mapLinks">
                      <a
                        href={buildNaverPlaceSearchUrl(getDestination(job))}
                        target="_blank"
                        rel="noreferrer"
                      >
                        네이버지도 열기 ↗
                      </a>
                      <a
                        href={buildNaverRouteSearchUrl(originAddress, getDestination(job))}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(event) => handleRouteClick(event, job)}
                      >
                        경로 확인하기 ↗
                      </a>
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
                      onBlur={(event) => void api.updateFavorite(
                        job.id,
                        event.target.value,
                        job.favorite_status ?? "planned",
                      )}
                    />
                  )}
                </div>
                <div className="rowActions">
                  <button
                    aria-label={job.is_favorite ? "관심공고 해제" : "관심공고 저장"}
                    className={`favoriteButton ${job.is_favorite ? "active" : ""}`}
                    onClick={() => void toggleFavorite(job)}
                  >{job.is_favorite ? "♥ 저장됨" : "♡ 저장"}</button>
                  {job.is_favorite && (
                    <select
                      aria-label="지원 상태"
                      value={job.favorite_status ?? "planned"}
                      onChange={(event) => void changeStatus(job, event.target.value)}
                    >
                      {Object.entries(statusLabel).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                  )}
                  {job.detail_url && <a href={job.detail_url} target="_blank" rel="noreferrer">원문 보기 ↗</a>}
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
            <strong>{formatMonth(calendarMonth)} 마감 캘린더</strong>
            <button onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))}>→</button>
          </div>
          <div className="calendarWeek">
            {weekDays.map((day) => <span key={day}>{day}</span>)}
          </div>
          <div className="calendarGrid">
            {getCalendarDays(calendarMonth).map((day, index) => {
              const dateKey = day ? toDateKey(day) : "";
              const dayJobs = dateKey ? jobsByDeadline[dateKey] ?? [] : [];
              return (
                <div className={`calendarCell ${dayJobs.length ? "hasJobs" : ""}`} key={`${dateKey}-${index}`}>
                  {day && <span className="dayNumber">{day.getDate()}</span>}
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
              {reportServerReady ? " 지금은 발송 서버가 연결되어 있어요." : " 발송 서버 설정 전에는 엑셀 다운로드와 메일 작성창으로 대체됩니다."}
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
              {emailSending ? "보내는 중..." : "엑셀 리포트 보내기"}
            </button>
            {emailStatus && <small>{emailStatus}</small>}
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
    </section>
  );
}
