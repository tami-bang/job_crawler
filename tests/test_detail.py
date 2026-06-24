import json
import unittest

from crawler.detail import build_job_from_detail_page, parse_job_detail


class JobKoreaDetailTests(unittest.TestCase):
    def test_extracts_job_fields_from_jobposting_jsonld(self):
        payload = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "백엔드 개발자",
            "employmentType": "FULL_TIME",
            "experienceRequirements": "경력 3년 이상",
            "educationRequirements": "학력무관",
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressRegion": "경기",
                    "addressLocality": "성남시",
                },
            },
        }
        html = (
            "<html><head><script type='application/ld+json'>"
            + json.dumps(payload, ensure_ascii=False)
            + "</script></head><body><h1>백엔드 개발자</h1></body></html>"
        )

        result = parse_job_detail(html)

        self.assertEqual(result["employment_type"], "정규직")
        self.assertEqual(result["location"], "경기 성남시")
        self.assertEqual(result["career"], "경력 3년 이상")
        self.assertEqual(result["education"], "학력무관")

    def test_falls_back_to_visible_employment_label(self):
        html = "<html><body><div>고용형태\n계약직</div></body></html>"

        result = parse_job_detail(html)

        self.assertEqual(result["employment_type"], "계약직")

    def test_uses_street_address_when_region_fields_are_missing(self):
        payload = {
            "@type": "JobPosting",
            "employmentType": "FULL_TIME",
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "서울 강남구 테헤란로 1",
                },
            },
        }
        html = (
            "<script type='application/ld+json'>"
            + json.dumps(payload, ensure_ascii=False)
            + "</script>"
        )

        result = parse_job_detail(html)

        self.assertEqual(result["location"], "서울 강남구 테헤란로 1")

    def test_always_open_deadline_does_not_create_deadline_date(self):
        html = "<html><body><div>마감일 상시채용</div></body></html>"

        result = parse_job_detail(html)

        self.assertEqual(result["deadline"], "상시채용")
        self.assertEqual(result["deadline_date"], "")

    def test_extracts_location_from_visible_job_summary(self):
        html = """
        <html><body>
        <div>
        근무지주소
        서울 강서구 강서로 468
        지도보기
        지원자격
        </div>
        </body></html>
        """

        result = parse_job_detail(html)

        self.assertEqual(result["location"], "서울 강서구 강서로 468")

    def test_builds_summary_job_from_detail_page(self):
        payload = {
            "@type": "JobPosting",
            "title": "AI AX 바이브 코딩 개발자",
            "datePosted": "2026-06-22",
            "validThrough": "2026-07-22T23:59",
            "employmentType": ["FULL_TIME", "CONTRACTOR"],
            "hiringOrganization": {
                "@type": "Organization",
                "name": "㈜글로벌비전",
            },
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "서울 강서구 강서로 468",
                },
            },
            "url": "https://www.jobkorea.co.kr/Recruit/GI_Read/49427812?Oem_Code=C1",
        }
        html = (
            "<html><head><script type='application/ld+json'>"
            + json.dumps(payload, ensure_ascii=False)
            + "</script></head><body>시작일 2026.06.22(월) 마감일 2026.07.22(수)</body></html>"
        )
        parsed = parse_job_detail(html)

        result = build_job_from_detail_page(
            "https://www.jobkorea.co.kr/Recruit/GI_Read/49427812?Oem_Code=C1&sc=7",
            html,
            parsed,
        )

        self.assertEqual(result["job_id"], "49427812")
        self.assertEqual(result["title"], "AI AX 바이브 코딩 개발자")
        self.assertEqual(result["company"], "㈜글로벌비전")
        self.assertEqual(result["location"], "서울 강서구 강서로 468")
        self.assertEqual(result["employment_type"], "정규직, 계약직")


if __name__ == "__main__":
    unittest.main()
