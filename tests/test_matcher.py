import tempfile
import unittest
from pathlib import Path

from crawler.database import get_connection, init_database
from crawler.matcher import (
    analyze_job,
    apply_score_compression,
    iter_preference_keywords,
    job_passes_hard_filters,
    load_preferences,
    upsert_match_result,
)


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

    def test_high_scores_are_compressed_without_losing_order(self):
        rich_job = make_job(
            "React TypeScript Python FastAPI 풀스택 백엔드 개발자",
            "JavaScript React TypeScript Python FastAPI SQL Docker Git API 웹서비스",
        )
        result = analyze_job(rich_job, self.preferences)

        self.assertGreater(result["raw_score"], result["match_score"])
        self.assertLess(result["match_score"], 100)
        self.assertGreater(
            apply_score_compression(120, self.preferences["weights"]),
            apply_score_compression(100, self.preferences["weights"]),
        )

    def test_raw_and_compressed_scores_are_persisted(self):
        analysis = analyze_job(
            make_job(
                "React TypeScript Python FastAPI 풀스택 백엔드 개발자",
                "JavaScript React TypeScript Python FastAPI SQL Docker Git API 웹서비스",
            ),
            self.preferences,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "matcher.db"
            init_database(db_path)

            with get_connection(db_path) as conn:
                profile_id = conn.execute(
                    "INSERT INTO user_profiles (name) VALUES (?)",
                    ("test-user",),
                ).lastrowid
                job_id = conn.execute(
                    "INSERT INTO job_postings (source, source_job_id, title) VALUES (?, ?, ?)",
                    ("test", "job-1", "테스트 공고"),
                ).lastrowid

                upsert_match_result(conn, profile_id, job_id, analysis)
                saved = conn.execute(
                    "SELECT match_score, raw_score FROM job_match_results"
                ).fetchone()

        self.assertEqual(saved["match_score"], analysis["match_score"])
        self.assertEqual(saved["raw_score"], analysis["raw_score"])

    def test_strict_location_filter_excludes_outside_capital_area(self):
        seoul_job = make_job("Python 백엔드 개발자", "FastAPI SQL")
        busan_job = {**seoul_job, "location": "부산 해운대구"}

        self.assertTrue(job_passes_hard_filters(seoul_job, self.preferences))
        self.assertFalse(job_passes_hard_filters(busan_job, self.preferences))

    def test_boolean_location_metadata_is_not_treated_as_keywords(self):
        keywords = list(iter_preference_keywords(self.preferences))

        self.assertTrue(keywords)
        self.assertFalse(
            any(
                category == "locations" and preference_type == "strict_only"
                for category, preference_type, _keyword, _weight in keywords
            )
        )


if __name__ == "__main__":
    unittest.main()
