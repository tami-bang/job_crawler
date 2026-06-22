"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Job } from "@/services/api";

const statusLabel: Record<string, string> = {
  saved: "저장",
  planned: "지원 예정",
  applied: "지원 완료",
  excluded: "제외",
};

export default function JobExplorer({ favoriteOnly = false }: { favoriteOnly?: boolean }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadJobs = useCallback(async (term = "") => {
    setLoading(true);
    try {
      const result = await api.jobs(term, favoriteOnly);
      setJobs(result.items);
      setError("");
    } catch {
      setError("API에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.");
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly]);

  useEffect(() => { void loadJobs(); }, [loadJobs]);

  async function toggleFavorite(job: Job) {
    if (job.is_favorite) await api.unfavorite(job.id);
    else await api.favorite(job.id);
    await loadJobs(search);
  }

  async function changeStatus(job: Job, status: string) {
    await api.updateFavorite(job.id, job.favorite_memo ?? "", status);
    await loadJobs(search);
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
        <span className="resultCount">{jobs.length.toString().padStart(2, "0")} RESULTS</span>
      </div>

      {loading && <div className="emptyState"><span className="loader" /> 데이터를 정리하고 있어요.</div>}
      {error && <div className="emptyState error">{error}</div>}
      {!loading && !error && jobs.length === 0 && (
        <div className="emptyState">아직 표시할 공고가 없어요. 샘플 데이터를 넣거나 기존 DB를 연결해주세요.</div>
      )}

      <div className="jobGrid">
        {jobs.map((job, index) => (
          <article className="jobCard" key={job.id} style={{ "--delay": `${index * 45}ms` } as React.CSSProperties}>
            <div className="cardTop">
              <div>
                <span className="company">{job.company_name || "회사 미상"}</span>
                <h3>{job.title}</h3>
              </div>
              <div className="score" style={{ "--score": `${job.match_score * 3.6}deg` } as React.CSSProperties}>
                <strong>{job.match_score}</strong><small>MATCH</small>
              </div>
            </div>
            <div className="meta">
              <span>{job.location || "지역 미정"}</span>
              <span>{job.career || "경력 무관"}</span>
              <span>{job.employment_type || "고용형태 미정"}</span>
            </div>
            <div className="keywords">
              {job.matched_keywords.slice(0, 4).map((keyword) => <span key={keyword}>#{keyword}</span>)}
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
            <div className="cardActions">
              <button
                aria-label={job.is_favorite ? "관심공고 해제" : "관심공고 저장"}
                className={`favoriteButton ${job.is_favorite ? "active" : ""}`}
                onClick={() => void toggleFavorite(job)}
              >{job.is_favorite ? "♥ SAVED" : "♡ SAVE"}</button>
              {job.is_favorite && (
                <select
                  aria-label="지원 상태"
                  value={job.favorite_status ?? "saved"}
                  onChange={(event) => void changeStatus(job, event.target.value)}
                >
                  {Object.entries(statusLabel).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              )}
              {job.detail_url && <a href={job.detail_url} target="_blank" rel="noreferrer">원문 ↗</a>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
