# crawler/parser_base.py 함수 하나만 두고, 사이트별 selector만 전달
from bs4 import BeautifulSoup

def parse_html(html, selectors):
    """
    공통 HTML 파서
    selectors: dict(title, company, location, url, card)
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    card_selector = selectors.get("card", "div.job-card")
    for card in soup.select(card_selector):
        jobs.append({
            "title": card.select_one(selectors["title"]).get_text(strip=True) if card.select_one(selectors["title"]) else "",
            "company": card.select_one(selectors["company"]).get_text(strip=True) if card.select_one(selectors["company"]) else "",
            "location": card.select_one(selectors["location"]).get_text(strip=True) if card.select_one(selectors["location"]) else "",
            "url": card.select_one(selectors["url"])["href"] if card.select_one(selectors["url"]) else ""
        })
    return jobs