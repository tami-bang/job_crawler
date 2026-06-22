# main.py
import argparse
import json

from crawler.database import finish_crawl_run, get_connection, init_database, start_crawl_run
from crawler.detail import collect_jobkorea_details
from crawler.fetcher import fetch, is_blocked_page
from crawler.health import build_collection_health_report, print_collection_health_report
from crawler.job_store import save_job_list_items, save_raw_list_page
from crawler.logger_setup import setup_logger
from crawler.matcher import DEFAULT_PREFERENCES_PATH, load_preferences, run_matching_analysis
from crawler.parser import parse_html
from crawler.report import build_match_report
from crawler.taxonomy import sync_jobkorea_taxonomy


logger = setup_logger()


def load_sites(config_path="config/sites.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def crawl(site_key, keyword, pages=2, sites=None, save_csv=True):
    site = sites[site_key]
    all_jobs = []
    crawl_run_id = None

    if site_key == "jobkorea":
        init_database()
        crawl_run_id = start_crawl_run(
            source="jobkorea",
            crawl_type="list",
            request_url=site["base_url"],
            request_params_json=json.dumps(
                {
                    "keyword": keyword,
                    "pages": pages,
                },
                ensure_ascii=False,
            ),
        )

    try:
        db_result = {
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
        }

        for page in range(1, pages + 1):
            url = site["base_url"].format(keyword=keyword, page=page)
            logger.info(f"Crawling {site['name']} page {page}: {url}")

            html, jobs = fetch_list_jobs(site_key, site, url)
            if not html:
                logger.warning(f"Failed to fetch page {page}: {url}")
                continue

            all_jobs.extend(jobs)

            if site_key == "jobkorea":
                with get_connection() as conn:
                    save_raw_list_page(conn, crawl_run_id, url, html)

                page_result = save_job_list_items(jobs, crawl_run_id)
                for key, value in page_result.items():
                    db_result[key] += value

        if site_key == "jobkorea":
            print(
                "[INFO] DB save complete: "
                f"new={db_result['new']}, "
                f"updated={db_result['updated']}, "
                f"unchanged={db_result['unchanged']}, "
                f"skipped={db_result['skipped']}"
            )

        if all_jobs and save_csv:
            from crawler.saver import save_jobs

            save_jobs(all_jobs, filename=f"data/{site_key}_{keyword}_jobs.csv")
        else:
            logger.error("No job postings were extracted. Check the site or selectors.")

        if crawl_run_id:
            finish_crawl_run(crawl_run_id, status="success")

        return {
            "jobs_found": len(all_jobs),
            "db_result": db_result,
            "crawl_run_id": crawl_run_id,
        }
    except Exception as exc:
        if crawl_run_id:
            finish_crawl_run(crawl_run_id, status="failed", error_message=str(exc))
        raise


def fetch_list_page(site_key, site, url):
    if site_key == "jobkorea":
        # 목록은 카드 파싱을 먼저 수행한 뒤 차단 여부를 판정한다.
        return fetch(url, dynamic=False, reject_blocked=False)

    return fetch(
        url,
        dynamic=site["dynamic"],
        wait_selector=site["selectors"].get("card", "body"),
    )


def fetch_list_jobs(site_key, site, url):
    html = fetch_list_page(site_key, site, url)
    jobs = parse_html(html, site["selectors"], base_url=url) if html else []

    if site_key != "jobkorea" or jobs or not site.get("dynamic"):
        return html, jobs

    if html and is_blocked_page(html):
        logger.warning("JobKorea static response looks blocked after card parsing failed.")

    print("[INFO] JobKorea static collection failed or returned no cards. Trying Selenium fallback.")
    dynamic_html = fetch(
        url,
        dynamic=True,
        wait_selector=site["selectors"].get("card", "body"),
        reject_blocked=False,
    )
    if not dynamic_html:
        return html, jobs

    dynamic_jobs = parse_html(
        dynamic_html,
        site["selectors"],
        base_url=url,
    )
    if dynamic_jobs:
        return dynamic_html, dynamic_jobs

    if is_blocked_page(dynamic_html):
        logger.warning("JobKorea Selenium response is a blocked page.")
        return None, []

    return dynamic_html, []


def sync_taxonomy():
    result = sync_jobkorea_taxonomy(fetch)
    print(
        "[INFO] JobKorea taxonomy sync complete: "
        f"groups={result['group_count']}, "
        f"values={result['value_count']}, "
        f"crawl_run_id={result['crawl_run_id']}"
    )


def collect_details():
    limit_str = input("Detail pages to collect (example: 5): ").strip()
    limit = int(limit_str) if limit_str.isdigit() else 5

    result = collect_jobkorea_details(fetch, limit=limit)
    print(
        "[INFO] JobKorea detail collection complete: "
        f"target={result['target']}, "
        f"success={result['success']}, "
        f"failed={result['failed']}, "
        f"skipped={result['skipped']}, "
        f"crawl_run_id={result['crawl_run_id']}"
    )


def analyze_matches():
    limit_str = input("Jobs to analyze (blank for all): ").strip()
    limit = int(limit_str) if limit_str.isdigit() else None

    result = run_matching_analysis(limit=limit)
    print(
        "[INFO] JobKorea matching analysis complete: "
        f"profile_id={result['profile_id']}, "
        f"target={result['target']}, "
        f"analyzed={result['analyzed']}"
    )


def show_report():
    limit_str = input("Max results to show/export (blank for all current matches): ").strip()
    limit = int(limit_str) if limit_str.isdigit() else None

    result = build_match_report(limit=limit)
    print(
        "[INFO] JobKorea report complete: "
        f"count={result['count']}, "
        f"output={result['output_path']}, "
        f"xlsx={result.get('xlsx_output_path')}"
    )


def show_health():
    metrics = build_collection_health_report()
    print_collection_health_report(metrics)


def run_jobkorea_pipeline(sites):
    keyword = input("Keyword (example: python): ").strip()
    pages_str = input("Pages to crawl (example: 1): ").strip()
    detail_limit_str = input("Detail pages to collect (example: 5): ").strip()
    report_limit_str = input("Max report results (blank for all current matches): ").strip()

    pages = int(pages_str) if pages_str.isdigit() else 1
    detail_limit = int(detail_limit_str) if detail_limit_str.isdigit() else 5
    report_limit = int(report_limit_str) if report_limit_str.isdigit() else None

    summary = {
        "list": {"status": "not_run"},
        "detail": {"status": "not_run"},
        "match": {"status": "not_run"},
        "report": {"status": "not_run"},
    }

    print("[PIPELINE] Step 1/4: JobKorea list collection")
    try:
        list_result = crawl("jobkorea", keyword, pages, sites=sites)
        summary["list"] = {
            "status": "success",
            "jobs_found": list_result["jobs_found"],
            "db_result": list_result["db_result"],
            "crawl_run_id": list_result["crawl_run_id"],
        }
    except Exception as exc:
        summary["list"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[PIPELINE][ERROR] List step failed: {exc}")

    print("[PIPELINE] Step 2/4: JobKorea detail collection")
    try:
        detail_result = collect_jobkorea_details(fetch, limit=detail_limit)
        summary["detail"] = {
            "status": "success",
            **detail_result,
        }
    except Exception as exc:
        summary["detail"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[PIPELINE][ERROR] Detail step failed: {exc}")

    print("[PIPELINE] Step 3/4: Matching analysis")
    try:
        match_result = run_matching_analysis()
        summary["match"] = {
            "status": "success",
            **match_result,
        }
    except Exception as exc:
        summary["match"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[PIPELINE][ERROR] Match step failed: {exc}")

    print("[PIPELINE] Step 4/4: Report export")
    try:
        report_result = build_match_report(limit=report_limit)
        summary["report"] = {
            "status": "success",
            **report_result,
        }
    except Exception as exc:
        summary["report"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[PIPELINE][ERROR] Report step failed: {exc}")

    print_pipeline_summary(summary)


def run_jobkorea_multi_pipeline(sites, options=None):
    preferences = load_preferences(DEFAULT_PREFERENCES_PATH)
    search_keywords = preferences.get("search_keywords", [])
    if not search_keywords:
        print("[PIPELINE][ERROR] No search_keywords found in config/user_preferences.json")
        return

    if options:
        pages = options.pages
        detail_limit = options.detail_limit
        report_limit = options.report_top_n
        delay_seconds = options.keyword_delay
        keyword_batch_size = options.keyword_batch_size
        resume = options.resume
        report_only = options.report_only
    else:
        pages_str = input("Pages per keyword (example: 1): ").strip()
        detail_limit_str = input("Detail pages to collect after list collection (example: 10): ").strip()
        report_limit_str = input("Max report results (blank for all current matches): ").strip()
        delay_str = input("Delay seconds between keywords (example: 1): ").strip()

        pages = int(pages_str) if pages_str.isdigit() else 3
        detail_limit = int(detail_limit_str) if detail_limit_str.isdigit() else 10
        report_limit = int(report_limit_str) if report_limit_str.isdigit() else None
        delay_seconds = float(delay_str) if is_number(delay_str) else 1.0
        keyword_batch_size = len(search_keywords)
        resume = False
        report_only = False

    if report_only:
        run_report_only(report_limit)
        return

    completed_keywords = get_completed_jobkorea_keywords() if resume else set()
    pending_keywords = [
        keyword for keyword in search_keywords
        if keyword not in completed_keywords
    ]
    selected_keywords = pending_keywords[:keyword_batch_size] if keyword_batch_size else pending_keywords

    summary = {
        "keywords": [],
        "keyword_total": len(search_keywords),
        "keyword_completed_before": len(completed_keywords),
        "keyword_selected": len(selected_keywords),
        "list_total": {
            "jobs_found": 0,
            "new": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
            "failed": 0,
        },
        "detail": {"status": "not_run"},
        "match": {"status": "not_run"},
        "report": {"status": "not_run"},
    }

    print(
        "[MULTI PIPELINE] Step 1/4: list collection "
        f"selected={len(selected_keywords)}, "
        f"completed_before={len(completed_keywords)}, "
        f"total={len(search_keywords)}"
    )
    for index, keyword in enumerate(selected_keywords, start=1):
        print(f"[MULTI PIPELINE] Keyword {index}/{len(selected_keywords)}: {keyword}")
        if index > 1 and delay_seconds > 0:
            import time

            time.sleep(delay_seconds)

        try:
            list_result = crawl("jobkorea", keyword, pages, sites=sites, save_csv=False)
            db_result = list_result["db_result"]
            keyword_result = {
                "keyword": keyword,
                "status": "success",
                "jobs_found": list_result["jobs_found"],
                **db_result,
            }
            summary["keywords"].append(keyword_result)
            summary["list_total"]["jobs_found"] += list_result["jobs_found"]
            summary["list_total"]["new"] += db_result["new"]
            summary["list_total"]["updated"] += db_result["updated"]
            summary["list_total"]["unchanged"] += db_result["unchanged"]
            summary["list_total"]["skipped"] += db_result["skipped"]
        except Exception as exc:
            summary["keywords"].append(
                {
                    "keyword": keyword,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            summary["list_total"]["failed"] += 1
            print(f"[MULTI PIPELINE][ERROR] Keyword failed: {keyword} reason={exc}")

    print("[MULTI PIPELINE] Step 2/4: detail collection")
    try:
        detail_result = collect_jobkorea_details(fetch, limit=detail_limit)
        summary["detail"] = {
            "status": "success",
            **detail_result,
        }
    except Exception as exc:
        summary["detail"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[MULTI PIPELINE][ERROR] Detail step failed: {exc}")

    print("[MULTI PIPELINE] Step 3/4: matching analysis")
    try:
        match_result = run_matching_analysis()
        summary["match"] = {
            "status": "success",
            **match_result,
        }
    except Exception as exc:
        summary["match"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[MULTI PIPELINE][ERROR] Match step failed: {exc}")

    print("[MULTI PIPELINE] Step 4/4: report export")
    try:
        report_result = build_match_report(limit=report_limit)
        summary["report"] = {
            "status": "success",
            **report_result,
        }
    except Exception as exc:
        summary["report"] = {
            "status": "failed",
            "error": str(exc),
        }
        print(f"[MULTI PIPELINE][ERROR] Report step failed: {exc}")

    print_multi_pipeline_summary(summary)
    print_database_summary()


def print_pipeline_summary(summary):
    print("=" * 80)
    print("[PIPELINE] Summary")

    list_step = summary["list"]
    print(f"- list: {list_step['status']}")
    if list_step["status"] == "success":
        db_result = list_step["db_result"]
        print(
            "  "
            f"jobs_found={list_step['jobs_found']}, "
            f"new={db_result['new']}, "
            f"updated={db_result['updated']}, "
            f"unchanged={db_result['unchanged']}, "
            f"skipped={db_result['skipped']}"
        )
    elif "error" in list_step:
        print(f"  error={list_step['error']}")

    detail_step = summary["detail"]
    print(f"- detail: {detail_step['status']}")
    if detail_step["status"] == "success":
        print(
            "  "
            f"target={detail_step['target']}, "
            f"success={detail_step['success']}, "
            f"failed={detail_step['failed']}, "
            f"skipped={detail_step['skipped']}"
        )
    elif "error" in detail_step:
        print(f"  error={detail_step['error']}")

    match_step = summary["match"]
    print(f"- match: {match_step['status']}")
    if match_step["status"] == "success":
        print(
            "  "
            f"profile_id={match_step['profile_id']}, "
            f"target={match_step['target']}, "
            f"analyzed={match_step['analyzed']}"
        )
    elif "error" in match_step:
        print(f"  error={match_step['error']}")

    report_step = summary["report"]
    print(f"- report: {report_step['status']}")
    if report_step["status"] == "success":
        print(
            "  "
            f"count={report_step['count']}, "
            f"output={report_step['output_path']}"
        )
    elif "error" in report_step:
        print(f"  error={report_step['error']}")


def print_multi_pipeline_summary(summary):
    print("=" * 80)
    print("[MULTI PIPELINE] Keyword Summary")
    for item in summary["keywords"]:
        if item["status"] == "success":
            print(
                f"- {item['keyword']}: "
                f"jobs_found={item['jobs_found']}, "
                f"new={item['new']}, "
                f"updated={item['updated']}, "
                f"unchanged={item['unchanged']}, "
                f"skipped={item['skipped']}"
            )
        else:
            print(f"- {item['keyword']}: failed, error={item['error']}")

    total = summary["list_total"]
    print("[MULTI PIPELINE] Keyword Progress")
    print(
        "  "
        f"total={summary.get('keyword_total', 0)}, "
        f"completed_before={summary.get('keyword_completed_before', 0)}, "
        f"selected_this_run={summary.get('keyword_selected', 0)}, "
        f"failed_this_run={total['failed']}"
    )
    print("[MULTI PIPELINE] List Total")
    print(
        "  "
        f"jobs_found={total['jobs_found']}, "
        f"new={total['new']}, "
        f"updated={total['updated']}, "
        f"unchanged={total['unchanged']}, "
        f"skipped={total['skipped']}, "
        f"failed_keywords={total['failed']}"
    )

    detail = summary["detail"]
    print(f"[MULTI PIPELINE] Detail: {detail['status']}")
    if detail["status"] == "success":
        print(
            "  "
            f"target={detail['target']}, "
            f"success={detail['success']}, "
            f"failed={detail['failed']}, "
            f"skipped={detail['skipped']}"
        )
    elif "error" in detail:
        print(f"  error={detail['error']}")

    match = summary["match"]
    print(f"[MULTI PIPELINE] Match: {match['status']}")
    if match["status"] == "success":
        print(
            "  "
            f"profile_id={match['profile_id']}, "
            f"target={match['target']}, "
            f"analyzed={match['analyzed']}"
        )
    elif "error" in match:
        print(f"  error={match['error']}")

    report = summary["report"]
    print(f"[MULTI PIPELINE] Report: {report['status']}")
    if report["status"] == "success":
        print(f"  count={report['count']}, output={report['output_path']}")
    elif "error" in report:
        print(f"  error={report['error']}")


def run_report_only(report_limit=None):
    print("[REPORT ONLY] Step 1/2: matching analysis")
    match_result = run_matching_analysis()
    print(
        "[REPORT ONLY] Match complete: "
        f"profile_id={match_result['profile_id']}, "
        f"target={match_result['target']}, "
        f"analyzed={match_result['analyzed']}"
    )

    print("[REPORT ONLY] Step 2/2: report export")
    report_result = build_match_report(limit=report_limit)
    print(
        "[REPORT ONLY] Report complete: "
        f"count={report_result['count']}, "
        f"output={report_result['output_path']}"
    )
    print_database_summary()


def get_completed_jobkorea_keywords():
    init_database()
    completed = set()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT request_params_json
            FROM crawl_runs
            WHERE source = 'jobkorea'
              AND crawl_type = 'list'
              AND status = 'success'
              AND request_params_json IS NOT NULL
            """
        ).fetchall()

    for row in rows:
        try:
            params = json.loads(row["request_params_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        keyword = str(params.get("keyword", "")).strip()
        if keyword:
            completed.add(keyword)
    return completed


def print_database_summary():
    init_database()
    with get_connection() as conn:
        job_count = conn.execute("SELECT COUNT(1) FROM job_postings").fetchone()[0]
        detail_success = conn.execute(
            "SELECT COUNT(1) FROM job_postings WHERE detail_status = ?",
            ("success",),
        ).fetchone()[0]
        detail_missing = conn.execute(
            """
            SELECT COUNT(1)
            FROM job_postings
            WHERE source = ?
              AND detail_url IS NOT NULL
              AND detail_url != ?
              AND (
                    detail_collected_at IS NULL
                    OR detail_collected_at = ?
                    OR detail_status = ?
                  )
            """,
            ("jobkorea", "", "", "failed"),
        ).fetchone()[0]
        match_count = conn.execute("SELECT COUNT(1) FROM job_match_results").fetchone()[0]
        latest_profile_match_count = conn.execute(
            """
            SELECT COUNT(1)
            FROM job_match_results
            WHERE user_profile_id = (
                SELECT id
                FROM user_profiles
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
            )
            """
        ).fetchone()[0]
        duplicate_source_job_id = conn.execute(
            """
            SELECT COUNT(1)
            FROM (
                SELECT source_job_id
                FROM job_postings
                WHERE source_job_id IS NOT NULL AND source_job_id != ?
                GROUP BY source_job_id
                HAVING COUNT(1) > 1
            )
            """,
            ("",),
        ).fetchone()[0]
        duplicate_url = conn.execute(
            """
            SELECT COUNT(1)
            FROM (
                SELECT normalized_url
                FROM job_postings
                WHERE normalized_url IS NOT NULL AND normalized_url != ?
                GROUP BY normalized_url
                HAVING COUNT(1) > 1
            )
            """,
            ("",),
        ).fetchone()[0]
        duplicate_key = conn.execute(
            """
            SELECT COUNT(1)
            FROM (
                SELECT duplicate_key
                FROM job_postings
                WHERE duplicate_key IS NOT NULL AND duplicate_key != ?
                GROUP BY duplicate_key
                HAVING COUNT(1) > 1
            )
            """,
            ("",),
        ).fetchone()[0]

    print("[DB] Summary")
    print(f"  job_postings={job_count}")
    print(f"  detail_success={detail_success}")
    print(f"  detail_missing={detail_missing}")
    print(f"  match_results_total={match_count}")
    print(f"  match_results_latest_profile={latest_profile_match_count}")
    print(f"  duplicate_source_job_id_groups={duplicate_source_job_id}")
    print(f"  duplicate_normalized_url_groups={duplicate_url}")
    print(f"  duplicate_key_groups={duplicate_key}")


def parse_args():
    parser = argparse.ArgumentParser(description="Personal JobKorea radar")
    parser.add_argument("mode", nargs="?", help="Execution mode")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--keyword-batch-size", type=int, default=10)
    parser.add_argument("--detail-limit", type=int, default=100)
    parser.add_argument("--report-top-n", type=int, default=None)
    parser.add_argument("--keyword-delay", type=float, default=2.0)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    return parser.parse_args()


def is_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    args = parse_args()
    sites = load_sites()
    available_sites = list(sites.keys()) + [
        "jobkorea-taxonomy",
        "jobkorea-detail",
        "jobkorea-match",
        "jobkorea-report",
        "jobkorea-report-only",
        "jobkorea-health",
        "jobkorea-pipeline",
        "jobkorea-multi-pipeline",
    ]

    if args.mode:
        site = args.mode.strip().lower()
    else:
        print("Available modes:", ", ".join(available_sites))
        site = input(
            "Select mode (saramin/jobkorea/jobkorea-taxonomy/jobkorea-detail/jobkorea-match/jobkorea-report/jobkorea-report-only/jobkorea-pipeline/jobkorea-multi-pipeline): "
        ).strip().lower()

    if site == "jobkorea-taxonomy":
        sync_taxonomy()
    elif site == "jobkorea-detail":
        collect_details()
    elif site == "jobkorea-match":
        analyze_matches()
    elif site == "jobkorea-report":
        show_report()
    elif site == "jobkorea-report-only":
        run_report_only(args.report_top_n)
    elif site == "jobkorea-health":
        show_health()
    elif site == "jobkorea-pipeline":
        run_jobkorea_pipeline(sites)
    elif site == "jobkorea-multi-pipeline":
        run_jobkorea_multi_pipeline(sites, args if args.mode else None)
    elif site not in sites:
        logger.error("Invalid site input.")
    else:
        keyword = input("Keyword (example: python): ").strip()
        pages_str = input("Pages to crawl (example: 2): ").strip()
        pages = int(pages_str) if pages_str.isdigit() else 2
        crawl(site, keyword, pages, sites=sites)
