"""Shared browser-quality HTTP headers for JobKorea collectors."""

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
    "Cache-Control": "no-cache",
    "Origin": "https://www.jobkorea.co.kr",
    "Pragma": "no-cache",
    "Referer": "https://www.jobkorea.co.kr/recruit/joblist?menucode=duty",
    "Sec-CH-UA": '"Google Chrome";v="151", "Chromium";v="151", "Not_A Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Sec-Fetch-Site": "same-origin",
}

LIST_HEADERS = {
    **BROWSER_HEADERS,
    "Accept": "text/html, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "X-Requested-With": "XMLHttpRequest",
}

DETAIL_HEADERS = {
    **BROWSER_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Upgrade-Insecure-Requests": "1",
}
