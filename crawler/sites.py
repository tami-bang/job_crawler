# crawler/sites.py

"""
사이트별 설정 (동적 페이지 포함, 최신 CSS 선택자 기준)
- base_url: 페이지 URL (검색어 {keyword}, 페이지 번호 {page} 사용 가능)
- selectors: CSS 선택자
- dynamic: Selenium 사용 여부
"""
sites = {
    "saramin": {
        "name": "사람인",
        "base_url": (
            "https://www.saramin.co.kr/zf_user/search"
            "?searchType=search&searchword={keyword}&recruitPage={page}"
        ),
        "selectors": {
            "card": "div.item_recruit",
            "title": "h2.job_tit a",
            "company": "strong.corp_name",
            "location": "div.job_condition span.loc",
            "url": "h2.job_tit a"
        },
        "dynamic": True
    },
    "jobkorea": {
        "name": "잡코리아",
        "base_url": (
            "https://www.jobkorea.co.kr/Search/"
            "?stext={keyword}&page={page}"
        ),
        "selectors": {
            "card": "div.list-post",       # 공고 블록
            "title": "a.title",            # 공고 제목
            "company": "a.name",           # 회사명
            "location": "span.loc",        # 근무지
            "url": "a.title"               # 상세 URL
        },
        "dynamic": True
    }
}
