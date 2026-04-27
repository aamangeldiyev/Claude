import csv
import sys
from datetime import datetime
from pathlib import Path


def generate_report(results: list[dict], output_path: str) -> None:
    """Generate Excel report; fall back to CSV if openpyxl is unavailable."""
    out = Path(output_path)

    try:
        import openpyxl  # noqa: F401
        _write_excel(results, out)
    except ImportError:
        csv_path = out.with_suffix(".csv")
        print(f"[WARN] openpyxl not found, writing CSV to {csv_path}", file=sys.stderr)
        _write_csv(results, csv_path)


# ──────────────────────────── Excel ────────────────────────────

def _write_excel(results: list[dict], out: Path) -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()

    # ── Sheet 1: detail rows ──
    ws = wb.active
    ws.title = "Найденные штампы"

    HEADERS = [
        "Файл", "Папка", "Тип файла", "Страница", "Стр. всего",
        "Название штампа", "Метод", "Уверенность, %", "Область (x1,y1,x2,y2)",
    ]
    WIDTHS = [42, 60, 10, 10, 10, 30, 12, 18, 28]

    hdr_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    hdr_font = Font(color="FFFFFF", bold=True, size=10)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col, (hdr, width) in enumerate(zip(HEADERS, WIDTHS), 1):
        cell = ws.cell(row=1, column=col, value=hdr)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = center
        ws.column_dimensions[cell.column_letter].width = width

    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30

    alt_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    row_idx = 2

    for result in results:
        for det in result["detections"]:
            is_alt = (row_idx % 2 == 0)
            fill = alt_fill if is_alt else None

            values = [
                result["file_name"],
                result["folder"],
                result["file_type"],
                result["page"],
                result.get("total_pages", 1),
                det["template_name"],
                det.get("method", "—"),
                round(det["confidence"] * 100, 1),
                "{},{},{},{}".format(*det["bbox"]),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)
                if fill:
                    cell.fill = fill
                cell.alignment = Alignment(vertical="center")

            row_idx += 1

    # ── Sheet 2: summary ──
    ws2 = wb.create_sheet("Сводка")
    ws2.column_dimensions["A"].width = 45
    ws2.column_dimensions["B"].width = 20

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    unique_files = len({r["file"] for r in results})
    total_hits = sum(len(r["detections"]) for r in results)

    title_font = Font(bold=True, size=13)
    ws2["A1"] = "Отчёт о поиске штампов"
    ws2["A1"].font = title_font

    for row, (label, value) in enumerate([
        ("Дата формирования:", now),
        ("Файлов со штампами:", unique_files),
        ("Всего вхождений:", total_hits),
    ], start=3):
        ws2.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws2.cell(row=row, column=2, value=value)

    # Template breakdown
    ws2.cell(row=7, column=1, value="По шаблонам:").font = Font(bold=True)
    counts: dict[str, int] = {}
    for r in results:
        for d in r["detections"]:
            counts[d["template_name"]] = counts.get(d["template_name"], 0) + 1
    for i, (name, cnt) in enumerate(sorted(counts.items()), start=8):
        ws2.cell(row=i, column=1, value=name)
        ws2.cell(row=i, column=2, value=cnt)

    wb.save(out)
    print(f"Report saved: {out}")


# ──────────────────────────── CSV fallback ────────────────────────────

def _write_csv(results: list[dict], out: Path) -> None:
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "Файл", "Папка", "Тип файла", "Страница", "Стр. всего",
            "Название штампа", "Метод", "Уверенность", "Область (x1,y1,x2,y2)",
        ])
        for r in results:
            for d in r["detections"]:
                writer.writerow([
                    r["file_name"],
                    r["folder"],
                    r["file_type"],
                    r["page"],
                    r.get("total_pages", 1),
                    d["template_name"],
                    d.get("method", "—"),
                    f"{d['confidence']:.1%}",
                    "{},{},{},{}".format(*d["bbox"]),
                ])
    print(f"Report saved: {out}")
