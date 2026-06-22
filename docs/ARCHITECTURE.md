# Architecture

## 시스템 구성

```text
sites.json / user_preferences.json
                │
                ▼
        CLI Orchestrator (main.py)
                │
      ┌─────────┼──────────┐
      ▼         ▼          ▼
   Fetcher    Parser    Taxonomy
 requests/   list/detail  reference
 Selenium        │          data
      └──────────┼──────────┘
                 ▼
          SQLite Repository
      raw → normalized → history
                 │
                 ▼
          Explainable Matcher
                 │
                 ▼
        Console / CSV / XLSX
```

## 모듈 책임

| 모듈 | 책임 |
| --- | --- |
| `main.py` | CLI 입력, 파이프라인 순서, 단계별 결과 요약 |
| `fetcher.py` | 정적/동적 HTTP 수집, 제한된 재시도, 비정상 HTML 거부, ChromeDriver 재사용 |
| `parser.py` | 목록 카드 파싱, URL·마감일 정규화 |
| `detail.py` | 상세 본문과 업무·자격·우대·복지 영역 추출 |
| `job_store.py` | 회사/공고 upsert, 중복키, 변경 이력 |
| `database.py` | SQLite 연결과 현재 스키마 초기화 |
| `matcher.py` | 사용자 설정 기반 설명 가능한 점수 계산 |
| `report.py` | 현재 유효 공고 조회와 CSV/XLSX 생성 |
| `health.py` | 수집·상세·마감일·중복 상태 점검 |

## 주요 데이터 흐름

1. `main.py`가 사이트 설정과 실행 옵션을 읽습니다.
2. 목록 HTML을 수집하고 비정상 응답을 거부합니다.
3. 파서가 공고 ID, URL, 회사, 조건, 마감일을 정규화합니다.
4. 원본 HTML을 저장하고 중복키 기준으로 공고를 upsert합니다.
5. 상세 수집 대상만 골라 본문과 섹션 데이터를 보강합니다.
6. 사용자 선호 설정을 읽어 각 점수와 이유를 저장합니다.
7. 유효 공고만 점수순으로 CSV와 XLSX에 출력합니다.

## 브라우저 수명주기

- 동적 수집은 프로세스 안에서 ChromeDriver 하나를 재사용합니다.
- 세션 오류가 발생하면 기존 드라이버를 종료하고 다음 재시도에서 새로 생성합니다.
- 프로세스 종료 시 `atexit` 정리 함수가 남은 브라우저를 닫습니다.
- 현재 파이프라인은 순차 실행을 전제로 하며 병렬 브라우저 공유는 지원하지 않습니다.

## 점수 보정

- 기술 키워드와 커리어 목표 부스트는 설정된 상한까지만 가산합니다.
- 75점을 넘는 원점수는 설정 비율로 압축해 여러 공고가 100점에 몰리는 현상을 줄입니다.
- 원점수와 최종 점수를 매칭 결과에 함께 저장해 보정 과정을 비교할 수 있습니다.
- 보정 시작점과 비율은 `config/user_preferences.json`에서 변경할 수 있습니다.

## 예외 흐름

- 목록 수집 실패: 해당 페이지를 기록하고 다음 페이지로 진행합니다.
- 상세 수집 실패: 공고에 `detail_status=failed`와 원인을 기록합니다.
- 파이프라인 단계 실패: 다음 단계는 실행하되 요약에서 실패를 구분합니다.
- 비정상 HTML: 성공 데이터로 저장하지 않고 제한된 backoff 후 재시도합니다.

## 현재 기술 부채

- 버전 기반 DB migration이 아닌 `ALTER TABLE` 보정 방식을 사용합니다.
- 원본 HTML 보관 만료 정책이 아직 자동화되지 않았습니다.
- 점수 상한 포화 여부를 실제 지원 결과로 보정할 데이터가 부족합니다.
