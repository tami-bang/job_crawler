# crawler/parser.py
import json
import re
from datetime import date
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


DEFAULT_BASE_URL = "https://www.jobkorea.co.kr"


def parse_html(html, selectors, base_url=None):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(selectors["card"])
    print(f"[DEBUG] Found {len(cards)} cards with selector: {selectors['card']}")

    jobs = []
    for card in cards:
        fields = _extract_default_card_fields(card, selectors, base_url)
        if _is_jobkorea_card(card):
            fields.update(_extract_jobkorea_card_fields(card, base_url))

        job = {
            "job_id": extract_job_id(fields["job_url"]),
            "title": fields["title"],
            "company": fields["company"],
            "location": fields["location"],
            "url": fields["job_url"],
            "normalized_url": normalize_url(fields["job_url"]),
            "company_url": fields["company_url"],
            "career": fields["career"],
            "education": fields["education"],
            "employment_type": fields["employment_type"],
            "deadline": fields["deadline"],
            "deadline_date": normalize_deadline_date(fields.get("deadline_date") or fields["deadline"]),
            "raw_text": card.get_text(" ", strip=True),
        }
        jobs.append(job)

    if not jobs and "jobUrl" in html and "/Recruit/GI_Read/" in html:
        jobs = _extract_jobkorea_next_data_jobs(html, base_url)

    return jobs


