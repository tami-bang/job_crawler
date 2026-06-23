import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawler.database import init_database


def parse_json_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [str(value)]
    return parsed if isinstance(parsed, list) else [str(parsed)]


def is_always_open_deadline(value):
    text = str(value or "").strip().lower()
    return any(keyword in text for keyword in ("상시", "수시채용", "채용시", "채용 시"))


def load_jobs(db_path, limit):
    init_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            jp.id,
            jp.title,
            c.name AS company_name,
            jp.location,
            jp.career,
            jp.employment_type,
            jp.posted_date,
            jp.deadline,
            jp.deadline_date,
            jp.detail_url,
            jp.raw_detail_text,
            jp.main_tasks,
            jp.qualifications,
            jp.preferred_conditions,
            jp.benefits,
            jp.description_text,
            jp.raw_summary_text,
            jp.reopen_count,
            jp.skill_candidates,
            jp.detail_status,
            COALESCE(jmr.match_score, jmr.score, 0) AS match_score,
            jmr.recommendation_level,
            jmr.matched_keywords_json,
            jmr.positive_reasons_json,
            jmr.negative_reasons_json
        FROM job_postings jp
        LEFT JOIN companies c ON c.id = jp.company_id
        LEFT JOIN job_match_results jmr
          ON jmr.job_posting_id = jp.id
         AND jmr.user_profile_id = (
            SELECT id FROM user_profiles ORDER BY updated_at DESC, id DESC LIMIT 1
         )
        ORDER BY
            COALESCE(jmr.match_score, jmr.score, 0) DESC,
            CASE WHEN jp.detail_status = 'success' THEN 0 ELSE 1 END,
            jp.updated_at DESC,
            jp.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def serialize_job(index, row):
    score = round(row["match_score"] or 0)
    matched_keywords = parse_json_list(row["matched_keywords_json"]) or ["JobKorea"]
    positive_reasons = parse_json_list(row["positive_reasons_json"])
    if not positive_reasons:
        positive_reasons = [
            "JobKorea 목록에서 실제 수집된 공고입니다. 상세 수집/매칭 분석 대기 상태입니다."
        ]
    snapshot_text = build_snapshot_text(row)

    return {
        "id": index,
        "title": row["title"] or "제목 미상",
        "company_name": row["company_name"] or None,
        "location": row["location"] or None,
        "career": row["career"] or None,
        "employment_type": row["employment_type"] or None,
        "posted_date": row["posted_date"] or None,
        "deadline": row["deadline"] or row["deadline_date"] or "마감일 미정",
        "deadline_date": None if is_always_open_deadline(row["deadline"]) else (row["deadline_date"] or None),
        "detail_url": row["detail_url"] or None,
        "raw_detail_text": snapshot_text,
        "reopen_count": row["reopen_count"] or 0,
        "skill_candidates": row["skill_candidates"] or "",
        "detail_status": row["detail_status"] or None,
        "match_score": score,
        "recommendation_level": row["recommendation_level"] or ("unscored" if score == 0 else None),
        "matched_keywords": matched_keywords,
        "positive_reasons": positive_reasons,
        "negative_reasons": parse_json_list(row["negative_reasons_json"]),
        "is_favorite": False,
        "favorite_memo": None,
        "favorite_status": None,
    }


def build_snapshot_text(row):
    raw_detail = row["raw_detail_text"]
    if raw_detail:
        return raw_detail

    sections = [
        ("주요업무", row["main_tasks"]),
        ("자격요건", row["qualifications"]),
        ("우대사항", row["preferred_conditions"]),
        ("복지/혜택", row["benefits"]),
    ]
    section_text = "\n\n".join(
        f"{label}\n{text.strip()}"
        for label, text in sections
        if text and text.strip()
    )
    if section_text:
        return section_text

    return row["description_text"] or row["raw_summary_text"] or None


def write_demo_data(jobs, output_path, db_path):
    content = "\n".join(
        [
            'import type { Job } from "./api";',
            "",
            f"// {db_path}에서 생성한 실제 JobKorea 수집 결과 스냅샷입니다.",
            "// 공개 GitHub Pages 정적 데모에서 서버 없이 보여주기 위해 DB를 TypeScript 데이터로 변환했습니다.",
            f"export const demoJobs: Job[] = {json.dumps(jobs, ensure_ascii=False, indent=2)};",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export static demo data from JobRadar DB")
    parser.add_argument("--db", default="data/job_radar.db")
    parser.add_argument("--output", default="frontend/services/demo-data.ts")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    rows = load_jobs(args.db, args.limit)
    jobs = [serialize_job(index, row) for index, row in enumerate(rows, start=1)]
    write_demo_data(jobs, Path(args.output), args.db)
    print(f"[INFO] demo data exported: jobs={len(jobs)} output={args.output}")


if __name__ == "__main__":
    main()
