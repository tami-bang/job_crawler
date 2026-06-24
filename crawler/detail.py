# crawler/detail.py
import hashlib
import json
import re
import time

from bs4 import BeautifulSoup

from crawler.database import (
    DEFAULT_DB_PATH,
    finish_crawl_run,
    get_connection,
    init_database,
    start_crawl_run,
)
from crawler.parser import extract_job_id, is_always_open_deadline, normalize_deadline_date, normalize_url


SECTION_LABELS = {
    "main_tasks": [
        "주요업무",
        "담당업무",
        "업무내용",
        "하는 일",
    ],
    "qualifications": [
        "자격요건",
        "지원자격",
        "필수사항",
        "필수요건",
    ],
    "preferred_conditions": [
        "우대사항",
        "우대조건",
        "선호조건",
    ],
    "benefits": [
        "복리후생",
        "혜택",
        "근무환경",
        "복지",
    ],
}

SKILL_HINTS = [
    "기술스택",
    "개발환경",
    "사용기술",
    "사용 기술",
    "tech stack",
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "vue",
    "node",
    "spring",
    "django",
    "flask",
    "fastapi",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "linux",
    "git",
]


DEFAULT_DETAIL_LOCATION_PREFIXES = ("서울", "경기", "인천")

SCHEMA_EMPLOYMENT_TYPES = {
    "FULL_TIME": "정규직",
    "PART_TIME": "아르바이트",
    "CONTRACTOR": "계약직",
    "TEMPORARY": "계약직",
    "INTERN": "인턴",
}


def collect_jobkorea_details(
    fetch_func,
    limit=10,
    delay_seconds=1.0,
    db_path=DEFAULT_DB_PATH,
    allowed_location_prefixes=DEFAULT_DETAIL_LOCATION_PREFIXES,
):
    init_database(db_path)
    crawl_run_id = start_crawl_run(
        source="jobkorea",
        crawl_type="detail",
        request_params_json=json.dumps(
            {
                "limit": limit,
                "delay_seconds": delay_seconds,
            },
            ensure_ascii=False,
        ),
        db_path=db_path,
    )

    result = {
        "target": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }

    try:
        targets = get_detail_targets(
            limit=limit,
            db_path=db_path,
            allowed_location_prefixes=allowed_location_prefixes,
        )
        result["target"] = len(targets)

        for index, job in enumerate(targets):
            if index > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)

            detail_url = job["detail_url"]
            if not detail_url:
                result["skipped"] += 1
                continue

            try:
                html = fetch_func(detail_url, dynamic=False)
                if not html:
                    raise RuntimeError("empty detail HTML")

                parsed = parse_job_detail(html)
                with get_connection(db_path) as conn:
                    save_raw_detail_page(conn, crawl_run_id, detail_url, html)
                    update_job_detail(conn, job["id"], parsed)

                result["success"] += 1
                print(f"[INFO] Detail saved: job_posting_id={job['id']} url={detail_url}")
            except Exception as exc:
                result["failed"] += 1
                mark_detail_failed(job["id"], str(exc), db_path=db_path)
                print(f"[ERROR] Detail failed: job_posting_id={job['id']} url={detail_url} reason={exc}")

        finish_crawl_run(crawl_run_id, status="success", db_path=db_path)
        result["crawl_run_id"] = crawl_run_id
        return result
    except Exception as exc:
        finish_crawl_run(crawl_run_id, status="failed", error_message=str(exc), db_path=db_path)
        raise