def extract_job_id(url):
    if not url:
        return ""

    patterns = [
        r"/Recruit/GI_Read/(\d+)",
        r"[?&]GI_No=(\d+)",
        r"[?&]gi_no=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def normalize_url(url):
    if not url:
        return ""

    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _get_text(tag):
    return tag.get_text(strip=True) if tag else ""


def _get_absolute_href(tag, base_url=None):
    if not tag or not tag.has_attr("href"):
        return ""
    return urljoin(base_url or DEFAULT_BASE_URL, tag["href"])


def _extract_default_card_fields(card, selectors, base_url=None):
    title_tag = _select_one(card, selectors.get("title"))
    company_tag = _select_one(card, selectors.get("company"))
    location_tag = _select_one(card, selectors.get("location"))
    url_tag = _select_one(card, selectors.get("url"))

    return {
        "title": _get_text(title_tag),
        "company": _get_text(company_tag),
        "location": _get_text(location_tag),
        "job_url": _get_absolute_href(url_tag, base_url),
        "company_url": _get_absolute_href(company_tag, base_url),
        "career": "",
        "education": "",
        "employment_type": "",
        "deadline": "",
        "deadline_date": "",
    }


def _is_jobkorea_card(card):
    return card.get("data-sentry-component") == "CardJob"


def _select_one(card, selector):
    if not selector:
        return None
    return card.select_one(selector)


def _extract_jobkorea_card_fields(card, base_url=None):
    title_link = card.select_one('a[data-sentry-component="Title"]')
    job_url = _get_absolute_href(title_link, base_url)
    title = _get_text(title_link)

    company_name = ""
    company_url = ""
    for link in card.find_all("a", href=True):
        href = link.get("href", "")
        text = _get_text(link)
        if "/Recruit/GI_Read/" not in href:
            continue
        if link == title_link or not text or text == title:
            continue
        company_name = text
        company_url = _get_absolute_href(link, base_url)
        break

    chips = [_get_text(tag) for tag in card.select('[data-sentry-component="GrayChip"] span.truncate')]
    location = chips[0] if chips else ""

    raw_text = card.get_text(" ", strip=True)

    return {
        "title": title,
        "company": company_name,
        "location": location,
        "job_url": job_url,
        "company_url": company_url,
        "career": _extract_career(raw_text),
        "education": _extract_education(raw_text),
        "employment_type": _extract_employment_type(raw_text),
        "deadline": _extract_deadline(raw_text),
        "deadline_date": normalize_deadline_date(_extract_deadline(raw_text)),
    }


def _extract_career(text):
    match = re.search(r"(신입|경력무관|경력\s*\d+년[↑이상]*|경력\s*\d+~\d+년)", text)
    return match.group(1).replace(" ", "") if match else ""


def _extract_education(text):
    patterns = ["학력무관", "대졸", "초대졸", "고졸", "석사", "박사"]
    return _find_first_keyword(text, patterns)


def _extract_employment_type(text):
    patterns = ["정규직", "계약직", "인턴", "파견직", "도급", "프리랜서", "아르바이트"]
    return _find_first_keyword(text, patterns)


def _extract_deadline(text):
    match = re.search(r"(\d{2}[./]\d{2}\([^)]+\)\s*(?:마감|까지)?)", text)
    if not match:
        match = re.search(r"(\d{4}[.-]\d{2}[.-]\d{2})", text)
    if not match:
        match = re.search(r"(~\s*\d{2}[./]\d{2}\s*\([^)]+\))", text)
    return match.group(1) if match else ""


def _find_first_keyword(text, keywords):
    for keyword in keywords:
        if keyword in text:
            return keyword
    return ""


def _extract_jobkorea_next_data_jobs(html, base_url=None):
    quote = '\\\"'
    pattern = (
        re.escape("{" + quote + "gNo" + quote)
        + ".*?"
        + re.escape(quote + "recommendType" + quote)
        + r":(?:null|"
        + re.escape(quote)
        + r".*?"
        + re.escape(quote)
        + ")"
        + re.escape("}")
    )

    jobs = []
    seen_ids = set()
    for raw_object in re.findall(pattern, html):
        job = _parse_jobkorea_next_data_object(raw_object, base_url)
        if not job or job["job_id"] in seen_ids:
            continue
        jobs.append(job)
        seen_ids.add(job["job_id"])

    if jobs:
        print(f"[DEBUG] Found {len(jobs)} JobKorea jobs from Next data fallback")
    return jobs


def _parse_jobkorea_next_data_object(raw_object, base_url=None):
    try:
        payload = raw_object.replace('\\\"', '"')
        payload = payload.replace("\\u0026", "&").replace("\\u003e", ">")
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    job_url = _get_absolute_href_from_value(data.get("jobUrl"), base_url)
    job_id = extract_job_id(job_url)
    title = _get_next_data_text(data, "title")
    if not job_id or not title:
        return None

    location = _normalize_jobkorea_location(_get_next_data_text(data, "localName"))
    deadline = _get_next_data_text(data, "applyCloseDisplayText")
    deadline_date = "" if is_always_open_deadline(deadline) else normalize_deadline_date(
        _get_next_data_text(data, "applyCloseDate") or deadline
    )
    company = _get_next_data_text(data, "companyName")
    career = _get_next_data_text(data, "careerName")
    education = _get_next_data_text(data, "educationName")
    job_type = _get_next_data_text(data, "jobTypeName")
    raw_text = " ".join(
        value
        for value in [title, company, location, career, education, job_type, deadline]
        if value
    )

    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "url": job_url,
        "normalized_url": normalize_url(job_url),
        "company_url": _get_absolute_href_from_value(data.get("companyUrl"), base_url),
        "career": career,
        "education": education,
        "employment_type": "",
        "deadline": deadline,
        "deadline_date": deadline_date,
        "raw_text": raw_text,
    }


def _get_absolute_href_from_value(href, base_url=None):
    if not href:
        return ""
    return urljoin(base_url or DEFAULT_BASE_URL, href)


def _get_next_data_text(data, key):
    return str(data.get(key) or "").strip()


def _normalize_jobkorea_location(location):
    return " ".join(str(location or "").replace(">", " ").split())


def normalize_deadline_date(value, today=None):
    text = str(value or "").strip()
    if not text:
        return ""
    if is_always_open_deadline(text):
        return ""

    today = today or date.today()
    normalized = text.replace(".", "-").replace("/", "-")

    full_date = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if full_date:
        return _format_date_parts(full_date.group(1), full_date.group(2), full_date.group(3))

    month_day = re.search(r"(\d{1,2})-(\d{1,2})", normalized)
    if not month_day:
        return ""

    month = int(month_day.group(1))
    day = int(month_day.group(2))
    year = today.year
    if month < today.month - 1:
        year += 1
    return _format_date_parts(year, month, day)


def is_always_open_deadline(value):
    text = str(value or "").strip().lower()
    return any(keyword in text for keyword in ("상시", "수시채용", "채용시", "채용 시"))


def _format_date_parts(year, month, day):
    try:
        parsed = date(int(year), int(month), int(day))
    except ValueError:
        return ""
    return parsed.isoformat()
