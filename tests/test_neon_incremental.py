import hashlib
import json
import unittest

from scripts.neon_incremental_crawl import JobListItem, extract_items, parse_datetime


class NeonIncrementalTests(unittest.TestCase):
    def test_canonical_hash_ignores_list_order(self):
        base = {
            "id": 123,
            "title": " 백엔드 개발자 ",
            "companyName": "회사",
            "createdAt": "2026-08-09T10:00:00Z",
            "employmentTypeCodeList": ["B", "A"],
            "areaCodeList": ["2", "1"],
        }
        reordered = {**base, "employmentTypeCodeList": ["A", "B"], "areaCodeList": ["1", "2"]}
        self.assertEqual(
            JobListItem.model_validate(base).canonical_hash(),
            JobListItem.model_validate(reordered).canonical_hash(),
        )

    def test_canonical_hash_changes_with_meaningful_content(self):
        first = JobListItem.model_validate({
            "id": "1", "title": "개발자", "companyName": "회사", "createdAt": "2026-08-09T10:00:00+09:00"
        })
        second = first.model_copy(update={"title": "시니어 개발자"})
        self.assertNotEqual(first.canonical_hash(), second.canonical_hash())

    def test_datetime_is_timezone_aware_kst(self):
        parsed = parse_datetime("2026-08-09T00:00:00Z")
        self.assertEqual(parsed.utcoffset().total_seconds(), 9 * 3600)
        self.assertEqual(parsed.hour, 9)

    def test_extract_items_supports_known_envelopes(self):
        item = {"id": "1"}
        self.assertEqual(extract_items({"content": [item]}), [item])
        self.assertEqual(extract_items({"data": {"items": [item]}}), [item])

    def test_extract_items_rejects_success_shaped_but_unknown_payload(self):
        with self.assertRaisesRegex(ValueError, "job list not found"):
            extract_items({"status": 200, "result": []})


if __name__ == "__main__":
    unittest.main()
