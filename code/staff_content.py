"""Staff-authored content stored alongside the app's existing local data."""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from code import auth

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTICLES_PATH = DATA_DIR / "knowledge_articles.json"
ANNOUNCEMENTS_PATH = DATA_DIR / "staff_announcements.json"
DOCUMENTS_PATH = DATA_DIR / "staff_documents.json"
DOCUMENT_DIR = DATA_DIR / "staff_documents"
MAX_DOCUMENT_BYTES = 1024 * 1024 * 1024
_DOCUMENT_STORAGE_NAME = re.compile(r"[a-f0-9]{32}(\..+)?")
ARTICLE_CATEGORIES = (
    "Enrollment",
    "Tuition and Fees",
    "Academic Calendar",
    "Requirements",
    "Student Services",
    "Other",
)


def _read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise ValueError(f"Invalid staff content format in {path.name}")
    return records


def _write_records(path: Path, records: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_articles() -> list[dict[str, Any]]:
    return _read_records(ARTICLES_PATH)


def save_article(
    title: str,
    content: str,
    category: str,
    source: str,
    staff_id: str,
    article_id: str | None = None,
) -> dict[str, Any]:
    title = title.strip()
    content = content.strip()
    source = source.strip()
    if not title or len(title) > 160:
        raise ValueError("Article title is required and must be 160 characters or fewer.")
    if not content or len(content) > 12000:
        raise ValueError("Article content is required and must be 12,000 characters or fewer.")
    if category not in ARTICLE_CATEGORIES:
        raise ValueError("Choose a valid knowledge category.")
    if not source or len(source) > 500:
        raise ValueError("Provide the school source used to verify this article.")

    records = load_articles()
    now = datetime.now().isoformat(timespec="seconds")
    record = next((row for row in records if row.get("id") == article_id), None)
    if article_id and record is None:
        raise ValueError("Knowledge article no longer exists.")
    if record is None:
        record = {"id": uuid.uuid4().hex, "created_at": now, "status": "draft"}
        records.append(record)
    record.update(
        title=title,
        content=content,
        category=category,
        source=source,
        status="draft",
        updated_at=now,
        updated_by=staff_id,
    )
    _write_records(ARTICLES_PATH, records)
    return record


def set_article_status(article_id: str, status: str, staff_id: str) -> dict[str, Any]:
    if status not in {"draft", "approved", "archived"}:
        raise ValueError("Invalid knowledge article status.")
    records = load_articles()
    record = next((row for row in records if row.get("id") == article_id), None)
    if record is None:
        raise ValueError("Knowledge article no longer exists.")
    record.update(status=status, updated_at=datetime.now().isoformat(timespec="seconds"), updated_by=staff_id)
    _write_records(ARTICLES_PATH, records)
    return record


def load_announcements() -> list[dict[str, Any]]:
    return _read_records(ANNOUNCEMENTS_PATH)


def save_announcement(
    title: str,
    body: str,
    staff_id: str,
    publish_on: date | None = None,
    announcement_id: str | None = None,
) -> dict[str, Any]:
    title = title.strip()
    body = body.strip()
    if not title or len(title) > 160:
        raise ValueError("Announcement title is required and must be 160 characters or fewer.")
    if not body or len(body) > 12000:
        raise ValueError("Announcement content is required and must be 12,000 characters or fewer.")

    now = datetime.now().isoformat(timespec="seconds")
    status = "scheduled" if publish_on and publish_on > date.today() else "published"
    records = load_announcements()
    record = next((row for row in records if row.get("id") == announcement_id), None)
    if announcement_id and record is None:
        raise ValueError("Announcement no longer exists.")
    if record is None:
        record = {"id": uuid.uuid4().hex, "created_at": now}
        records.append(record)
    record.update(
        title=title,
        body=body,
        status=status,
        publish_on=publish_on.isoformat() if publish_on else date.today().isoformat(),
        updated_at=now,
        updated_by=staff_id,
    )
    _write_records(ANNOUNCEMENTS_PATH, records)
    return record


def set_announcement_status(announcement_id: str, status: str, staff_id: str) -> dict[str, Any]:
    if status not in {"published", "archived"}:
        raise ValueError("Invalid announcement status.")
    records = load_announcements()
    record = next((row for row in records if row.get("id") == announcement_id), None)
    if record is None:
        raise ValueError("Announcement no longer exists.")
    record.update(status=status, updated_at=datetime.now().isoformat(timespec="seconds"), updated_by=staff_id)
    _write_records(ANNOUNCEMENTS_PATH, records)
    return record


def load_documents() -> list[dict[str, Any]]:
    return _read_records(DOCUMENTS_PATH)


def _normalize_student_ids(student_ids: list[str] | None) -> list[str]:
    if student_ids is None:
        return []
    if not isinstance(student_ids, list) or any(
        not isinstance(student_id, str)
        or not student_id.strip()
        or len(student_id.strip()) > 64
        for student_id in student_ids
    ):
        raise ValueError("Choose valid student accounts to share this document with.")
    return list(dict.fromkeys(student_id.strip() for student_id in student_ids))


def documents_for_student(student_id: str) -> list[dict[str, Any]]:
    if not isinstance(student_id, str) or not student_id.strip():
        return []
    normalized_id = student_id.strip().casefold()
    visible = []
    for row in load_documents():
        shared_with = row.get("shared_with", [])
        if isinstance(shared_with, list) and any(
            isinstance(shared_id, str)
            and shared_id.strip().casefold() == normalized_id
            for shared_id in shared_with
        ):
            visible.append(row)
    return visible


def _validate_document_content(content: bytes) -> None:
    if not content:
        raise ValueError("The selected document is empty. Choose a file containing data.")
    if len(content) > MAX_DOCUMENT_BYTES:
        size_mb = len(content) / (1024 * 1024)
        limit_mb = MAX_DOCUMENT_BYTES // (1024 * 1024)
        raise ValueError(
            f"Document is {size_mb:.1f} MB; the maximum allowed size is {limit_mb} MB."
        )


def save_document(
    filename: str,
    content: bytes,
    category: str,
    staff_id: str,
    shared_with: list[str] | None = None,
) -> dict[str, Any]:
    original_name = Path(filename).name
    extension = Path(original_name).suffix.lower()
    _validate_document_content(content)
    category = category.strip() or "General"
    if len(category) > 80:
        raise ValueError("Document category must be 80 characters or fewer.")

    document_id = uuid.uuid4().hex
    stored_name = f"{document_id}{extension}"
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    (DOCUMENT_DIR / stored_name).write_bytes(content)
    record = {
        "id": document_id,
        "filename": original_name,
        "stored_name": stored_name,
        "category": category,
        "size": len(content),
        "uploaded_by": staff_id,
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "shared_with": _normalize_student_ids(shared_with),
    }
    records = load_documents()
    records.append(record)
    _write_records(DOCUMENTS_PATH, records)
    return record


def replace_document(
    document_id: str,
    filename: str,
    content: bytes,
    category: str,
    staff_id: str,
    shared_with: list[str] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", document_id):
        raise ValueError("Invalid document reference.")
    original_name = Path(filename).name
    extension = Path(original_name).suffix.lower()
    _validate_document_content(content)
    category = category.strip() or "General"
    if len(category) > 80:
        raise ValueError("Document category must be 80 characters or fewer.")

    records = load_documents()
    record = next((row for row in records if row.get("id") == document_id), None)
    if record is None:
        raise ValueError("Document no longer exists.")
    old_name = record.get("stored_name", "")
    if not _DOCUMENT_STORAGE_NAME.fullmatch(old_name):
        raise ValueError("Invalid document storage reference.")
    stored_name = f"{uuid.uuid4().hex}{extension}"
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    (DOCUMENT_DIR / stored_name).write_bytes(content)
    record.update(
        filename=original_name,
        stored_name=stored_name,
        category=category,
        size=len(content),
        uploaded_by=staff_id,
        uploaded_at=datetime.now().isoformat(timespec="seconds"),
    )
    if shared_with is not None:
        record["shared_with"] = _normalize_student_ids(shared_with)
    _write_records(DOCUMENTS_PATH, records)
    old_path = DOCUMENT_DIR / old_name
    if old_path.is_file():
        old_path.unlink()
    return record


def read_document(document_id: str) -> tuple[dict[str, Any], bytes]:
    if not re.fullmatch(r"[a-f0-9]{32}", document_id):
        raise ValueError("Invalid document reference.")
    record = next((row for row in load_documents() if row.get("id") == document_id), None)
    if record is None:
        raise ValueError("Document no longer exists.")
    stored_name = record.get("stored_name", "")
    if not _DOCUMENT_STORAGE_NAME.fullmatch(stored_name):
        raise ValueError("Invalid document storage reference.")
    path = DOCUMENT_DIR / stored_name
    if not path.is_file():
        raise FileNotFoundError(f"Stored document is missing: {record.get('filename', document_id)}")
    return record, path.read_bytes()


def read_document_for_student(
    document_id: str,
    student_id: str,
) -> tuple[dict[str, Any], bytes]:
    current_student_id = auth.get_current_user_id()
    if (
        not auth.is_student()
        or not isinstance(student_id, str)
        or not student_id.strip()
        or not isinstance(current_student_id, str)
        or current_student_id.strip().casefold() != student_id.strip().casefold()
    ):
        raise PermissionError("A student account is required to access shared documents.")
    allowed_ids = {
        row.get("id")
        for row in documents_for_student(student_id)
    }
    if document_id not in allowed_ids:
        raise PermissionError("This document has not been shared with your account.")
    return read_document(document_id)


def remove_shared_document_for_student(document_id: str, student_id: str) -> bool:
    current_student_id = auth.get_current_user_id()
    if (
        not auth.is_student()
        or not isinstance(student_id, str)
        or not student_id.strip()
        or not isinstance(current_student_id, str)
        or current_student_id.strip().casefold() != student_id.strip().casefold()
    ):
        raise PermissionError("Students can only remove documents shared with their own account.")
    if not re.fullmatch(r"[a-f0-9]{32}", document_id):
        raise ValueError("Invalid document reference.")

    records = load_documents()
    record = next((row for row in records if row.get("id") == document_id), None)
    if record is None:
        return False
    shared_with = record.get("shared_with", [])
    if not isinstance(shared_with, list):
        raise ValueError("Invalid document sharing record.")
    normalized_id = student_id.strip().casefold()
    updated_shared_with = [
        shared_id
        for shared_id in shared_with
        if not isinstance(shared_id, str)
        or shared_id.strip().casefold() != normalized_id
    ]
    if len(updated_shared_with) == len(shared_with):
        return False
    record["shared_with"] = updated_shared_with
    _write_records(DOCUMENTS_PATH, records)
    return True


def delete_document(document_id: str) -> bool:
    if not auth.is_staff():
        raise PermissionError("Only staff accounts can delete managed documents.")
    if not re.fullmatch(r"[a-f0-9]{32}", document_id):
        raise ValueError("Invalid document reference.")

    records = load_documents()
    record = next((row for row in records if row.get("id") == document_id), None)
    if record is None:
        return False
    stored_name = record.get("stored_name", "")
    if not _DOCUMENT_STORAGE_NAME.fullmatch(stored_name):
        raise ValueError("Invalid document storage reference.")

    _write_records(
        DOCUMENTS_PATH,
        [row for row in records if row.get("id") != document_id],
    )
    stored_path = DOCUMENT_DIR / stored_name
    if stored_path.is_file():
        stored_path.unlink()
    return True
