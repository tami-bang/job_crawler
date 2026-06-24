"use client";

import { useMemo, useState } from "react";

const updates = [
  {
    date: "2026.06.24",
    tag: "READABILITY",
    title: "별로 버튼, 경력 연차, 엑셀 가독성 보강",
    items: [
      "`⭐ 별로` 버튼은 기본 다크그레이로 맞추고 클릭 반응만 주황색으로 바꿨습니다.",
      "경력 필터는 신입, 경력무관, 신입·경력, 경력 1년 이상 순으로 읽히게 정렬했습니다.",
      "원문 스냅샷의 경력 연차를 다시 읽어 `경력1년이상`처럼 표시하고, 엑셀은 줄바꿈·열 너비·행 높이를 조정했습니다.",
    ],
  },
  {
    date: "2026.06.24",
    tag: "STATE SAFE",
    title: "저장·읽음·별로 상태가 목록 흐름을 흔들지 않게 수정",
    items: [
      "관심공고 저장 후에도 현재 페이지와 공고 순서가 유지되도록 관심공고 우선 정렬을 제거했습니다.",
      "저장된 공고는 네온핑크 카드로 표시하고, 저장과 별도로 `⭐ 별로` 상태를 추가했습니다.",
      "사용자가 남긴 메모, 읽음 표시, 숨김 상태를 크롤링·export·UI 수정 과정에서 리셋하지 않는 원칙을 프로젝트 규칙에 추가했습니다.",
    ],
  },
  {
    date: "2026.06.24",
    tag: "COVERAGE",
    title: "AI AX·바이브코딩 공고 누락 보강",
    items: [
      "JobKorea 상세 URL을 직접 넣어도 공고를 저장하고 상세 스냅샷까지 반영할 수 있는 수집 모드를 추가했습니다.",
      "AI AX, 바이브코딩, 바이브 코딩, 노코드, 로우코드 키워드를 검색·매칭 기준에 보강했습니다.",
      "정적 대시보드는 상세 수집이 완료된 공고만 내보내도록 정리해 대기 상태 데이터가 섞이지 않게 했습니다.",
    ],
  },
  {
    date: "2026.06.24",
    tag: "DATA QUALITY",
    title: "마감 표기와 상세 스냅샷 신뢰도 보강",
    items: [
      "상시채용 공고가 마감 미정처럼 보이지 않도록 원문 스냅샷의 마감일 값을 다시 반영했습니다.",
      "마감 정보가 비어 있는 공고는 중복 문구 없이 `마감 미정`으로 정리했습니다.",
      "엑셀 다운로드와 이메일 리포트에서도 상시채용, 마감 미정, 날짜형 마감이 같은 기준으로 표시되도록 맞췄습니다.",
    ],
  },
  {
    date: "2026.06.24",
    tag: "UX TUNE",
    title: "대시보드 탐색 흐름과 공통 필터 정리",
    items: [
      "대시보드 상단 공백과 불필요한 운영 배지를 줄였습니다.",
      "경력 필터, 전체 지역 칩, 확인한 공고의 회색 표시를 공통 탐색 화면에 적용했습니다.",
      "저장된 상세 텍스트를 스냅샷으로 볼 수 있는 흐름을 추가했습니다.",
    ],
  },
  {
    date: "2026.06.23",
    tag: "DATA PATCH",
    title: "상시채용 공고가 마감 공고로 분류되지 않도록 정규화",
    items: [
      "상시채용 공고는 deadline_date를 비워 마감 달력과 마감 탭에서 제외되도록 수정했습니다.",
      "수집·상세수집·정적 데모 export 단계에서 모두 같은 기준을 적용했습니다.",
      "엑셀 다운로드와 이메일 리포트에서도 상시채용은 날짜 대신 상시채용으로 표시되도록 맞췄습니다.",
    ],
  },
  {
    date: "2026.06.23",
    tag: "UX PATCH",
    title: "네이버지도 길찾기 흐름을 실제 사용 방식에 맞게 정리",
    items: [
      "공고별 버튼을 `네이버지도 열기` 하나로 정리했습니다.",
      "마우스를 올렸을 때만 보이는 안내 툴팁을 추가했습니다.",
      "출발지·도착지 후보를 선택한 뒤 대중교통 경로를 확인하는 실제 네이버지도 흐름을 안내합니다.",
    ],
  },
  {
    date: "2026.06.23",
    tag: "REPORT",
    title: "엑셀 리포트 이메일 발송 조건을 명확하게 표시",
    items: [
      "정적 데모에서 다운로드/메일 작성창으로 우회하던 흐름을 제거했습니다.",
      "REPORT_API_URL과 SMTP 설정값이 연결되어야 실제 이메일 발송이 가능하다는 안내를 추가했습니다.",
      "README에 필요한 SMTP 환경변수와 Gmail 앱 비밀번호 주의사항을 정리했습니다.",
    ],
  },
  {
    date: "2026.06.23",
    tag: "DASHBOARD",
    title: "대량 공고 탐색에 맞춘 리스트형 대시보드 개선",
    items: [
      "카드형 대신 많은 공고를 빠르게 훑을 수 있는 리스트형 결과 화면을 적용했습니다.",
      "15개, 50개, 100개씩 보기와 이전/다음 페이지 이동을 추가했습니다.",
      "마감 임박순, 시작 최신순, 회사명 가나다순 등 정렬 조건을 추가했습니다.",
    ],
  },
  {
    date: "2026.06.23",
    tag: "FILTER",
    title: "실사용 필터와 마감 관리 기능 추가",
    items: [
      "서울·경기·인천의 시/구 단위 다중 지역 필터를 추가했습니다.",
      "매칭 점수, 경력, 고용형태 조건 필터를 실제 결과에 반영했습니다.",
      "마감 달력과 오늘 표시, 마감된 공고 분리 보기를 추가했습니다.",
    ],
  },
  {
    date: "2026.06.23",
    tag: "SHORTLIST",
    title: "관심공고 지원 상태 관리 확장",
    items: [
      "지원예정, 지원완료, 서류합격, 1차합격, 2차합격, 최종합격 상태를 추가했습니다.",
      "관심공고 메모와 상태 변경이 브라우저 localStorage에 유지되도록 정리했습니다.",
      "관심공고가 리스트 상단에 우선 보이도록 탐색 흐름을 개선했습니다.",
    ],
  },
];

