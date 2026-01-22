# crawler/fetcher.py
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/144.0.7559.97 Safari/537.36"
}

def fetch(url, dynamic=False, retries=2):
    """
    안정화 fetch 함수
    dynamic=True -> Selenium 사용
    dynamic=False -> requests 사용
    retries -> 실패 시 재시도 횟수
    """
    for attempt in range(1, retries + 1):
        if dynamic:
            options = Options()
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")
            # Headless 모드 끄고 실제 브라우저로 확인 가능
            # options.add_argument("--headless=new")  

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            try:
                print(f"[INFO] Selenium 시도 {attempt}: {url}")
                driver.get(url)

                # 카드 로딩될 때까지 최대 10초 대기
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.item_recruit"))
                    )
                except:
                    print("[WARN] 페이지 로딩 지연 또는 카드 없음")

                html = driver.page_source
                driver.quit()
                
                if html:
                    return html
            except Exception as e:
                print(f"[ERROR] Selenium 요청 실패: {e}")
                driver.quit()
        else:
            try:
                print(f"[INFO] requests 시도 {attempt}: {url}")
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                print(f"[ERROR] requests 실패: {e}")

        print(f"[WARN] 시도 {attempt} 실패, 재시도 중...")

    print("[ERROR] 모든 시도 실패")
    return None