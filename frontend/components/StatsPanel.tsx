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
    ["TOTAL", stats.total_jobs, "수집 공고"],
    ["DETAIL", stats.detailed_jobs, "상세 완료"],
    ["MATCH", stats.matched_jobs, "분석 완료"],
    ["SAVED", stats.favorite_jobs, "관심공고"],
  ];
  return (
    <div className="statsGrid">
      {cards.map(([code, value, label]) => (
        <article className="statCard" key={String(code)}>
          <span>{code}</span><strong>{String(value).padStart(2, "0")}</strong><small>{label}</small>
        </article>
      ))}
    </div>
  );
}
