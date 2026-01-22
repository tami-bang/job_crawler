# crawler/parser_base.py 함수 하나만 두고, 사이트별 selector만 전달
from bs4 import BeautifulSoup

def parse_html(html, selectors):
    """
    공통 HTML 파서
    selectors: dict(title, company, location, url, card)
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(selectors['card'])
    print(f"[DEBUG] 카드 선택자 '{selectors['card']}'로 찾은 카드 수: {len(cards)}")
    
    jobs = []
    for card in cards:
        title_tag = card.select_one(selectors.get("title"))
        company_tag = card.select_one(selectors.get("company"))
        location_tag = card.select_one(selectors.get("location"))
        url_tag = card.select_one(selectors.get("url"))
        
        job = {
            "title": title_tag.get_text(strip=True) if title_tag else "",
            "company": company_tag.get_text(strip=True) if company_tag else "",
            "location": location_tag.get_text(strip=True) if location_tag else "",
            "url": url_tag["href"] if url_tag and url_tag.has_attr("href") else ""
        }
        jobs.append(job)
    return jobs
