# Job Crawler / JobKorea Radar

JobKorea 채용공고를 수집하고, 상세 내용을 저장한 뒤, 개인 선호 조건에 따라 매칭 점수를 계산하고 CSV 리포트로 export하는 개인용 채용 레이더입니다.

현재 주요 흐름은 다음과 같습니다.

```text
JobKorea list page 수집
-> DB 저장
-> 상세 페이지 수집
-> 규칙 기반 매칭 분석
-> 콘솔 리포트 출력
-> CSV export
```

## 자동 실행 배포

GitHub Actions에서 평일 오전 9시(KST)에 잡코리아 공고를 자동으로 수집하고 분석합니다.

자동 실행 순서:

```text
목록 수집 → 상세 수집 → 매칭 분석 → CSV·XLSX 리포트 생성 → 결과 파일 업로드
```

수동으로 실행하려면 GitHub 저장소의 `Actions` 탭에서 `잡코리아 채용공고 수집`을 선택한 뒤 `Run workflow`를 누릅니다. 키워드 수, 페이지 수, 상세 수집 수, 리포트 수를 실행 전에 조정할 수 있습니다.

실행이 끝나면 해당 실행 화면 아래의 `Artifacts`에서 다음 결과를 내려받을 수 있습니다.

* SQLite 데이터베이스
* 채용공고 CSV·XLSX 리포트
* 실행 로그

결과 파일은 14일 동안 보관됩니다. GitHub Actions 실행 환경은 매번 새로 생성되므로 현재 자동 실행은 실행별 결과를 독립적으로 보관합니다.

로컬에서 같은 방식으로 비대화형 실행을 하려면 다음 명령을 사용합니다.

```bash
python main.py jobkorea-multi-pipeline \
  --keyword-batch-size 5 \
  --pages 1 \
  --detail-limit 25 \
  --report-top-n 50 \
  --keyword-delay 2
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
* 대시보드/UI
* 상세 페이지 OCR
* Selenium taxonomy 고도화
* 자동 스케줄러

## 주의

크롤링은 과도하게 실행하지 마세요. 요청 간격을 지키고, 대상 사이트에 부담을 주지 않는 범위에서 사용하세요.
