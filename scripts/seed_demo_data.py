import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.database import get_connection, init_database


DEMO_JOBS = [
    ("Layer Nine", "Python FastAPI 백엔드 개발자", "서울 강남구", "신입·경력 2년", "Python, FastAPI, PostgreSQL, Docker", 92, ["Python", "FastAPI", "SQL", "Docker"]),
    ("Orbit Works", "데이터 플랫폼 엔지니어", "서울 성동구", "경력 1년 이상", "Python, Airflow, AWS, SQL", 86, ["Python", "AWS", "SQL", "데이터"]),
    ("Nouveau Lab", "React 기반 프론트엔드 개발자", "경기 성남시", "신입", "React, TypeScript, Next.js", 81, ["React", "TypeScript", "웹서비스"]),
    ("Mono Systems", "서비스 자동화 엔지니어", "서울 영등포구", "경력 무관", "Python, Selenium, CI/CD", 76, ["Python", "자동화", "Git"]),
    ("Pixel Route", "주니어 풀스택 개발자", "인천 연수구", "신입·경력", "Next.js, FastAPI, Docker", 73, ["Next.js", "FastAPI", "Docker"]),
    ("Cloud Canvas", "클라우드 운영 개발자", "서울 마포구", "경력 2년 이상", "AWS, Linux, Terraform", 68, ["AWS", "Linux", "인프라"]),
]


def seed_demo_data(db_path="data/job_radar.db"):
    init_database(db_path)
    with get_connection(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0] > 0:
            print("[INFO] Existing job data found. Demo seed skipped.")
            return 0

        profile_id = conn.execute("INSERT INTO user_profiles (name) VALUES (?)", ("demo-user",)).lastrowid
        for index, (company, title, location, career, skills, score, keywords) in enumerate(DEMO_JOBS, start=1):
            company_id = conn.execute(
                "INSERT INTO companies (source, source_company_key, name) VALUES (?, ?, ?)",
                ("demo", f"company-{index}", company),
            ).lastrowid
            job_id = conn.execute(
                """
                INSERT INTO job_postings (
                    source, source_job_id, company_id, title, detail_url, location, career,
                    education, employment_type, deadline, deadline_date, skill_candidates,
                    detail_status, detail_collected_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date('now', '+30 days'), ?, 'success', CURRENT_TIMESTAMP, 'active')
                """,
                (
                    "demo", f"job-{index}", company_id, title, f"https://example.com/jobs/{index}",
                    location, career, "학력무관", "정규직", "상시채용", skills,
                ),
            ).lastrowid
            reasons = [f"희망 기술 {keywords[0]} 경험과 연결됩니다.", f"선호 지역 {location.split()[0]}에 해당합니다."]
            conn.execute(
                """
                INSERT INTO job_match_results (
                    user_profile_id, job_posting_id, score, match_score, raw_score,
                    matched_keywords_json, missing_keywords_json, positive_reasons_json,
                    negative_reasons_json, recommendation_level, reason, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, '[]', ?, '[]', ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    profile_id, job_id, score, score, score + 8,
                    json.dumps(keywords, ensure_ascii=False),
                    json.dumps(reasons, ensure_ascii=False),
                    "strong" if score >= 85 else "good",
                    reasons[0],
                ),
            )

    print(f"[INFO] {len(DEMO_JOBS)} demo jobs created: {db_path}")
    return len(DEMO_JOBS)


if __name__ == "__main__":
    seed_demo_data()
