# crawler/report.py
import csv
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from crawler.database import DEFAULT_DB_PATH, get_connection, init_database


DEFAULT_REPORT_DIR = "data"
DEFAULT_REPORT_NAME_TEMPLATE = "{date}_jobkorea_match.csv"
DEFAULT_ALLOWED_LOCATION_PREFIXES = ("서울", "경기", "인천")


def build_match_report(
    limit=None,
    output_path=None,
    db_path=DEFAULT_DB_PATH,
    allowed_location_prefixes=DEFAULT_ALLOWED_LOCATION_PREFIXES,
):
    init_database(db_path)

    rows = get_match_results(
        limit=limit,
        db_path=db_path,
        allowed_location_prefixes=allowed_location_prefixes,
    )
    report_rows = [format_report_row(row) for row in rows]

    print_match_report(report_rows)
    output_path = output_path or get_default_report_path()
    export_match_report(report_rows, output_path)
    xlsx_output_path = export_xlsx_match_report(report_rows, output_path)

    return {
        "count": len(report_rows),
        "output_path": output_path,
        "xlsx_output_path": xlsx_output_path,
    }


def get_match_results(
    limit=None,
    db_path=DEFAULT_DB_PATH,
    allowed_location_prefixes=DEFAULT_ALLOWED_LOCATION_PREFIXES,
):
    location_filter, location_params = build_location_filter(
        "jp.location",
        allowed_location_prefixes,
    )
    user_profile_filter = """
        WHERE jmr.user_profile_id = (
            SELECT id
            FROM user_profiles
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        )
    """
    sql = """
        SELECT
            jmr.match_score,
            jmr.score,
            jmr.recommendation_level,
            jmr.matched_keywords_json,
            jmr.missing_keywords_json,
            jmr.positive_reasons_json,
            jmr.negative_reasons_json,
            jmr.reason,
            jmr.updated_at,
            jp.id AS job_posting_id,
            jp.title,
            jp.location,
            jp.career,
            jp.posted_date,
            jp.deadline,
            jp.deadline_date,
            jp.detail_url,
            c.name AS company_name
        FROM job_match_results jmr
        JOIN job_postings jp ON jp.id = jmr.job_posting_id
        LEFT JOIN companies c ON c.id = jp.company_id
        {user_profile_filter}
          AND jp.detail_status = 'success'
          AND jp.detail_collected_at IS NOT NULL
          AND (
                jp.deadline_date IS NULL
                OR jp.deadline_date = ''
                OR jp.deadline_date >= date('now', '+9 hours')
              )
          {location_filter}
        ORDER BY
            COALESCE(jmr.match_score, jmr.score, 0) DESC,
            jmr.updated_at DESC,
            jp.id DESC
    """.format(
        user_profile_filter=user_profile_filter,
        location_filter=location_filter,
    )

    params = list(location_params)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    with get_connection(db_path) as conn:
        return conn.execute(sql, params).fetchall()


def format_report_row(row):
    positive_reasons = parse_json_list(row["positive_reasons_json"])
    negative_reasons = parse_json_list(row["negative_reasons_json"])

    return {
        "score": row["match_score"] if row["match_score"] is not None else row["score"],
        "level": clean_text(row["recommendation_level"]),
        "company": clean_text(row["company_name"]),
        "job_title": clean_text(row["title"]),
        "색 이유": "",
        "job_url": clean_text(row["detail_url"]),
        "location": clean_text(row["location"]),
        "career": clean_text(row["career"]),
        "startdate": format_jobkorea_display_date(row["posted_date"]),
        "deadline": format_deadline(row["deadline"], row["deadline_date"]),
        "matched_keywords": join_list(parse_json_list(row["matched_keywords_json"])),
        "caution_keywords": join_list(parse_json_list(row["missing_keywords_json"])),
        "good_points": join_list(positive_reasons),
        "caution_points": join_list(negative_reasons),
        "updatedate": format_report_date(row["updated_at"]),
    }


