# main.py (실행 엔트리)
from crawler.fetcher import fetch
from crawler.parser_base import parse_html
from crawler.sites import sites
from crawler.utils import save_jobs

def crawl(site_key, pages=2):
    """사이트별 크롤링 실행"""
    site = sites[site_key]
    all_jobs = []
    for page in range(1, pages + 1):
        url = site["base_url"].format(page=page)
        html = fetch(url, dynamic=site["dynamic"])
        if html:
            jobs = parse_html(html, site["selectors"])
            all_jobs.extend(jobs)
    save_jobs(all_jobs, filename=f"data/{site_key}_jobs.csv")

if __name__ == "__main__":
    print("사용 가능한 사이트:", list(sites.keys()))
    site = input("크롤링할 사이트 선택: ")
    if site in sites:
        crawl(site)
    else:
        print("잘못된 사이트 입력")