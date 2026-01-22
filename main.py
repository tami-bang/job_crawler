# main.py
import json
from crawler.fetcher import fetch
from crawler.parser import parse_html
from crawler.saver import save_jobs
from crawler.logger_setup import setup_logger

# 로거 생성
logger = setup_logger()

def load_sites(config_path="config/sites.json"):
    # 사이트 설정 로드
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def crawl(site_key, keyword, pages=2, sites=None):
    site = sites[site_key]
    all_jobs = []
    for page in range(1, pages + 1):
        url = site["base_url"].format(keyword=keyword, page=page)
        logger.info(f"크롤링 중: {site['name']} 페이지 {page} -> {url}")
        html = fetch(url, dynamic=site["dynamic"])
        if html:
            jobs = parse_html(html, site["selectors"])
            all_jobs.extend(jobs)
        else:
            logger.warning(f"페이지 {page} HTML 가져오기 실패")
    if all_jobs:
        save_jobs(all_jobs, filename=f"data/{site_key}_{keyword}_jobs.csv")
    else:
        logger.error("추출된 공고가 없습니다. 선택자 또는 구조를 확인하세요.")

if __name__ == "__main__":
    sites = load_sites()
    print("사용 가능한 사이트:", ", ".join(sites.keys()))
    site = input("크롤링할 사이트 선택 (saramin/jobkorea): ").strip().lower()
    if site not in sites:
        logger.error("잘못된 사이트 입력")
    else:
        keyword = input("검색어 입력 (예: python): ").strip()
        pages_str = input("크롤링할 페이지 수 입력 (예: 2): ").strip()
        pages = int(pages_str) if pages_str.isdigit() else 2
        crawl(site, keyword, pages, sites=sites)