def print_match_report(rows):
    if not rows:
        print("[INFO] No match results found. Run jobkorea-match first.")
        return

    print(f"[INFO] Current {len(rows)} JobKorea match results")
    for index, row in enumerate(rows, start=1):
        print("-" * 80)
        print(f"{index}. [{row['score']}] {row['level']} | {row['company']}")
        print(f"   공고명: {row['job_title']}")
        print(f"   지역/경력/마감: {row['location']} / {row['career']} / {row['deadline']}")
        print(f"   매칭 키워드: {row['matched_keywords']}")
        print(f"   주의 키워드: {row['caution_keywords']}")
        print(f"   추천 이유: {row['good_points']}")
        print(f"   주의 이유: {row['caution_points']}")
        print(f"   URL: {row['job_url']}")


def export_match_report(rows, output_path=None):
    output_path = output_path or get_default_report_path()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = get_report_fieldnames()

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[INFO] Match report exported: {path}")


def export_xlsx_match_report(rows, csv_output_path=None):
    csv_output_path = csv_output_path or get_default_report_path()
    xlsx_path = Path(csv_output_path).with_suffix(".xlsx")
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = get_report_fieldnames()
    sheet_rows = [fieldnames]
    sheet_rows.extend([[row.get(fieldname, "") for fieldname in fieldnames] for row in rows])

    with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", build_content_types_xml())
        workbook.writestr("_rels/.rels", build_root_rels_xml())
        workbook.writestr("xl/workbook.xml", build_workbook_xml())
        workbook.writestr("xl/_rels/workbook.xml.rels", build_workbook_rels_xml())
        workbook.writestr("xl/styles.xml", build_styles_xml())
        workbook.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(sheet_rows))
        workbook.writestr(
            "xl/worksheets/_rels/sheet1.xml.rels",
            build_sheet_rels_xml(sheet_rows),
        )

    print(f"[INFO] Match report xlsx exported: {xlsx_path}")
    return str(xlsx_path)


def get_report_fieldnames():
    return [
        "company",
        "job_title",
        "색 이유",
        "job_url",
        "location",
        "career",
        "startdate",
        "deadline",
        "matched_keywords",
        "caution_keywords",
        "good_points",
        "caution_points",
        "updatedate",
        "score",
        "level",
    ]


def parse_json_list(value):
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [clean_text(value)]

    if isinstance(parsed, list):
        return [clean_text(item) for item in parsed if clean_text(item)]
    if parsed:
        return [clean_text(parsed)]
    return []


def join_list(values):
    return ", ".join(values)


def format_deadline(deadline, deadline_date):
    cleaned_deadline = clean_text(deadline)
    cleaned_deadline_date = clean_text(deadline_date)
    return cleaned_deadline or cleaned_deadline_date


def format_report_date(value):
    cleaned = clean_text(value)
    if not cleaned:
        return ""

    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(cleaned[:19], date_format)
            return format_korean_month_day(parsed)
        except ValueError:
            continue

    return cleaned


def format_jobkorea_display_date(value):
    cleaned = clean_text(value)
    if not cleaned:
        return ""

    match = re.search(r"(\d{4})[.](\d{2})[.](\d{2})(?:\(([^)]+)\))?", cleaned)
    if match:
        _year, month, day, weekday = match.groups()
        if weekday:
            return f"{month}/{day}({weekday})"
        return f"{month}/{day}"

    return cleaned


def format_korean_month_day(value):
    weekdays = ("월", "화", "수", "목", "금", "토", "일")
    return f"{value.month:02d}/{value.day:02d}({weekdays[value.weekday()]})"


def clean_text(value):
    return str(value).strip() if value is not None else ""


def get_default_report_path(today=None):
    report_date = today or date.today()
    filename = DEFAULT_REPORT_NAME_TEMPLATE.format(
        date=report_date.strftime("%Y%m%d"),
    )
    return str(Path(DEFAULT_REPORT_DIR) / filename)


