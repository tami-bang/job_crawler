# crawler/fetcher.py
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def fetch(url, dynamic=False):
    """
    공통 fetch 함수
    dynamic=True -> Selenium 사용
    dynamic=False -> requests 사용
    """
    if dynamic:
        options = Options()
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        html = driver.page_source
        driver.quit()
        return html
    else:
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=7)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"페이지 요청 실패: {e}")
            return None
