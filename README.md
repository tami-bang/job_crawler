# Job Crawler / JobKorea Radar

JobKorea 채용공고를 수집하고, 상세 내용을 저장한 뒤, 개인 선호 조건에 따라 매칭 점수를 계산하고 CSV 리포트로 export하는 개인용 채용 레이더입니다.

현재 주요 흐름은 다음과 같습니다.

```text
JobKorea list page 수집
-> DB 저장
-> 상세 페이지 수집
-> 규칙 기반 매칭 분석
-> 콘솔 리포트 출력
-> CSV/XLSX export
```

## 웹 대시보드

저장된 SQLite 데이터를 FastAPI와 Next.js 화면에서 탐색할 수 있습니다. 대시보드에서는 전체·상세·분석·관심공고 수를 확인하고, 공고 검색·찜하기·메모·지원 상태 관리, 운영 상태 확인, 페이지네이션 리스트, 마감 달력, 엑셀 다운로드, 엑셀 리포트 이메일 발송을 할 수 있습니다.

데이터가 없는 개발 환경에서는 샘플 공고를 생성합니다.

```bash
python scripts/seed_demo_data.py
```

백엔드 실행:

```bash
python -m uvicorn backend.main:app --reload
```

프론트엔드 실행:

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000`을 열면 됩니다. API 문서는 `http://localhost:8000/docs`에서 확인할 수 있습니다.

