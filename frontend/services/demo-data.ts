import type { Job } from "./api";

export const demoJobs: Job[] = [
  {
    id: 1, title: "Python FastAPI 백엔드 개발자", company_name: "Layer Nine",
    location: "서울 강남구", career: "신입·경력 2년", employment_type: "정규직",
    deadline: "상시채용", detail_url: null, skill_candidates: "Python, FastAPI, PostgreSQL, Docker",
    match_score: 92, recommendation_level: "strong", matched_keywords: ["Python", "FastAPI", "SQL", "Docker"],
    positive_reasons: ["희망 기술 Python 경험과 연결됩니다.", "선호 지역 서울에 해당합니다."], negative_reasons: [],
    is_favorite: false, favorite_memo: null, favorite_status: null,
  },
  {
    id: 2, title: "데이터 플랫폼 엔지니어", company_name: "Orbit Works",
    location: "서울 성동구", career: "경력 1년 이상", employment_type: "정규직",
    deadline: "D-18", detail_url: null, skill_candidates: "Python, Airflow, AWS, SQL",
    match_score: 86, recommendation_level: "strong", matched_keywords: ["Python", "AWS", "SQL", "데이터"],
    positive_reasons: ["데이터 파이프라인 커리어 목표와 일치합니다."], negative_reasons: [],
    is_favorite: false, favorite_memo: null, favorite_status: null,
  },
  {
    id: 3, title: "React 기반 프론트엔드 개발자", company_name: "Nouveau Lab",
    location: "경기 성남시", career: "신입", employment_type: "정규직",
    deadline: "D-12", detail_url: null, skill_candidates: "React, TypeScript, Next.js",
    match_score: 81, recommendation_level: "good", matched_keywords: ["React", "TypeScript", "Next.js"],
    positive_reasons: ["프론트엔드 웹개발 관심 직무에 해당합니다."], negative_reasons: [],
    is_favorite: false, favorite_memo: null, favorite_status: null,
  },
  {
    id: 4, title: "서비스 자동화 엔지니어", company_name: "Mono Systems",
    location: "서울 영등포구", career: "경력 무관", employment_type: "계약직",
    deadline: "D-23", detail_url: null, skill_candidates: "Python, Selenium, CI/CD",
    match_score: 76, recommendation_level: "good", matched_keywords: ["Python", "자동화", "Git"],
    positive_reasons: ["Python 업무 자동화 경험을 활용할 수 있습니다."], negative_reasons: [],
    is_favorite: false, favorite_memo: null, favorite_status: null,
  },
  {
    id: 5, title: "주니어 풀스택 개발자", company_name: "Pixel Route",
    location: "인천 연수구", career: "신입·경력", employment_type: "정규직",
    deadline: "상시채용", detail_url: null, skill_candidates: "Next.js, FastAPI, Docker",
    match_score: 73, recommendation_level: "good", matched_keywords: ["Next.js", "FastAPI", "Docker"],
    positive_reasons: ["프론트엔드와 백엔드 기술을 함께 활용합니다."], negative_reasons: [],
    is_favorite: false, favorite_memo: null, favorite_status: null,
  },
  {
    id: 6, title: "클라우드 운영 개발자", company_name: "Cloud Canvas",
    location: "서울 마포구", career: "경력 2년 이상", employment_type: "정규직",
    deadline: "D-7", detail_url: null, skill_candidates: "AWS, Linux, Terraform",
    match_score: 68, recommendation_level: "good", matched_keywords: ["AWS", "Linux", "인프라"],
    positive_reasons: ["클라우드 엔지니어 관심 분야와 연결됩니다."], negative_reasons: [],
    is_favorite: false, favorite_memo: null, favorite_status: null,
  },
];
