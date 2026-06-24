import argparse
import json
import re
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


def clean_deadline(value):
    text = str(value or "").strip()
    if not text or "미정" in text:
        return ""
    return text.replace("마감일", "").replace("마감", "").strip() or text


def infer_deadline_from_text(text):
    if not text:
        return ""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line == "마감일" and index + 1 < len(lines):
            return lines[index + 1]
    compact = " ".join(lines)
    if is_always_open_deadline(compact):
        return "상시채용"
    match = re.search(r"마감일\s*(\d{4}[.]\d{2}[.]\d{2}\([^)]+\)|\d{4}[.-]\d{2}[.-]\d{2})", compact)
    return match.group(1) if match else ""


def load_hard_filters():
    try:
        return json.loads(Path("config/user_preferences.json").read_text(encoding="utf-8")).get("hard_filters", {})
    except (OSError, json.JSONDecodeError):
        return {}


def location_token_pattern(location):
    if location == "세종":
        return r"(^|\n)\s*세종(?:시|\s|$)"
    return rf"(^|\n)\s*{re.escape(location)}(?:\s|$)"


def extract_work_location_text(row):
    parts = [row["location"] or ""]
    raw_detail_text = row["raw_detail_text"] or ""
    if raw_detail_text:
        lines = [line.strip() for line in raw_detail_text.splitlines()]
        collecting = False
        for line in lines:
            if line == "근무지주소":
                collecting = True
                continue
            if collecting and line in {"지도보기", "인근지하철", "지원자격", "스킬", "우대조건"}:
                if line != "지도보기":
                    break
                continue
            if collecting and line:
                parts.append(line)
    return "\n".join(parts)


def is_allowed_by_hard_location(row, hard_filters):
    if not hard_filters.get("strict_location_only"):
        return True

    location_text = extract_work_location_text(row)
    allowed_locations = hard_filters.get("locations") or []
    exclude_locations = hard_filters.get("exclude_locations") or []
    if allowed_locations and not any(re.search(location_token_pattern(location), location_text) for location in allowed_locations):
        return False
    return not any(re.search(location_token_pattern(location), location_text) for location in exclude_locations)


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
        if row["detail_status"] == "success":
            positive_reasons = ["상세 원문 수집 완료. 원문 스냅샷에서 주요 정보를 확인할 수 있습니다."]
        else:
            positive_reasons = ["JobKorea 목록에서 수집된 공고입니다. 원문 보기로 최신 상세를 확인해주세요."]
    snapshot_text = build_snapshot_text(row)
    deadline = clean_deadline(row["deadline"]) or infer_deadline_from_text(snapshot_text) or clean_deadline(row["deadline_date"])
    deadline = "상시채용" if is_always_open_deadline(deadline) else (deadline or "마감 미정")

    return {
        "id": index,
        "title": row["title"] or "제목 미상",
        "company_name": row["company_name"] or None,
        "location": row["location"] or None,
        "career": row["career"] or None,
        "employment_type": row["employment_type"] or None,
        "posted_date": row["posted_date"] or None,
        "deadline": deadline,
        "deadline_date": None if is_always_open_deadline(deadline) else (row["deadline_date"] or None),
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

    hard_filters = load_hard_filters()
    rows = [row for row in load_jobs(args.db, args.limit * 4) if is_allowed_by_hard_location(row, hard_filters)]
    jobs = [serialize_job(index, row) for index, row in enumerate(rows[:args.limit], start=1)]
    write_demo_data(jobs, Path(args.output), args.db)
    print(f"[INFO] demo data exported: jobs={len(jobs)} output={args.output}")


if __name__ == "__main__":
    main()