export default function UpdatesPage() {
  const pageSizeOptions = [15, 50, 100];
  const [pageSize, setPageSize] = useState(15);
  const [page, setPage] = useState(1);
  const sortedUpdates = useMemo(() => (
    [...updates].sort((a, b) => b.date.localeCompare(a.date))
  ), []);
  const totalPages = Math.max(1, Math.ceil(sortedUpdates.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleUpdates = sortedUpdates.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <section className="pageSection">
      <div className="eyebrow"><span>03</span> PATCH NOTES</div>
      <h1 className="pageTitle">매일 조금씩,<br /><em>쓰는 도구</em>로 다듬기.</h1>
      <div className="sectionHeading updateHeading">
        <div>
          <span>BUILD LOG</span>
          <h2>업데이트 로그</h2>
        </div>
        <p>WHAT CHANGED · WHY IT MATTERS</p>
      </div>
      <div className="updateList">
        {visibleUpdates.map((update) => (
          <article className="updateItem" key={`${update.date}-${update.title}`}>
            <div className="updateMeta">
              <strong>{update.date}</strong>
              <span>{update.tag}</span>
            </div>
            <div className="updateBody">
              <h3>{update.title}</h3>
              <ul>
                {update.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          </article>
        ))}
      </div>
      <div className="pagination updatePagination" aria-label="업데이트 로그 페이지네이션">
        <button disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>←</button>
        <strong>{currentPage} / {totalPages}</strong>
        <button disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>→</button>
        <label className="pageSizeSelect bottom">
          <span>표시 개수</span>
          <select
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(1);
            }}
          >
            {pageSizeOptions.map((option) => <option key={option} value={option}>{option}개씩</option>)}
          </select>
        </label>
      </div>
    </section>
  );
}
