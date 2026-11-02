"""Staff-only analytics report file storage and PDF export helpers."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "data" / "staff_reports"
HISTORY_PATH = REPORT_DIR / "history.json"


def _safe_pdf_text(value: str) -> str:
    text = str(value).encode("latin-1", errors="replace").decode("latin-1")
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def make_pdf(
    title: str,
    lines: list[str],
    category_counts: list[tuple[str, int]] | None = None,
) -> bytes:
    """Create a small, dependency-free, multipage text report PDF."""
    content_lines = [title, f"Generated {datetime.now().astimezone().isoformat(timespec='minutes')}", ""]
    content_lines.extend(lines)
    pages = [
        (content_lines[index:index + 54], False)
        for index in range(0, len(content_lines), 54)
    ] or [([], False)]
    if category_counts:
        pages.append((["Inquiry category distribution"], True))

    objects: list[bytes] = []
    page_ids = [4 + index * 2 for index in range(len(pages))]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, (page_lines, has_chart) in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        commands = ["BT", "/F1 9 Tf", "40 800 Td", "12 TL"]
        for line in page_lines:
            commands.append(f"({_safe_pdf_text(line[:180])}) Tj")
            commands.append("T*")
        if has_chart and category_counts:
            maximum = max(count for _, count in category_counts) or 1
            for chart_index, (category, count) in enumerate(category_counts[:12]):
                y_position = 690 - chart_index * 38
                bar_width = round(300 * count / maximum)
                commands.extend([
                    f"0.03 0.62 0.92 rg 40 {y_position} {bar_width} 14 re f",
                    f"0 0 0 rg 1 0 0 1 355 {y_position + 2} Tm "
                    f"({_safe_pdf_text(category[:32])}: {count}) Tj",
                ])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
            + stream + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read report history: {error}") from error
    if not isinstance(history, list):
        raise ValueError("Report history file must contain a list.")
    return history


def save_report(
    name: str,
    report_type: str,
    generated_by: str,
    files: dict[str, bytes],
) -> dict:
    if not files or any(fmt not in {"csv", "xlsx", "pdf"} for fmt in files):
        raise ValueError("A report must include at least one supported export format.")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_id = uuid.uuid4().hex
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:48] or "report"
    stored_files: dict[str, str] = {}
    for file_format, content in files.items():
        filename = f"{report_id}-{slug}.{file_format}"
        (REPORT_DIR / filename).write_bytes(content)
        stored_files[file_format] = filename
    record = {
        "id": report_id,
        "name": name,
        "type": report_type,
        "generated_by": generated_by,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "files": stored_files,
    }
    history = load_history()
    history.insert(0, record)
    HISTORY_PATH.write_text(json.dumps(history[:100], indent=2), encoding="utf-8")
    return record


def read_report_file(filename: str) -> bytes:
    if not re.fullmatch(r"[a-f0-9]{32}-[a-z0-9-]{1,48}\.(csv|xlsx|pdf)", filename):
        raise ValueError("Invalid report file name.")
    path = REPORT_DIR / filename
    if not path.is_file():
        raise FileNotFoundError("The saved report file is no longer available.")
    return path.read_bytes()