def collect_jobkorea_detail_urls(
    fetch_func,
    urls,
    delay_seconds=1.0,
    db_path=DEFAULT_DB_PATH,
):
    from crawler.job_store import save_job_list_items

    init_database(db_path)
    cleaned_urls = [str(url).strip() for url in urls if str(url).strip()]
    crawl_run_id = start_crawl_run(
        source="jobkorea",
        crawl_type="detail-url",
        request_params_json=json.dumps(
            {
                "urls": cleaned_urls,
                "delay_seconds": delay_seconds,
            },
            ensure_ascii=False,
        ),
        db_path=db_path,
    )

    result = {
        "target": len(cleaned_urls),
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }

    try:
        for index, detail_url in enumerate(cleaned_urls):
            if index > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)

            try:
                html = fetch_func(detail_url, dynamic=False)
                if not html:
                    raise RuntimeError("empty detail HTML")

                parsed = parse_job_detail(html)
                summary_job = build_job_from_detail_page(detail_url, html, parsed)
                save_job_list_items([summary_job], crawl_run_id, db_path=db_path)
                job_posting_id = find_job_posting_id(
                    summary_job["job_id"],
                    summary_job["normalized_url"],
                    db_path=db_path,
                )
                if not job_posting_id:
                    raise RuntimeError("detail URL was fetched but could not be saved")

                with get_connection(db_path) as conn:
                    save_raw_detail_page(conn, crawl_run_id, detail_url, html)
                    update_job_detail(conn, job_posting_id, parsed)

                result["success"] += 1
                print(f"[INFO] Detail URL saved: job_posting_id={job_posting_id} url={detail_url}")
            except Exception as exc:
                result["failed"] += 1
                print(f"[ERROR] Detail URL failed: url={detail_url} reason={exc}")

        finish_crawl_run(crawl_run_id, status="success", db_path=db_path)
        result["crawl_run_id"] = crawl_run_id
        return result
    except Exception as exc:
        finish_crawl_run(crawl_run_id, status="failed", error_message=str(exc), db_path=db_path)
        raise


def build_job_from_detail_page(detail_url, html, parsed):
    soup = BeautifulSoup(html, "html.parser")
    structured = extract_jobposting_data(soup)
    canonical_url = _normalize_structured_text(structured.get("url")) or detail_url
    title = _normalize_structured_text(structured.get("title")) or extract_title_from_page(soup)
    company = extract_company_name(structured, soup)

    return {
        "job_id": extract_job_id(canonical_url or detail_url),
        "title": title,
        "company": company,
        "location": parsed.get("location") or "",
        "url": canonical_url or detail_url,
        "normalized_url": normalize_url(canonical_url or detail_url),
        "company_url": "",
        "career": parsed.get("career") or "",
        "education": parsed.get("education") or "",
        "employment_type": parsed.get("employment_type") or "",
        "deadline": parsed.get("deadline") or "",
        "deadline_date": parsed.get("deadline_date") or "",
        "salary": "",
        "raw_text": parsed.get("description_text") or "",
    }


