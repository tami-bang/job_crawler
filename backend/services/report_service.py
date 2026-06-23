import os
import smtplib
import zipfile
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from io import BytesIO
from typing import Iterable

from crawler.report import (
    build_content_types_xml,
    build_root_rels_xml,
    build_styles_xml,
    build_workbook_rels_xml,
    build_workbook_xml,
)
from xml.sax.saxutils import escape


REPORT_HEADERS = [
    "score",
    "company",
    "job_title",
    "location",
    "career",
    "employment_type",
    "deadline",
    "matched_keywords",
    "reason",
    "job_url",
]

REPORT_HEADER_LABELS = [
    "매칭 점수",
    "회사",
    "공고명",
    "지역",
    "경력",
    "고용형태",
    "마감일",
    "매칭 키워드",
    "추천 이유",
    "공고 URL",
]


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    use_tls: bool


class ReportMailConfigError(RuntimeError):
    pass


def validate_email_address(address: str) -> str:
    parsed_name, parsed_address = parseaddr(address.strip())
    if parsed_name or "@" not in parsed_address or parsed_address.count("@") != 1:
        raise ValueError("이메일 주소 형식이 올바르지 않습니다.")
    return parsed_address


def build_jobs_xlsx(rows: Iterable[dict]) -> bytes:
    sheet_rows = [REPORT_HEADER_LABELS]
    for row in rows:
        sheet_rows.append([row.get(field, "") for field in REPORT_HEADERS])

    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", build_content_types_xml())
        workbook.writestr("_rels/.rels", build_root_rels_xml())
        workbook.writestr("xl/workbook.xml", build_workbook_xml())
        workbook.writestr("xl/_rels/workbook.xml.rels", build_workbook_rels_xml())
        workbook.writestr("xl/styles.xml", build_styles_xml())
        workbook.writestr("xl/worksheets/sheet1.xml", build_report_sheet_xml(sheet_rows))
    return output.getvalue()


def build_report_sheet_xml(rows: list[list[object]]) -> str:
    col_count = len(rows[0]) if rows else 1
    row_count = max(len(rows), 1)
    dimension = f"A1:{column_letter(col_count)}{row_count}"
    row_xml = "\n".join(
        build_report_row_xml(index, row)
        for index, row in enumerate(rows, start=1)
    )
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
            f'  <dimension ref="{dimension}"/>',
            "  <sheetViews>",
            '    <sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView>',
            "  </sheetViews>",
            build_report_columns_xml(rows),
            "  <sheetData>",
            row_xml,
            "  </sheetData>",
            f'  <autoFilter ref="A1:{column_letter(col_count)}{row_count}"/>',
            "</worksheet>",
        ]
    )


def build_report_columns_xml(rows: list[list[object]]) -> str:
    widths = []
    for column_index in range(len(rows[0])):
        max_width = max(len(str(row[column_index] or "")) for row in rows)
        widths.append(min(max(max_width + 2, 10), 60))
    columns = [
        f'    <col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    ]
    return "\n".join(["  <cols>", *columns, "  </cols>"])


def build_report_row_xml(row_index: int, values: list[object]) -> str:
    cells = [
        build_report_cell_xml(row_index, column_index, value, is_header=row_index == 1)
        for column_index, value in enumerate(values, start=1)
    ]
    return "\n".join([f'    <row r="{row_index}">', *cells, "    </row>"])


def build_report_cell_xml(row_index: int, column_index: int, value: object, is_header: bool = False) -> str:
    cell_ref = f"{column_letter(column_index)}{row_index}"
    style = ' s="1"' if is_header else ""
    if not is_header and column_index == 1 and isinstance(value, (int, float)):
        return f'      <c r="{cell_ref}"{style}><v>{value}</v></c>'
    return f'      <c r="{cell_ref}" t="inlineStr"{style}><is><t>{escape(str(value or ""))}</t></is></c>'


def column_letter(column_number: int) -> str:
    letters = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def send_report_email(recipient: str, jobs: list[dict]) -> None:
    config = get_smtp_config()
    recipient_address = validate_email_address(recipient)
    workbook = build_jobs_xlsx(jobs)

    message = EmailMessage()
    message["Subject"] = "JobRadar 공고 분석 결과"
    message["From"] = config.sender
    message["To"] = recipient_address
    message.set_content(
        "JobRadar 공고 분석 결과를 엑셀 파일로 첨부했습니다.\n\n"
        "포트폴리오 데모에서 생성된 리포트입니다."
    )
    message.add_attachment(
        workbook,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="jobradar_report.xlsx",
    )

    with smtplib.SMTP(config.host, config.port, timeout=15) as smtp:
        if config.use_tls:
            smtp.starttls()
        smtp.login(config.user, config.password)
        smtp.send_message(message)


def get_smtp_config() -> SmtpConfig:
    missing = [
        key for key in (
            "JOB_RADAR_SMTP_HOST",
            "JOB_RADAR_SMTP_USER",
            "JOB_RADAR_SMTP_PASSWORD",
        )
        if not os.getenv(key)
    ]
    if missing:
        raise ReportMailConfigError(
            "SMTP 설정이 없어 이메일을 보낼 수 없습니다: " + ", ".join(missing)
        )

    sender = os.getenv("JOB_RADAR_SMTP_FROM") or os.getenv("JOB_RADAR_SMTP_USER", "")
    return SmtpConfig(
        host=os.environ["JOB_RADAR_SMTP_HOST"],
        port=int(os.getenv("JOB_RADAR_SMTP_PORT", "587")),
        user=os.environ["JOB_RADAR_SMTP_USER"],
        password=os.environ["JOB_RADAR_SMTP_PASSWORD"],
        sender=sender,
        use_tls=os.getenv("JOB_RADAR_SMTP_TLS", "true").lower() != "false",
    )
