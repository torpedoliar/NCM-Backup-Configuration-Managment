from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app_v4.core.utcdatetime import utc_now


@dataclass(frozen=True)
class BackupReportRow:
    id: int
    switch_name: str
    taken_at: datetime
    backup_type: str
    success: bool
    size_bytes: int
    message: str


@dataclass(frozen=True)
class ComplianceRow:
    """One switch's config-management status (ISO 27001 A.8.9 evidence)."""

    switch: str
    ip: str
    model: str
    baseline: str  # "yes" | "no" | "stale"
    last_backup: str
    open_reviews: int
    last_review: str
    review_state: str  # pending | approved | flagged | dismissed | ""
    next_review: str = ""  # YYYY-MM-DD when the reminder-review cycle comes due


HEADERS = ["ID", "Switch", "Taken at", "Type", "Status", "Size (KB)", "Message"]
COMPLIANCE_HEADERS = ["Switch", "IP", "Model", "Baseline", "Last backup", "Open reviews", "Last review", "Review state", "Next review"]


def _row_values(row: BackupReportRow) -> list[str]:
    return [
        str(row.id),
        row.switch_name,
        row.taken_at.strftime("%Y-%m-%d %H:%M:%S"),
        row.backup_type,
        "ok" if row.success else "failed",
        f"{round((row.size_bytes or 0) / 1024, 1)}",
        (row.message or "").replace("\n", " ").strip(),
    ]


def render_csv(rows: list[BackupReportRow]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADERS)
    for row in rows:
        writer.writerow(_row_values(row))
    return buf.getvalue().encode("utf-8-sig")


def render_xlsx(rows: list[BackupReportRow], title: str = "Backup report") -> bytes:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Backups"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(_row_values(row))
    sheet.freeze_panes = "A2"
    for column in range(1, len(HEADERS) + 1):
        sheet.column_dimensions[chr(64 + column)].width = 22
    sheet.column_dimensions["G"].width = 60
    output = BytesIO()
    wb.properties.title = title
    wb.save(output)
    return output.getvalue()


def render_pdf(rows: list[BackupReportRow], title: str = "Backup report") -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        title=title,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(title, styles["Title"]),
        Paragraph(
            f"Generated {utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC · {len(rows)} rows",
            styles["BodyText"],
        ),
        Spacer(1, 12),
    ]
    data = [HEADERS] + [_row_values(row) for row in rows]
    table = Table(data, repeatRows=1, colWidths=[40, 110, 120, 60, 50, 60, 260])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222222")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return output.getvalue()


# ----- config-management compliance report (ISO 27001 A.8.9) -----


def _compliance_values(row: ComplianceRow) -> list[str]:
    return [
        row.switch,
        row.ip,
        row.model or "",
        row.baseline,
        row.last_backup,
        str(row.open_reviews),
        row.last_review,
        row.review_state,
        row.next_review,
    ]


def render_compliance_csv(rows: list[ComplianceRow]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COMPLIANCE_HEADERS)
    for row in rows:
        writer.writerow(_compliance_values(row))
    return buf.getvalue().encode("utf-8-sig")


def render_compliance_xlsx(rows: list[ComplianceRow], title: str = "Config compliance report") -> bytes:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Compliance"
    sheet.append(COMPLIANCE_HEADERS)
    for row in rows:
        sheet.append(_compliance_values(row))
    sheet.freeze_panes = "A2"
    for column in range(1, len(COMPLIANCE_HEADERS) + 1):
        sheet.column_dimensions[chr(64 + column)].width = 20
    output = BytesIO()
    wb.properties.title = title
    wb.save(output)
    return output.getvalue()


def render_compliance_pdf(rows: list[ComplianceRow], title: str = "Config compliance report") -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        title=title,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(title, styles["Title"]),
        Paragraph(
            f"Generated {utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC · {len(rows)} switch(es)",
            styles["BodyText"],
        ),
        Spacer(1, 12),
    ]
    data = [COMPLIANCE_HEADERS] + [_compliance_values(row) for row in rows]
    table = Table(data, repeatRows=1, colWidths=[90, 70, 90, 60, 90, 60, 90, 90])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222222")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return output.getvalue()
