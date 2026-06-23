"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Job } from "@/services/api";
import { downloadWorkbook } from "@/services/export-xlsx";

const statusLabel: Record<string, string> = {
  saved: "저장",
  planned: "지원 예정",
  applied: "지원 완료",
  excluded: "제외",
};

const weekDays = ["일", "월", "화", "수", "목", "금", "토"];

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

export default function JobExplorer({ favoriteOnly = false }: { favoriteOnly?: boolean }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"list" | "calendar">("list");
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [email, setEmail] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [emailSending, setEmailSending] = useState(false);

  const loadJobs = useCallback(async (term = "") => {
    setLoading(true);
    try {
      const result = await api.jobs(term, favoriteOnly);
      setJobs(result.items);
      setCalendarMonth(getInitialMonth(result.items));
      setError("");
    } catch {
      setError("API에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.");
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly]);

  useEffect(() => { void loadJobs(); }, [loadJobs]);

  const jobsByDeadline = useMemo(() => {
    return jobs.reduce<Record<string, Job[]>>((acc, job) => {
      if (!job.deadline_date) return acc;
      acc[job.deadline_date] = [...(acc[job.deadline_date] ?? []), job];
      return acc;
    }, {});
  }, [jobs]);

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
        await api.emailReport(email, jobs);
        setEmailStatus("엑셀 리포트를 이메일로 보냈어요.");
        return;
      }

      const file = downloadWorkbook(jobs);
      window.location.href = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent("JobRadar 공고 분석 결과")}&body=${getMailBody(file.name)}`;
      setEmailStatus("정적 데모라 자동 첨부 대신 엑셀을 다운로드하고 메일 작성창을 열었어요.");
    } catch {
      setEmailStatus("발송 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.");
    } finally {
      setEmailSending(false);
    }
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
            onKeyDown={(event) => event.key === "Enter" && void loadJobs(search)}
          />
        </label>
        <button className="scanButton" onClick={() => void loadJobs(search)}>SCAN DATA</button>
        <button className="ghostButton" onClick={() => downloadWorkbook(jobs)} disabled={jobs.length === 0}>엑셀 받기</button>
        <button className="ghostButton accent" onClick={() => setShowEmailModal(true)} disabled={jobs.length === 0}>이메일로 보내기</button>
        <span className="resultCount">{jobs.length.toString().padStart(2, "0")} RESULTS</span>
      </div>

      <div className="viewSwitch" role="tablist" aria-label="공고 보기 방식">
        <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>리스트</button>
        <button className={view === "calendar" ? "active" : ""} onClick={() => setView("calendar")}>마감 달력</button>
      </div>

      {loading && <div className="emptyState"><span className="loader" /> 데이터를 정리하고 있어요.</div>}
      {error && <div className="emptyState error">{error}</div>}
      {!loading && !error && jobs.length === 0 && (
        <div className="emptyState">아직 표시할 공고가 없어요. 샘플 데이터를 넣거나 기존 DB를 연결해주세요.</div>
      )}

      {!loading && !error && jobs.length > 0 && view === "list" && (
        <div className="jobList">
          {jobs.map((job, index) => (
            <article className="jobRow" key={job.id} style={{ "--delay": `${index * 25}ms` } as React.CSSProperties}>
              <div className="rowScore" style={{ "--score": `${job.match_score * 3.6}deg` } as React.CSSProperties}>
                <strong>{job.match_score}</strong>
                <small>MATCH</small>
              </div>
              <div className="rowMain">
                <span className="company">{job.company_name || "회사 미상"}</span>
                <h3>{job.title}</h3>
                <div className="meta">
                  <span>{job.location || "지역 미정"}</span>
                  <span>{job.career || "경력 무관"}</span>
                  <span>{job.employment_type || "고용형태 미정"}</span>
                  <span>{job.deadline_date || job.deadline || "마감일 미정"}</span>
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
                      job.favorite_status ?? "saved",
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
                    value={job.favorite_status ?? "saved"}
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
      )}

      {!loading && !error && jobs.length > 0 && view === "calendar" && (
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
            <p>받을 이메일을 입력하면 현재 화면의 공고 리스트를 엑셀 리포트로 정리해요.</p>
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
    </section>
  );
}