무료 공개 데모는 [GitHub Pages](https://tami-bang.github.io/job_crawler/)에서 사용할 수 있습니다. 공개 데모는 실제 수집 DB를 변환한 정적 스냅샷을 사용하며 찜, 메모, 지원 상태는 방문자의 브라우저 `localStorage`에만 저장됩니다. 정적 데모에서도 엑셀 다운로드는 브라우저에서 바로 동작합니다.

이메일 첨부 발송은 보안상 SMTP 비밀값이 필요하므로 FastAPI 백엔드가 실행 중일 때 `/api/reports/email`로 처리합니다. 공개 GitHub Pages에서 자동 발송을 쓰려면 별도 FastAPI 백엔드를 배포하고, GitHub 저장소 변수 `REPORT_API_URL`에 그 백엔드 URL을 연결합니다. 발송 서버가 연결되지 않은 상태에서는 다운로드나 메일 작성창으로 우회하지 않고, 발송 서버 연결이 필요하다는 안내를 표시합니다.

백엔드 환경변수:

```bash
JOB_RADAR_SMTP_HOST=smtp.gmail.com
JOB_RADAR_SMTP_PORT=587
JOB_RADAR_SMTP_USER=
JOB_RADAR_SMTP_PASSWORD=
JOB_RADAR_SMTP_FROM=
JOB_RADAR_SMTP_TLS=true
```

프론트가 실제 발송 서버와 연결되었는지는 대시보드 상단의 `메일 서버 연결됨 / 메일 서버 설정 대기` 상태로 확인할 수 있습니다.

무료 공개 데모에서는 네이버지도 API 키 없이도 공고별 `네이버지도 열기` 링크를 제공합니다. 출발지 주소를 입력한 뒤 `네이버지도 열기`를 누르면 출발지와 도착지를 넣은 대중교통 길찾기 화면으로 이동합니다. 네이버지도에서 주소 후보를 확정 선택하면 실제 경로가 표시됩니다.

네이버지도 기준 예상 소요시간까지 화면 안에 직접 표시하려면 선택적으로 FastAPI 백엔드에 Naver Cloud Platform Maps API 키를 설정합니다.

```bash
NAVER_MAPS_CLIENT_ID=
NAVER_MAPS_CLIENT_SECRET=
```

출발지 주소는 화면에서 먼저 형식을 확인합니다. 장소명·역명·도로명 주소처럼 검색 가능한 값을 입력해야 하며, 숫자만 입력하거나 너무 짧은 값은 팝업으로 다시 안내합니다.

## 수동 수집 실행

대상 사이트의 접근 정책을 존중하기 위해 예약 크롤링은 사용하지 않습니다. GitHub Actions의 `잡코리아 채용공고 수집`은 필요할 때만 수동으로 실행할 수 있으며, 접근 제한을 우회하지 않습니다.

자동 실행 순서:

```text
목록 수집 → 상세 수집 → 매칭 분석 → CSV·XLSX 리포트 생성 → 결과 파일 업로드
```

수동으로 실행하려면 GitHub 저장소의 `Actions` 탭에서 `잡코리아 채용공고 수집`을 선택한 뒤 `Run workflow`를 누릅니다. 기본값은 운영형 수집을 기준으로 `키워드 20개 × 페이지 5개`이며, 실행 전에 키워드 수, 페이지 수, 상세 수집 수, 리포트 수를 조정할 수 있습니다.

실행이 끝나면 해당 실행 화면 아래의 `Artifacts`에서 다음 결과를 내려받을 수 있습니다.

* SQLite 데이터베이스
* 채용공고 CSV·XLSX 리포트
* GitHub Pages 정적 데모용 데이터 스냅샷
* 실행 로그

결과 파일은 14일 동안 보관됩니다. GitHub Actions 실행 환경은 매번 새로 생성되므로 실행별 결과를 독립적으로 보관합니다.

로컬에서 같은 방식으로 비대화형 실행을 하려면 다음 명령을 사용합니다.

```bash
python main.py jobkorea-multi-pipeline \
  --keyword-batch-size 20 \
  --pages 5 \
  --detail-limit 100 \
  --report-top-n 200 \
  --keyword-delay 1
python scripts/export_demo_data_from_db.py --limit 500
```

## 주요 기능

* JobKorea 검색 결과 list page 수집
* 공고 중복 감지 및 DB 저장
* 회사 정보 upsert
* 공고 상세 페이지 HTML 저장
* 상세 텍스트 추출
* 사용자 선호 조건 기반 매칭 점수 계산
* 추천 결과 콘솔 출력
* Excel 호환 CSV export
* 전체 파이프라인 한 번에 실행

## 설치 방법

Python 3.11 사용을 권장합니다.

### macOS

```bash
git clone git@github.com:tami-bang/job_crawler.git
cd job_crawler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

실행:

```bash
python main.py
```

가상환경 종료:

```bash
deactivate
```

### Windows

```powershell
py -3.11 -m pip install -r requirements.txt
```

설치 확인:

```powershell
py -3.11 -m pip check
```

## 전체 파이프라인 실행

가장 쉬운 실행 방법입니다.

```powershell
py -3.11 main.py
```

모드 선택에서 다음을 입력합니다.

```text
jobkorea-pipeline
```

예시 입력:

```text
Keyword (example: python): python
Pages to crawl (example: 1): 1
Detail pages to collect (example: 5): 3
Top N report results (example: 10): 10
```

실행 순서:

```text
1. list page 수집
2. detail page 수집
3. match 분석
4. report 출력 및 CSV export
```

## 개별 실행 모드

### 1. JobKorea list 수집

```powershell
py -3.11 main.py
```

입력:

```text
jobkorea
python
1
```

결과:

* JobKorea 검색 결과 수집
* `job_postings`, `companies`, `posting_history` DB 저장
* `data/jobkorea_python_jobs.csv` 생성

### 2. 상세 페이지 수집

```powershell
py -3.11 main.py
```

입력:

```text
jobkorea-detail
5
```

결과:

* DB에 저장된 공고 중 상세 수집이 필요한 공고 조회
* 상세 HTML을 `raw_pages`에 저장
* 상세 텍스트를 `job_postings`에 저장

### 3. 매칭 분석

```powershell
py -3.11 main.py
```

입력:

```text
jobkorea-match
```

전체 분석하려면 다음 입력에서 Enter를 누릅니다.

결과:

* 상세 수집 완료 공고만 분석
* `job_match_results`에 매칭 결과 저장
* 같은 공고는 중복 저장하지 않고 최신 결과로 갱신

### 4. 리포트 조회 및 CSV export

```powershell
py -3.11 main.py
```

입력:

```text
jobkorea-report
10
```

결과:

* 매칭 점수 높은 순서로 TOP N 출력
* `data/jobkorea_match_report.csv` 생성

### 5. JobKorea taxonomy 수집

```powershell
py -3.11 main.py
```

입력:

```text
jobkorea-taxonomy
```

결과:

* JobKorea 상세검색 조건을 reference data로 저장
* `taxonomy_groups`, `taxonomy_values`, `taxonomy_value_snapshots` 저장

## 사용자 선호 조건 수정

사용자 선호 조건은 다음 파일에서 수정합니다.

```text
config/user_preferences.json
```

주요 설정:

```json
{
  "preferences": {
    "job_keywords": {
      "preferred": ["백엔드", "서버", "API"]
    },
    "skill_keywords": {
      "preferred": ["Python", "FastAPI", "SQL", "AWS"]
    },
    "locations": {
      "preferred": ["서울", "경기"]
    },
    "employment_types": {
      "preferred": ["정규직"],
      "avoid": ["아르바이트", "파견직"]
    },
    "penalties": {
      "critical": ["보험영업"],
      "major": ["영업"],
      "minor": ["주말근무"]
    }
  }
}
```

가중치도 같은 파일에서 수정할 수 있습니다.

`hard_filters.strict_location_only`가 `true`이면 `hard_filters.locations`에 지정된 서울·경기·인천 공고만 매칭 분석과 대시보드에 표시됩니다. 제외 지역은 점수를 낮추는 방식이 아니라 대상에서 제거합니다.

```json
{
  "weights": {
    "job_preferred": 12,
    "skill_preferred": 8,
    "location_preferred": 10,
    "penalty_major": -25
  }
}
```

수정 후 다시 실행:

```text
jobkorea-match
jobkorea-report
```

## 결과 파일 위치

```text
data/job_radar.db
```

SQLite DB 파일입니다.

```text
data/jobkorea_python_jobs.csv
```

list page 수집 결과 CSV입니다.

```text
data/jobkorea_match_report.csv
```

매칭 분석 리포트 CSV입니다. Excel에서 바로 열 수 있도록 `utf-8-sig`로 저장됩니다.

## 추천 테스트 순서

처음 실행할 때는 아래 순서를 추천합니다.

```text
1. jobkorea
2. jobkorea-detail
3. jobkorea-match
4. jobkorea-report
```

또는 한 번에 실행:

```text
jobkorea-pipeline
```

예시:

```text
jobkorea-pipeline
python
1
3
10
```

## 테스트

실제 채용 사이트에 요청하지 않고 파서, 날짜 정규화, 중복 저장, 매칭 점수, 리포트 생성을 검증합니다.

```bash
python -m unittest discover -s tests -v
```

Python 문법 컴파일까지 함께 확인하려면:

```bash
python -m compileall -q main.py crawler scripts
python -m unittest discover -s tests -v
```

프로젝트 정의와 설계 문서는 `docs/`에서 확인할 수 있습니다.

## 자주 발생하는 문제

### Python 버전 문제

Python 3.13에서는 일부 고정 패키지 설치가 불안정할 수 있습니다.

권장:

```powershell
py -3.11 main.py
```

### Selenium 또는 ChromeDriver 문제

`webdriver_manager`가 필요합니다.

```powershell
py -3.11 -m pip install webdriver-manager
```

Chrome 브라우저가 설치되어 있어야 합니다.

### JobKorea 카드가 0개로 나오는 경우

JobKorea 페이지 구조가 바뀌었을 수 있습니다.

확인할 파일:

```text
config/sites.json
crawler/parser.py
```

### 상세 수집 결과가 비어 있는 경우

일부 공고는 이미지형 상세 페이지일 수 있습니다. 이 경우 텍스트 추출이 제한됩니다.

현재 OCR은 사용하지 않습니다.

### 매칭 결과가 없을 경우

먼저 상세 수집이 완료되어야 합니다.

순서:

```text
jobkorea
jobkorea-detail
jobkorea-match
jobkorea-report
```

### CSV 한글이 깨지는 경우

CSV는 `utf-8-sig`로 저장됩니다. Excel에서 바로 열 수 있습니다.

그래도 깨지면 Excel의 데이터 가져오기 기능에서 UTF-8 인코딩을 선택하세요.

## 현재 제외된 기능

* OpenAI API 또는 외부 AI API 분석
* 상세 페이지 OCR
* Selenium taxonomy 고도화
* 자동 스케줄러

## 주의

크롤링은 과도하게 실행하지 마세요. 요청 간격을 지키고, 대상 사이트에 부담을 주지 않는 범위에서 사용하세요.
