# crawler/taxonomy.py
import hashlib
import re

from bs4 import BeautifulSoup

from crawler.database import (
    DEFAULT_DB_PATH,
    finish_crawl_run,
    get_connection,
    init_database,
    start_crawl_run,
)


JOBKOREA_TAXONOMY_URL = "https://www.jobkorea.co.kr/recruit/joblist?menucode=local&localorder=1"

TAXONOMY_GROUPS = [
    ("job", "직무"),
    ("location", "근무지역"),
    ("career", "경력"),
    ("education", "학력"),
    ("company_type", "기업형태"),
    ("employment_type", "고용형태"),
    ("industry", "산업"),
    ("rank_position_salary", "직급/직책/급여"),
    ("major", "우대전공"),
    ("certificate", "자격증"),
    ("preference", "우대조건"),
    ("welfare", "복리후생"),
]

IGNORED_LINES = {
    "펴기",
    "닫기",
    "취소 선택",
    "검색 결과가 없습니다.",
    "최근검색",
    "1차메뉴",
    "2차메뉴",
    "3차메뉴",
    "선택한 조건 값",
    "초기화",
    "조건저장",
    "선택된 조건 검색하기",
}


def sync_jobkorea_taxonomy(fetch_func, db_path=DEFAULT_DB_PATH):
    init_database(db_path)
    crawl_run_id = start_crawl_run(
        source="jobkorea",
        crawl_type="taxonomy",
        request_url=JOBKOREA_TAXONOMY_URL,
        db_path=db_path,
    )

    try:
        html = fetch_func(JOBKOREA_TAXONOMY_URL, dynamic=False)
        if not html:
            raise RuntimeError("JobKorea taxonomy page fetch failed.")

        content_hash = _hash_text(html)
        groups = parse_jobkorea_taxonomy(html)

        with get_connection(db_path) as conn:
            _save_raw_page(conn, crawl_run_id, JOBKOREA_TAXONOMY_URL, html, content_hash)
            saved_count = _save_taxonomy_groups(conn, crawl_run_id, groups)

        finish_crawl_run(crawl_run_id, status="success", db_path=db_path)
        return {
            "crawl_run_id": crawl_run_id,
            "group_count": len(groups),
            "value_count": saved_count,
        }
    except Exception as exc:
        finish_crawl_run(crawl_run_id, status="failed", error_message=str(exc), db_path=db_path)
        raise


def parse_jobkorea_taxonomy(html):
    soup = BeautifulSoup(html, "html.parser")
    lines = _extract_visible_lines(soup)
    group_ranges = _find_group_ranges(lines)

    parsed_groups = []
    for index, (code, name, start) in enumerate(group_ranges):
        end = group_ranges[index + 1][2] if index + 1 < len(group_ranges) else len(lines)
        raw_values = lines[start + 1:end]
        values = _parse_values(raw_values)
        parsed_groups.append(
            {
                "code": code,
                "name": name,
                "values": values,
            }
        )

    return parsed_groups


def _extract_visible_lines(soup):
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _find_group_ranges(lines):
    ranges = []
    seen = set()

    for index, line in enumerate(lines):
        normalized = _clean_line(line)
        for code, name in TAXONOMY_GROUPS:
            if code in seen:
                continue
            if normalized == name or normalized == f"{name} 펴기":
                ranges.append((code, name, index))
                seen.add(code)
                break

    ranges.sort(key=lambda item: item[2])
    return ranges


def _parse_values(lines):
    values = []

    for line in lines:
        item = _parse_taxonomy_line(line)
        if not item:
            continue

        name = item["name"]
        if name in IGNORED_LINES or name.startswith("←"):
            continue
        if _is_form_hint(name):
            continue

        value = {
            "name": name,
            "posting_count": item["posting_count"],
            "depth": 1,
            "path": name,
            "parent_path": None,
        }
        values.append(value)

    return values


def _parse_taxonomy_line(line):
    cleaned = _clean_line(line)
    if not cleaned:
        return None

    match = re.match(r"^(?P<name>.+?)\((?P<count>[\d,]+)\)$", cleaned)
    if match:
        return {
            "name": match.group("name").strip(),
            "posting_count": int(match.group("count").replace(",", "")),
        }

    return {
        "name": cleaned,
        "posting_count": None,
    }


def _clean_line(line):
    cleaned = re.sub(r"\s+", " ", line).strip()
    cleaned = cleaned.removesuffix(" 닫기").strip()
    cleaned = cleaned.removesuffix(" 펴기").strip()
    return cleaned


def _is_form_hint(name):
    hints = [
        "입력 찾기",
        "숫자만 입력",
        "만원 이상",
        "최소경력",
        "최대경력",
        "세",
    ]
    return any(hint in name for hint in hints)


def _save_raw_page(conn, crawl_run_id, url, html, content_hash):
    conn.execute(
        """
        INSERT INTO raw_pages (
            crawl_run_id, source, page_type, url, raw_content, content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (crawl_run_id, "jobkorea", "taxonomy_page", url, html, content_hash),
    )


def _save_taxonomy_groups(conn, crawl_run_id, groups):
    saved_count = 0

    for group in groups:
        group_id = _upsert_taxonomy_group(conn, group["code"], group["name"])
        path_to_id = {}

        for value in group["values"]:
            parent_id = path_to_id.get(value["parent_path"])
            value_id = _upsert_taxonomy_value(conn, group_id, parent_id, value)
            path_to_id[value["path"]] = value_id

            if value["posting_count"] is not None:
                _insert_taxonomy_snapshot(conn, value_id, crawl_run_id, value["posting_count"])

            saved_count += 1

    return saved_count


def _upsert_taxonomy_group(conn, code, name):
    conn.execute(
        """
        INSERT INTO taxonomy_groups (source, code, name)
        VALUES (?, ?, ?)
        ON CONFLICT(source, code)
        DO UPDATE SET name = excluded.name, updated_at = CURRENT_TIMESTAMP
        """,
        ("jobkorea", code, name),
    )
    row = conn.execute(
        "SELECT id FROM taxonomy_groups WHERE source = ? AND code = ?",
        ("jobkorea", code),
    ).fetchone()
    return row["id"]


def _upsert_taxonomy_value(conn, group_id, parent_id, value):
    conn.execute(
        """
        INSERT INTO taxonomy_values (
            group_id, parent_id, source, name, depth, path
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(group_id, path)
        DO UPDATE SET
            parent_id = excluded.parent_id,
            name = excluded.name,
            depth = excluded.depth,
            is_active = 1,
            last_seen_at = CURRENT_TIMESTAMP
        """,
        (
            group_id,
            parent_id,
            "jobkorea",
            value["name"],
            value["depth"],
            value["path"],
        ),
    )
    row = conn.execute(
        "SELECT id FROM taxonomy_values WHERE group_id = ? AND path = ?",
        (group_id, value["path"]),
    ).fetchone()
    return row["id"]


def _insert_taxonomy_snapshot(conn, taxonomy_value_id, crawl_run_id, posting_count):
    conn.execute(
        """
        INSERT INTO taxonomy_value_snapshots (
            taxonomy_value_id, crawl_run_id, posting_count
        )
        VALUES (?, ?, ?)
        """,
        (taxonomy_value_id, crawl_run_id, posting_count),
    )


def _hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
