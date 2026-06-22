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
| `fetcher.py` | 정적/동적 HTTP 수집, 제한된 재시도, 비정상 HTML 거부 |
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

## 예외 흐름

- 목록 수집 실패: 해당 페이지를 기록하고 다음 페이지로 진행합니다.
- 상세 수집 실패: 공고에 `detail_status=failed`와 원인을 기록합니다.
- 파이프라인 단계 실패: 다음 단계는 실행하되 요약에서 실패를 구분합니다.
- 비정상 HTML: 성공 데이터로 저장하지 않고 제한된 backoff 후 재시도합니다.

## 현재 기술 부채

- 버전 기반 DB migration이 아닌 `ALTER TABLE` 보정 방식을 사용합니다.
- Selenium 브라우저를 요청마다 생성해 다중 키워드 처리 비용이 큽니다.
- 원본 HTML 보관 만료 정책이 아직 자동화되지 않았습니다.
- 점수 상한 포화 여부를 실제 지원 결과로 보정할 데이터가 부족합니다.

