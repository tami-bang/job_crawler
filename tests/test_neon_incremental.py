import unittest
from datetime import datetime

from scripts.neon_incremental_crawl import (
    KST,
    JobListItem,
    extract_items,
    parse_datetime,
    parse_job_list_html,
)


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

    def test_parses_real_gi_list_row_shape(self):
        html = """
        <table><tr class="devloopArea" data-gno="49730351">
          <td class="tplCo"><a class="link">㈜안랩</a></td>
          <td class="tplTit"><strong><a href="/Recruit/GI_Read/49730351?x=1" title="개발자 채용">개발자 채용</a></strong>
            <p class="etc"><span class="cell">신입·경력</span><span class="cell">대졸↑</span><span class="cell">경기 성남시</span><span class="cell">정규직</span></p>
            <p class="dsc">Python, 백엔드</p></td>
          <td class="odd"><span class="time"><span>2</span>일 전 등록</span><span class="date"><span>~08/17</span>(월)</span></td>
        </tr></table>
        """
        now = datetime(2026, 8, 9, 12, tzinfo=KST)
        item = parse_job_list_html(html, now)[0]
        self.assertEqual(item["id"], "49730351")
        self.assertEqual(item["companyName"], "㈜안랩")
        self.assertEqual(item["createdAt"].day, 7)
        self.assertEqual(item["applicationPeriod"]["end"].day, 17)
        self.assertEqual(item["areaCodeList"], ["경기 성남시"])


if __name__ == "__main__":
    unittest.main()
