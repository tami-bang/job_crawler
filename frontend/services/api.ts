export type Job = {
  id: number;
  title: string;
  company_name: string | null;
  location: string | null;
  career: string | null;
  employment_type: string | null;
  deadline: string | null;
  detail_url: string | null;
  skill_candidates: string | null;
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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
  stats: () => request<Stats>("/api/stats"),
  jobs: (search = "", favorite = false) =>
    request<{ items: Job[] }>(
      `/api/jobs?search=${encodeURIComponent(search)}&favorite=${favorite}`,
    ),
  favorite: (jobId: number) =>
    request<Job>(`/api/jobs/${jobId}/favorite`, {
      method: "POST",
      body: JSON.stringify({ memo: "", status: "saved" }),
    }),
  unfavorite: (jobId: number) =>
    fetch(`${API_URL}/api/jobs/${jobId}/favorite`, { method: "DELETE" }),
  updateFavorite: (jobId: number, memo: string, status: string) =>
    request<Job>(`/api/favorites/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify({ memo, status }),
    }),
};
