"use client";

import { useEffect, useState } from "react";
import { api, Stats } from "@/services/api";

const initial: Stats = { total_jobs: 0, detailed_jobs: 0, matched_jobs: 0, favorite_jobs: 0, average_score: 0 };

export default function StatsPanel() {
  const [stats, setStats] = useState(initial);
  useEffect(() => {
    const refresh = () => { api.stats().then(setStats).catch(() => undefined); };
    refresh();
    window.addEventListener("job-radar-favorites-updated", refresh);
    return () => window.removeEventListener("job-radar-favorites-updated", refresh);
  }, []);
  const cards = [
    ["TOTAL", stats.total_jobs, "수집 공고", "수집 파이프라인을 통해 DB에 적재된 전체 채용 공고 수입니다."],
    ["DETAIL", stats.detailed_jobs, "상세 완료", "공고 상세 본문 및 자격 요건 파싱이 완료된 공고 수입니다."],
    ["MATCH", stats.matched_jobs, "분석 완료", "매칭 알고리즘 분석 및 적합도 점수 산출이 완료된 공고 수입니다."],
    ["SAVED", stats.favorite_jobs, "관심 공고", "내가 관심 등록(저장)하여 관리 중인 공고 수입니다."],
  ];
  return (
    <div className="statsGrid">
      {cards.map(([code, value, label, description]) => (
        <article className="statCard relative group cursor-help transition-all" key={String(code)}>
          <span>{code}</span><strong>{String(value).padStart(2, "0")}</strong><small>{label}</small>
          <div className="statTooltip pointer-events-none absolute -top-12 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-50 whitespace-nowrap rounded-md bg-zinc-900/95 border border-zinc-700 px-3 py-1.5 text-xs text-zinc-200 shadow-xl backdrop-blur-sm">
            {description}
            <div className="statTooltipArrow absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-zinc-700" />
          </div>
        </article>
      ))}
    </div>
  );
}
