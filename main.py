# main.py (실행 엔트리)# main.py
from crawler.fetcher import fetch
from crawler.parser_base import parse_html
from crawler.sites import sites
from crawler.utils import save_jobs

def crawl(site_key, keyword, pages=2):
    site = sites[site_key]
    all_jobs = []
    for page in range(1, pages + 1):
        url = site["base_url"].format(keyword=keyword, page=page)
        print(f"[INFO] 크롤링 중: {site['name']} 페이지 {page} -> {url}")
        html = fetch(url, dynamic=site["dynamic"])
        if html:
            jobs = parse_html(html, site["selectors"])
            all_jobs.extend(jobs)
        else:
            print(f"[WARN] 페이지 {page} HTML 가져오기 실패")
    if all_jobs:
        save_jobs(all_jobs, filename=f"data/{site_key}_{keyword}_jobs.csv")
    else:
        print("[ERROR] 추출된 공고가 없습니다. 선택자 또는 구조를 확인하세요.")

if __name__ == "__main__":
    print("사용 가능한 사이트:", ", ".join(sites.keys()))
    site = input("크롤링할 사이트 선택 (saramin/jobkorea): ").strip().lower()
    if site not in sites:
        print("[ERROR] 잘못된 사이트 입력")
    else:
        keyword = input("검색어 입력 (예: python): ").strip()
        pages_str = input("크롤링할 페이지 수 입력 (예: 2): ").strip()
        pages = int(pages_str) if pages_str.isdigit() else 2
        crawl(site, keyword, pages)
