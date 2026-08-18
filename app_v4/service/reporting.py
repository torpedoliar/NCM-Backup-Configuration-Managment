from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO


@dataclass(frozen=True)
class BackupReportRow:
    id: int
    switch_name: str
    taken_at: datetime
    backup_type: str
    success: bool
    size_bytes: int
    message: str


HEADERS = ["ID", "Switch", "Taken at", "Type", "Status", "Size (KB)", "Message"]


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
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADERS)
    for row in rows:
        writer.writerow(_row_values(row))
    return buf.getvalue().encode("utf-8-sig")


def render_xlsx(rows: list[BackupReportRow], title: str = "Backup report") -> bytes:
    from openpyxl import Workbook

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
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

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
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC · {len(rows)} rows",
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