def find_job_posting_id(job_id, normalized_url, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        if job_id:
            row = conn.execute(
                """
                SELECT id
                FROM job_postings
                WHERE source = 'jobkorea'
                  AND source_job_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            if row:
                return row["id"]

        if normalized_url:
            row = conn.execute(
                """
                SELECT id
                FROM job_postings
                WHERE source = 'jobkorea'
                  AND normalized_url = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (normalized_url,),
            ).fetchone()
            if row:
                return row["id"]
    return None


def get_detail_targets(
    limit=10,
    db_path=DEFAULT_DB_PATH,
    allowed_location_prefixes=DEFAULT_DETAIL_LOCATION_PREFIXES,
):
    init_database(db_path)
    location_filter, location_params = build_location_filter(
        "location",
        allowed_location_prefixes,
    )
    with get_connection(db_path) as conn:
        return conn.execute(
            f"""
            SELECT id, title, detail_url
            FROM job_postings
            WHERE source = 'jobkorea'
              AND detail_url IS NOT NULL
              AND detail_url != ''
              {location_filter}
              AND (
                    deadline_date IS NULL
                    OR deadline_date = ''
                    OR deadline_date >= date('now', '+9 hours')
                  )
              AND (
                    detail_collected_at IS NULL
                    OR detail_collected_at = ''
                    OR detail_status = 'failed'
                  )
            ORDER BY last_seen_at DESC, id DESC
            LIMIT ?
            """,
            (*location_params, limit),
        ).fetchall()


def parse_job_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    structured = extract_jobposting_data(soup)
    meta_deadline = extract_detail_deadline(soup)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = _normalize_text(soup.get_text("\n", strip=True))
    lines = _extract_lines(text)
    deadline = meta_deadline or extract_deadline_from_text(text)
    posted_date = extract_start_date_from_text(text)

    return {
        "description_text": text,
        "raw_detail_text": text,
        "main_tasks": _extract_section(lines, SECTION_LABELS["main_tasks"]),
        "qualifications": _extract_section(lines, SECTION_LABELS["qualifications"]),
        "preferred_conditions": _extract_section(lines, SECTION_LABELS["preferred_conditions"]),
        "benefits": _extract_section(lines, SECTION_LABELS["benefits"]),
        "skill_candidates": _extract_skill_candidates(lines),
        "posted_date": posted_date,
        "deadline": deadline,
        "deadline_date": "" if is_always_open_deadline(deadline) else normalize_deadline_date(deadline),
        "location": extract_structured_location(structured) or extract_location_from_text(lines),
        "career": extract_career_from_text(lines) or _normalize_structured_text(structured.get("experienceRequirements")),
        "education": _normalize_structured_text(structured.get("educationRequirements")),
        "employment_type": extract_employment_type(structured, text),
    }


def extract_career_from_text(lines):
    stop_labels = {
        "학력",
        "스킬",
        "우대조건",
        "기본우대",
        "근무조건",
        "근무지주소",
        "접수기간",
        "복리후생",
    }
    for index, line in enumerate(lines):
        compact_line = _compact_korean(line)
        if compact_line != "경력" and not compact_line.startswith("경력("):
            continue

        window = []
        for value in lines[index:index + 5]:
            compact_value = _compact_korean(value)
            if window and compact_value in stop_labels:
                break
            window.append(value)

        career = _normalize_career_window(window)
        if career:
            return career
    return ""


def _normalize_career_window(lines):
    text = " ".join(line.strip() for line in lines if line and line.strip())
    compact = _compact_korean(text)
    if not compact:
        return ""

    base = ""
    for candidate in ("신입·경력", "신입/경력", "경력무관", "신입", "경력"):
        if candidate.replace("/", "·") in compact.replace("/", "·"):
            base = candidate.replace("/", "·")
            break
    if not base:
        return ""

    if base in {"신입", "경력무관"}:
        return base

    range_match = re.search(r"(\d+)\s*~\s*(\d+)\s*년", compact)
    if range_match:
        return f"{base}{range_match.group(1)}~{range_match.group(2)}년"

    years_match = re.search(r"(\d+)\s*년\s*(?:이상|↑)?", compact)
    if years_match:
        suffix = "년이상" if re.search(rf"{years_match.group(1)}\s*년\s*(?:이상|↑)", compact) else "년"
        return f"{base}{years_match.group(1)}{suffix}"

    return base


def _compact_korean(value):
    return re.sub(r"\s+", "", str(value or "")).replace("（", "(").replace("）", ")")


def extract_title_from_page(soup):
    title_tag = soup.select_one('[data-sentry-component="Title"]')
    title = _normalize_structured_text(title_tag.get_text(" ", strip=True) if title_tag else "")
    if title:
        return title

    og_title = soup.select_one('meta[property="og:title"]')
    title = _normalize_structured_text(og_title.get("content", "") if og_title else "")
    if " 채용 - " in title:
        return title.split(" 채용 - ", 1)[1].split("|", 1)[0].strip()
    return title.split("|", 1)[0].strip()


def extract_company_name(structured, soup):
    organization = structured.get("hiringOrganization")
    if isinstance(organization, dict):
        name = _normalize_structured_text(organization.get("name"))
        if name:
            return name

    title_tag = soup.select_one('[data-sentry-component="Title"]')
    title_text = _normalize_structured_text(title_tag.get_text(" ", strip=True) if title_tag else "")
    structured_title = _normalize_structured_text(structured.get("title"))
    if title_text and structured_title and title_text.endswith(structured_title):
        company = title_text[: -len(structured_title)].strip()
        if company:
            return company

    og_title = soup.select_one('meta[property="og:title"]')
    title = _normalize_structured_text(og_title.get("content", "") if og_title else "")
    if " 채용 - " in title:
        return title.split(" 채용 - ", 1)[0].strip()
    return "Unknown"


def save_raw_detail_page(conn, crawl_run_id, url, html, source="jobkorea"):
    conn.execute(
        """
        INSERT INTO raw_pages (
            crawl_run_id, source, page_type, url, raw_content, content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (crawl_run_id, source, "detail_page", url, html, _hash_text(html)),
    )


def update_job_detail(conn, job_posting_id, parsed):
    should_clear_deadline_date = is_always_open_deadline(parsed.get("deadline"))
    conn.execute(
        """
        UPDATE job_postings
        SET
            description_text = ?,
            raw_detail_text = ?,
            main_tasks = ?,
            qualifications = ?,
            preferred_conditions = ?,
            benefits = ?,
            skill_candidates = ?,
            posted_date = COALESCE(NULLIF(?, ''), posted_date),
            deadline = COALESCE(NULLIF(?, ''), deadline),
            deadline_date = CASE
                WHEN ? THEN NULL
                ELSE COALESCE(NULLIF(?, ''), deadline_date)
            END,
            location = COALESCE(NULLIF(?, ''), location),
            career = COALESCE(NULLIF(?, ''), career),
            education = COALESCE(NULLIF(?, ''), education),
            employment_type = COALESCE(NULLIF(?, ''), employment_type),
            detail_collected_at = CURRENT_TIMESTAMP,
            detail_status = 'success',
            detail_error = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            parsed["description_text"],
            parsed["raw_detail_text"],
            parsed["main_tasks"],
            parsed["qualifications"],
            parsed["preferred_conditions"],
            parsed["benefits"],
            parsed["skill_candidates"],
            parsed["posted_date"],
            parsed["deadline"],
            should_clear_deadline_date,
            parsed["deadline_date"],
            parsed["location"],
            parsed["career"],
            parsed["education"],
            parsed["employment_type"],
            job_posting_id,
        ),
    )


