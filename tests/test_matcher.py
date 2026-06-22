import unittest
from pathlib import Path

from crawler.matcher import analyze_job, load_preferences


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_job(title, description):
    return {
        "id": 1,
        "title": title,
        "location": "서울",
        "career": "신입",
        "education": "학력무관",
        "employment_type": "정규직",
        "summary_text": description,
        "description_text": description,
        "main_tasks": description,
        "qualifications": description,
        "preferred_conditions": "",
        "benefits": "",
        "skill_candidates": description,
        "detail_status": "success",
    }


class MatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preferences = load_preferences(PROJECT_ROOT / "config/user_preferences.json")

    def test_analysis_is_explainable_and_bounded(self):
        job = make_job("Python FastAPI 백엔드 개발자", "API SQL Docker Git 웹서비스 개발")
        result = analyze_job(job, self.preferences)

        self.assertGreaterEqual(result["match_score"], 0)
        self.assertLessEqual(result["match_score"], 100)
        self.assertTrue(result["recommendation_level"])
        self.assertTrue(result["matched_keywords"])
        self.assertIn("점수", result["reason"])

    def test_qa_only_job_ranks_below_backend_job(self):
        backend = analyze_job(
            make_job("Python 백엔드 개발자", "FastAPI SQL API 서버 개발"),
            self.preferences,
        )
        qa_only = analyze_job(
            make_job("QA 담당자", "수동 테스트 검증 품질보증"),
            self.preferences,
        )

        self.assertGreater(backend["match_score"], qa_only["match_score"])
        self.assertTrue(qa_only["negative_reasons"])


if __name__ == "__main__":
    unittest.main()