def build_location_filter(column_name, allowed_location_prefixes):
    prefixes = [
        clean_text(prefix)
        for prefix in allowed_location_prefixes
        if clean_text(prefix)
    ]
    if not prefixes:
        return "", []

    clauses = [f"{column_name} LIKE ?" for _ in prefixes]
    params = [f"{prefix}%" for prefix in prefixes]
    return f"AND ({' OR '.join(clauses)})", params


def build_content_types_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""


def build_root_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def build_workbook_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="JobKorea Match" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""


def build_workbook_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def build_styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font>
    <font><u/><sz val="11"/><name val="Calibri"/><color rgb="FF0563C1"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF2F5597"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def build_sheet_xml(rows):
    row_count = len(rows)
    col_count = len(rows[0]) if rows else 1
    dimension = f"A1:{column_letter(col_count)}{max(row_count, 1)}"
    auto_filter = f'<autoFilter ref="A1:{column_letter(col_count)}{max(row_count, 1)}"/>'
    hyperlinks = build_hyperlinks_xml(rows)

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"',
            '           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
            f'  <dimension ref="{dimension}"/>',
            "  <sheetViews>",
            '    <sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView>',
            "  </sheetViews>",
            build_columns_xml(rows),
            "  <sheetData>",
            *[build_row_xml(index, row) for index, row in enumerate(rows, start=1)],
            "  </sheetData>",
            f"  {auto_filter}",
            hyperlinks,
            "</worksheet>",
        ]
    )


def build_columns_xml(rows):
    if not rows:
        return "  <cols/>"

    column_widths = []
    for column_index in range(len(rows[0])):
        values = [str(row[column_index] or "") for row in rows]
        max_width = max(len(value) for value in values)
        column_widths.append(min(max(max_width + 2, 10), 60))

    columns = [
        f'    <col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths, start=1)
    ]
    return "\n".join(["  <cols>", *columns, "  </cols>"])


def build_row_xml(row_index, values):
    cells = [
        build_cell_xml(row_index, column_index, value, is_header=row_index == 1)
        for column_index, value in enumerate(values, start=1)
    ]
    return "\n".join([f'    <row r="{row_index}">', *cells, "    </row>"])


def build_cell_xml(row_index, column_index, value, is_header=False):
    cell_ref = f"{column_letter(column_index)}{row_index}"
    style = ' s="1"' if is_header else ""
    if not is_header and column_index == get_job_url_column_index():
        style = ' s="2"'

    if not is_header and column_index == 1 and is_number(value):
        return f'      <c r="{cell_ref}"{style}><v>{value}</v></c>'

    escaped_value = escape(str(value or ""))
    return f'      <c r="{cell_ref}" t="inlineStr"{style}><is><t>{escaped_value}</t></is></c>'


def column_letter(column_number):
    letters = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def build_hyperlinks_xml(rows):
    hyperlinks = []
    for rel_id, cell_ref, _url in iter_hyperlinks(rows):
        hyperlinks.append(f'    <hyperlink ref="{cell_ref}" r:id="{rel_id}"/>')

    if not hyperlinks:
        return ""

    return "\n".join(["  <hyperlinks>", *hyperlinks, "  </hyperlinks>"])


def build_sheet_rels_xml(rows):
    relationships = []
    for rel_id, _cell_ref, url in iter_hyperlinks(rows):
        relationships.append(
            '  <Relationship '
            f'Id="{rel_id}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            f'Target="{escape_xml_attribute(url)}" '
            'TargetMode="External"/>'
        )

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            *relationships,
            "</Relationships>",
        ]
    )


def iter_hyperlinks(rows):
    url_column_index = get_job_url_column_index()
    for row_index, row in enumerate(rows[1:], start=2):
        if len(row) < url_column_index:
            continue
        url = clean_text(row[url_column_index - 1])
        if not url:
            continue
        cell_ref = f"{column_letter(url_column_index)}{row_index}"
        yield f"rId{row_index - 1}", cell_ref, url


def get_job_url_column_index():
    return get_report_fieldnames().index("job_url") + 1


def escape_xml_attribute(value):
    return escape(str(value), {'"': "&quot;"})