def extract_jobposting_data(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            payload = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        posting = _find_jobposting_payload(payload)
        if posting:
            return posting
    return {}


def _find_jobposting_payload(payload):
    if isinstance(payload, list):
        for item in payload:
            posting = _find_jobposting_payload(item)
            if posting:
                return posting
        return {}

    if not isinstance(payload, dict):
        return {}

    schema_type = payload.get("@type")
    schema_types = schema_type if isinstance(schema_type, list) else [schema_type]
    if "JobPosting" in schema_types:
        return payload

    for key in ["@graph", "mainEntity", "itemListElement"]:
        posting = _find_jobposting_payload(payload.get(key))
        if posting:
            return posting
    return {}


def extract_employment_type(structured, visible_text=""):
    value = structured.get("employmentType")
    values = value if isinstance(value, list) else [value]
    normalized = []
    for item in values:
        mapped = SCHEMA_EMPLOYMENT_TYPES.get(str(item or "").upper())
        if mapped and mapped not in normalized:
            normalized.append(mapped)
    if normalized:
        return ", ".join(normalized)

    match = re.search(
        r"(?:고용형태|근무형태)\s*(?:\n\s*)?(정규직|계약직|인턴|파견직|도급|프리랜서|아르바이트)",
        visible_text or "",
    )
    return match.group(1) if match else ""


def extract_structured_location(structured):
    locations = structured.get("jobLocation")
    locations = locations if isinstance(locations, list) else [locations]
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address", location)
        if not isinstance(address, dict):
            continue
        parts = [
            _normalize_structured_text(address.get("addressRegion")),
            _normalize_structured_text(address.get("addressLocality")),
        ]
        value = " ".join(part for part in parts if part).strip()
        if value:
            return value
        street_address = _normalize_structured_text(address.get("streetAddress"))
        if street_address:
            return street_address
    return ""


def _normalize_structured_text(value):
    if isinstance(value, list):
        return ", ".join(_normalize_structured_text(item) for item in value if item)
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or ""
    return str(value or "").strip()


def mark_detail_failed(job_posting_id, error_message, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE job_postings
            SET
                detail_status = 'failed',
                detail_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (error_message, job_posting_id),
        )


def _extract_section(lines, labels, max_lines=14):
    for index, line in enumerate(lines):
        if _contains_any(line, labels):
            collected = []
            for next_line in lines[index + 1 : index + 1 + max_lines]:
                if _is_section_boundary(next_line):
                    break
                collected.append(next_line)
            return "\n".join(collected).strip()
    return ""


def _extract_skill_candidates(lines, max_lines=30):
    candidates = []
    for line in lines:
        lowered = line.lower()
        if any(hint in lowered for hint in SKILL_HINTS):
            candidates.append(line)

    return "\n".join(candidates[:max_lines]).strip()


def _is_section_boundary(line):
    all_labels = []
    for labels in SECTION_LABELS.values():
        all_labels.extend(labels)

    compact = line.replace(" ", "")
    if len(compact) > 24:
        return False

    return any(label.replace(" ", "") in compact for label in all_labels)


def _contains_any(line, keywords):
    compact = line.replace(" ", "").lower()
    return any(keyword.replace(" ", "").lower() in compact for keyword in keywords)


def _extract_lines(text):
    lines = []
    for line in text.splitlines():
        cleaned = line.strip()
        if len(cleaned) < 2:
            continue
        lines.append(cleaned)
    return lines


def _normalize_text(text):
    text = re.sub(r"\r\n|\r", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_detail_deadline(soup):
    for tag in soup.find_all("meta"):
        content = tag.get("content", "")
        if "마감일" not in content and "마감" not in content:
            continue
        deadline = extract_deadline_from_text(content)
        if deadline:
            return deadline
    return ""


def extract_deadline_from_text(text):
    patterns = [
        r"마감일\s*[:：]?\s*(상시채용|상시|채용시|채용 시)",
        r"(상시채용|상시|채용시|채용 시)",
        r"마감일\s*[:：]?\s*(\d{4}[.-]\d{2}[.-]\d{2})",
        r"(\d{4}[.-]\d{2}[.-]\d{2})",
        r"(~\s*\d{2}[./]\d{2}\s*\([^)]+\))",
        r"(\d{2}[./]\d{2}\([^)]+\)\s*(?:마감|까지)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return match.group(1).strip()
    return ""


def extract_start_date_from_text(text):
    patterns = [
        r"시작일\s*(\d{4}[.]\d{2}[.]\d{2}\([^)]+\))",
        r"시작일\s*[:：]?\s*(\d{4}[.]\d{2}[.]\d{2})",
        r"등록일\s*(\d{4}[.]\d{2}[.]\d{2}\([^)]+\))",
        r"등록일\s*[:：]?\s*(\d{4}[.]\d{2}[.]\d{2})",
    ]
    compact_text = re.sub(r"\s+", " ", text or "")
    for pattern in patterns:
        match = re.search(pattern, compact_text)
        if match:
            return match.group(1).strip()
    return ""


def extract_location_from_text(lines):
    stop_labels = {"지도보기", "인근지하철", "지원자격", "경력", "학력", "스킬", "우대조건"}
    for index, line in enumerate(lines):
        if line != "근무지주소":
            continue

        collected = []
        for next_line in lines[index + 1 : index + 4]:
            if next_line in stop_labels:
                break
            if next_line:
                collected.append(next_line)
        return " ".join(collected).strip()
    return ""


def _hash_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def build_location_filter(column_name, allowed_location_prefixes):
    prefixes = [
        str(prefix).strip()
        for prefix in allowed_location_prefixes
        if str(prefix).strip()
    ]
    if not prefixes:
        return "", []

    clauses = [f"{column_name} LIKE ?" for _ in prefixes]
    params = [f"{prefix}%" for prefix in prefixes]
    return f"AND ({' OR '.join(clauses)})", params
