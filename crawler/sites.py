# sites.py 사이트별 정보만 정의
"""
사이트별 설정
- base_url: 페이지 URL (페이지 번호 {page} 사용 가능)
- selectors: CSS 선택자
- dynamic: 동적 페이지 여부
"""
sites = {
    "site1": {
        "name": "Site 1",
        "base_url": "https://example.com/search?page={page}",
        "selectors": {
            "card": "div.job-card",
            "title": ".job-title",
            "company": ".company-name",
            "location": ".job-location",
            "url": "a"
        },
        "dynamic": False
    },
    "site2": {
        "name": "Site 2",
        "base_url": "https://example2.com/list?page={page}",
        "selectors": {
            "card": ".post",
            "title": ".title",
            "company": ".name",
            "location": ".loc",
            "url": ".link"
        },
        "dynamic": True
    }
}