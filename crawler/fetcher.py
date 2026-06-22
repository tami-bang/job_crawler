# crawler/fetcher.py
import atexit
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/144.0.7559.97 Safari/537.36"
}

_dynamic_driver = None
_chrome_driver_path = None


def _build_chrome_options():
    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    return options


def _create_dynamic_driver():
    global _chrome_driver_path

    if not _chrome_driver_path:
        _chrome_driver_path = ChromeDriverManager().install()

    service = Service(_chrome_driver_path)
    return webdriver.Chrome(service=service, options=_build_chrome_options())


def get_dynamic_driver():
    global _dynamic_driver

    if _dynamic_driver is None:
        _dynamic_driver = _create_dynamic_driver()
    return _dynamic_driver


def close_dynamic_driver():
    global _dynamic_driver

    if _dynamic_driver is None:
        return

    try:
        _dynamic_driver.quit()
    except Exception as exc:
        print(f"[WARN] Selenium driver close failed: {exc}")
    finally:
        _dynamic_driver = None


atexit.register(close_dynamic_driver)


def fetch(url, dynamic=False, retries=3, wait_selector="body", min_html_length=500):
    """
    안정화 fetch 함수
    dynamic=True -> Selenium 사용
    dynamic=False -> requests 사용
    retries -> 실패 시 재시도 횟수
    """
    for attempt in range(1, retries + 1):
        if dynamic:
            try:
                driver = get_dynamic_driver()
                print(f"[INFO] Selenium 시도 {attempt}: {url}")
                driver.get(url)

                # 호출자가 넘긴 selector 기준으로 대기한다.
                try:
                    WebDriverWait(driver, 6).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector or "body"))
                    )
                except Exception:
                    print("[WARN] 페이지 로딩 지연 또는 카드 없음")

                html = driver.page_source

                if is_healthy_html(html, min_html_length=min_html_length):
                    return html
            except Exception as e:
                print(f"[ERROR] Selenium 요청 실패: {e}")
                close_dynamic_driver()
        else:
            try:
                print(f"[INFO] requests 시도 {attempt}: {url}")
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                if is_healthy_html(response.text, min_html_length=min_html_length):
                    return response.text
                print("[ERROR] requests returned unhealthy HTML")
            except requests.RequestException as e:
                print(f"[ERROR] requests 실패: {e}")

        if attempt < retries:
            sleep_seconds = min(2 ** (attempt - 1), 8)
            print(f"[WARN] Attempt {attempt} failed. Retrying in {sleep_seconds}s.")
            time.sleep(sleep_seconds)

    print("[ERROR] 모든 시도 실패")
    return None


def is_healthy_html(html, min_html_length=500):
    if not html or len(html) < min_html_length:
        return False

    lowered = html.lower()
    blocked_markers = [
        "captcha",
        "access denied",
        "blocked",
        "비정상적인 접근",
        "서비스 이용이 제한",
    ]
    return not any(marker in lowered for marker in blocked_markers)
