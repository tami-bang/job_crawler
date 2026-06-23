export type Job = {
  id: number;
  title: string;
  company_name: string | null;
  location: string | null;
  career: string | null;
  employment_type: string | null;
  posted_date: string | null;
  deadline: string | null;
  deadline_date: string | null;
  detail_url: string | null;
  skill_candidates: string | null;
  detail_status?: string | null;
  match_score: number;
  recommendation_level: string | null;
  matched_keywords: string[];
  positive_reasons: string[];
  negative_reasons: string[];
  is_favorite: boolean;
  favorite_memo: string | null;
  favorite_status: string | null;
};

export type Stats = {
  total_jobs: number;
  detailed_jobs: number;
  matched_jobs: number;
  favorite_jobs: number;
  average_score: number | null;
};

export type CommuteEstimate = {
  available: boolean;
  duration_minutes: number | null;
  label: string;
  map_url: string | null;
  reason?: string | null;
};

type FavoriteState = Record<number, { memo: string; status: string }>;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const STATIC_DEMO = process.env.NEXT_PUBLIC_STATIC_DEMO === "true";
const REPORT_API_URL = process.env.NEXT_PUBLIC_REPORT_API_URL?.replace(/\/$/, "") ?? "";
const FAVORITES_KEY = "job-radar-demo-favorites";

function getReportDeadline(job: Job) {
  if (job.deadline?.includes("상시")) return job.deadline;
  return job.deadline_date || job.deadline || "";
}

async function getDemoJobs(search = "", favoriteOnly = false): Promise<Job[]> {
  const { demoJobs } = await import("./demo-data");
  const favorites = readFavorites();
  const term = search.trim().toLowerCase();

  return demoJobs
    .map((job) => ({
      ...job,
      is_favorite: Boolean(favorites[job.id]),
      favorite_memo: favorites[job.id]?.memo ?? null,
      favorite_status: favorites[job.id]?.status ?? null,
    }))
    .filter((job) => !favoriteOnly || job.is_favorite)
    .filter((job) => !term || [job.title, job.company_name, job.skill_candidates]
      .some((value) => value?.toLowerCase().includes(term)));
}

function readFavorites(): FavoriteState {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) ?? "{}") as FavoriteState;
  } catch {
    return {};
  }
}

function writeFavorites(favorites: FavoriteState) {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    window.dispatchEvent(new Event("job-radar-favorites-updated"));
  } catch {
    // 저장소가 차단된 브라우저에서도 화면 탐색은 계속 허용합니다.
  }
}

async function getDemoJob(jobId: number) {
  return (await getDemoJobs()).find((job) => job.id === jobId) as Job;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
  });
  if (!response.ok) throw new Error("API 요청에 실패했습니다.");
  return response.json() as Promise<T>;
}

export const api = {
  canEmailReport: () => !STATIC_DEMO || Boolean(REPORT_API_URL),
  reportStatus: async () => {
    if (STATIC_DEMO && !REPORT_API_URL) return { ready: false };
    const baseUrl = REPORT_API_URL || API_URL;
    const response = await fetch(`${baseUrl}/api/reports/status`, { cache: "no-store" });
    if (!response.ok) return { ready: false };
    return response.json() as Promise<{ ready: boolean }>;
  },
  mapStatus: async () => {
    if (STATIC_DEMO && !REPORT_API_URL) return { ready: false };
    const baseUrl = REPORT_API_URL || API_URL;
    const response = await fetch(`${baseUrl}/api/maps/status`, { cache: "no-store" });
    if (!response.ok) return { ready: false };
    return response.json() as Promise<{ ready: boolean }>;
  },
  commuteEstimate: async (origin: string, destination: string) => {
    const mapUrl = `https://map.naver.com/p/search/${encodeURIComponent(destination)}`;
    if (STATIC_DEMO && !REPORT_API_URL) {
      return {
        available: false,
        duration_minutes: null,
        label: "지도 API 설정 필요",
        map_url: mapUrl,
        reason: "정적 데모에는 네이버지도 API 키를 저장할 수 없습니다.",
      } satisfies CommuteEstimate;
    }
    const baseUrl = REPORT_API_URL || API_URL;
    const response = await fetch(`${baseUrl}/api/maps/commute-time`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin, destination }),
    });
    if (!response.ok) {
      return {
        available: false,
        duration_minutes: null,
        label: "계산 실패",
        map_url: mapUrl,
      } satisfies CommuteEstimate;
    }
    return response.json() as Promise<CommuteEstimate>;
  },
  stats: async () => {
    if (!STATIC_DEMO) return request<Stats>("/api/stats");
    const jobs = await getDemoJobs();
    const matchedJobs = jobs.filter((job) => job.match_score > 0);
    return {
      total_jobs: jobs.length,
      detailed_jobs: jobs.filter((job) => job.detail_status === "success").length,
      matched_jobs: matchedJobs.length,
      favorite_jobs: jobs.filter((job) => job.is_favorite).length,
      average_score: matchedJobs.length
        ? Math.round(matchedJobs.reduce((sum, job) => sum + job.match_score, 0) / matchedJobs.length)
        : null,
    };
  },
  jobs: async (search = "", favorite = false) => {
    if (STATIC_DEMO) return { items: await getDemoJobs(search, favorite) };
    return request<{ items: Job[] }>(`/api/jobs?search=${encodeURIComponent(search)}&favorite=${favorite}&limit=500`);
  },
  favorite: async (jobId: number) => {
    if (STATIC_DEMO) {
      const favorites = readFavorites();
      favorites[jobId] = { memo: "", status: "planned" };
      writeFavorites(favorites);
      return getDemoJob(jobId);
    }
    return request<Job>(`/api/jobs/${jobId}/favorite`, {
      method: "POST",
      body: JSON.stringify({ memo: "", status: "planned" }),
    });
  },
  unfavorite: async (jobId: number) => {
    if (STATIC_DEMO) {
      const favorites = readFavorites();
      delete favorites[jobId];
      writeFavorites(favorites);
      return;
    }
    await fetch(`${API_URL}/api/jobs/${jobId}/favorite`, { method: "DELETE" });
  },
  updateFavorite: async (jobId: number, memo: string, status: string) => {
    if (STATIC_DEMO) {
      const favorites = readFavorites();
      favorites[jobId] = { memo, status };
      writeFavorites(favorites);
      return getDemoJob(jobId);
    }
    return request<Job>(`/api/favorites/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ memo, status }),
    });
  },
  emailReport: async (email: string, jobs: Job[]) => {
    const baseUrl = REPORT_API_URL || API_URL;
    const response = await fetch(`${baseUrl}/api/reports/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        jobs: jobs.map((job) => ({
          score: job.match_score,
          company: job.company_name ?? "",
          title: job.title,
          location: job.location ?? "",
          career: job.career ?? "",
          employment_type: job.employment_type ?? "",
          deadline: getReportDeadline(job),
          matched_keywords: job.matched_keywords.join(", "),
          reason: job.positive_reasons.join(" · "),
          url: job.detail_url ?? "",
        })),
      }),
    });
    if (!response.ok) throw new Error("이메일 발송에 실패했습니다.");
    return response.json() as Promise<{ sent: boolean }>;
  },
};
