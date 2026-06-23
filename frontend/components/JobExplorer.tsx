"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, CommuteEstimate, Job } from "@/services/api";
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

export default function JobExplorer({ favoriteOnly = false }: { favoriteOnly?: boolean }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState("");
  const [locationFilter, setLocationFilter] = useState("all");
  const [detailFilter, setDetailFilter] = useState("all");
  const [scoreFilter, setScoreFilter] = useState("all");
  const [employmentFilter, setEmploymentFilter] = useState("all");
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
  const [mapServerReady, setMapServerReady] = useState(false);
  const [originAddress, setOriginAddress] = useState("");
  const [commuteEstimates, setCommuteEstimates] = useState<Record<number, CommuteEstimate>>({});
  const [commuteLoading, setCommuteLoading] = useState(false);
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
    api.mapStatus()
      .then((status) => setMapServerReady(status.ready))
      .catch(() => setMapServerReady(false));
  }, []);

  const employmentOptions = useMemo(() => (
    Array.from(new Set(jobs.map((job) => job.employment_type).filter(Boolean))).sort() as string[]
  ), [jobs]);

  const filteredJobs = useMemo(() => (
    jobs
      .filter((job) => locationFilter === "all" || job.location?.includes(locationFilter))
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
  ), [detailFilter, employmentFilter, jobs, locationFilter, scoreFilter]);

  useEffect(() => {
    setPage(1);
  }, [detailFilter, employmentFilter, locationFilter, scoreFilter]);

  const jobsByDeadline = useMemo(() => {
    return filteredJobs.reduce<Record<string, Job[]>>((acc, job) => {
      if (!job.deadline_date) return acc;
      acc[job.deadline_date] = [...(acc[job.deadline_date] ?? []), job];
      return acc;
    }, {});
  }, [filteredJobs]);

  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedJobs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredJobs.slice(start, start + pageSize);
  }, [currentPage, filteredJobs, pageSize]);
  const matchedCount = jobs.filter((job) => job.match_score > 0).length;
  const detailedCount = jobs.filter((job) => job.detail_status === "success").length;
  const visibleStart = filteredJobs.length ? (currentPage - 1) * pageSize + 1 : 0;
  const visibleEnd = Math.min(currentPage * pageSize, filteredJobs.length);

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
        await api.emailReport(email, filteredJobs);
        setEmailStatus("엑셀 리포트를 이메일로 보냈어요.");
        return;
      }

      const file = downloadWorkbook(filteredJobs);
      window.location.href = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent("JobRadar 공고 분석 결과")}&body=${getMailBody(file.name)}`;
      setEmailStatus("정적 데모라 자동 첨부 대신 엑셀을 다운로드하고 메일 작성창을 열었어요.");
    } catch {
      setEmailStatus("발송 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setEmailSending(false);
    }
  }

  async function calculateCommutes() {
    const validationMessage = validateOriginAddress(originAddress);
    if (validationMessage) {
      setNoticeModal({
        title: "출발지 주소를 확인해주세요",
        message: validationMessage,
        hint: originExamples,
      });
      return;
    }
    if (!mapServerReady) {
      setNoticeModal({
        title: "네이버지도 API 연결이 필요해요",
        message: "예상소요시간을 실제로 계산하려면 FastAPI 백엔드에 네이버지도 API 키와 공개 백엔드 URL을 연결해야 합니다.",
        hint: "필요 값: NAVER_MAPS_CLIENT_ID, NAVER_MAPS_CLIENT_SECRET, NEXT_PUBLIC_REPORT_API_URL",
      });
      return;
    }
    setCommuteLoading(true);
    try {
      const entries = await Promise.all(
        pagedJobs.map(async (job) => {
          const destination = job.location || job.company_name || job.title;
          const estimate = await api.commuteEstimate(originAddress, destination);
          return [job.id, estimate] as const;
        }),
      );
      setCommuteEstimates((previous) => ({ ...previous, ...Object.fromEntries(entries) }));
    } finally {
      setCommuteLoading(false);
    }
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
        <span className={mapServerReady ? "ready" : "muted"}>
          {mapServerReady ? "지도 API 연결됨" : "지도 API 설정 대기"}
        </span>
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
        <button className="ghostButton" onClick={() => downloadWorkbook(filteredJobs)} disabled={filteredJobs.length === 0}>엑셀 받기</button>
        <button className="ghostButton accent" onClick={() => setShowEmailModal(true)} disabled={filteredJobs.length === 0}>이메일로 보내기</button>
        <span className="resultCount">{filteredJobs.length.toString().padStart(2, "0")} / {jobs.length.toString().padStart(2, "0")} RESULTS</span>
      </div>

      <div className="commutePanel" aria-label="네이버지도 예상 소요시간">
        <label>
          <span>출발지 주소</span>
          <input
            placeholder={originExamples}
            value={originAddress}
            onChange={(event) => setOriginAddress(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && void calculateCommutes()}
          />
        </label>
        <button className="ghostButton" onClick={() => void calculateCommutes()} disabled={!originAddress.trim() || commuteLoading || pagedJobs.length === 0}>
          {commuteLoading ? "계산 중..." : "예상소요시간 함께 보기"}
        </button>
        <small>{mapServerReady ? "필터 결과에 네이버지도 기준 예상 이동시간을 함께 표시합니다." : "네이버지도 API 키를 연결하면 실제 예상 시간이 표시됩니다."}</small>
      </div>

      <div className="filterPanel" aria-label="공고 조건 필터">
        <label><span>지역</span><select value={locationFilter} onChange={(event) => setLocationFilter(event.target.value)}><option value="all">전체</option><option value="서울">서울</option><option value="경기">경기</option><option value="인천">인천</option></select></label>
        <label><span>수집 상태</span><select value={detailFilter} onChange={(event) => setDetailFilter(event.target.value)}><option value="all">전체</option><option value="success">상세완료</option><option value="pending">목록수집</option></select></label>
        <label><span>매칭 점수</span><select value={scoreFilter} onChange={(event) => setScoreFilter(event.target.value)}><option value="all">전체</option><option value="strong">85점 이상</option><option value="good">65~84점</option><option value="possible">1~64점</option><option value="unscored">미분석</option></select></label>
        <label><span>고용형태</span><select value={employmentFilter} onChange={(event) => setEmploymentFilter(event.target.value)}><option value="all">전체</option>{employmentOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
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
            <span>점수 높은 순 · 관심공고 우선</span>
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
                    <span>{job.deadline_date || job.deadline || "마감일 미정"}</span>
                  </div>
                  <div className="commuteLine">
                    <span>예상소요시간: {commuteEstimates[job.id]?.label ?? (originAddress ? "계산 전" : "출발지 입력")}</span>
                    {(commuteEstimates[job.id]?.map_url || job.location) && (
                      <a
                        href={commuteEstimates[job.id]?.map_url ?? `https://map.naver.com/p/search/${encodeURIComponent(job.location ?? "")}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        네이버지도 ↗
                      </a>
                    )}
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
