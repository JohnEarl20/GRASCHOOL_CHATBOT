"""Analytics layer: the chat log the staff dashboard reads.

Every turn is one JSON line in data/chat_log.jsonl. Nothing personal is
written: no name, no id number, no contact details - the assistant never asks
for them (proposal section 14). The log holds the question, the intent, the
confidence, whether it was answered, the rules that fired and the feedback.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "chat_log.jsonl"
DELETED_SESSIONS_DIR = ROOT / "data" / "deleted_conversations"


def deleted_session_ids() -> set[str]:
    """Return conversation IDs that must stay hidden from Question Review."""
    if not DELETED_SESSIONS_DIR.exists():
        return set()
    return {
        path.stem
        for path in DELETED_SESSIONS_DIR.glob("*.deleted")
        if path.is_file()
    }


def mark_session_deleted(session_id: str) -> None:
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{12}", session_id):
        raise ValueError("Invalid conversation ID.")
    DELETED_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    (DELETED_SESSIONS_DIR / f"{session_id}.deleted").touch(exist_ok=True)


def clear_session_deleted(session_id: str) -> None:
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{12}", session_id):
        raise ValueError("Invalid conversation ID.")
    marker = DELETED_SESSIONS_DIR / f"{session_id}.deleted"
    marker.unlink(missing_ok=True)


def log_turn(record: dict) -> None:
    """Append one turn. Never raises into the chat path: a failed write must
    not kill a conversation that already produced a good answer."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now().isoformat(timespec="seconds"), **record}
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_logs() -> list[dict]:
    """Every logged turn, oldest first. A corrupt line is skipped, not fatal."""
    if not LOG_PATH.exists():
        return []
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def clear_logs() -> None:
    if LOG_PATH.exists():
        LOG_PATH.unlink()


def delete_session_logs(session_id: str) -> int:
    """Remove inquiry-log records for one conversation without changing other rows."""
    if not session_id:
        raise ValueError("A conversation ID is required.")
    if not LOG_PATH.exists():
        return 0

    kept_lines = []
    removed = 0
    for line in LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            kept_lines.append(line)
            continue
        if isinstance(row, dict) and row.get("session_id") == session_id:
            removed += 1
        else:
            kept_lines.append(line)

    temporary_path = LOG_PATH.with_name(f"{LOG_PATH.name}.tmp")
    try:
        temporary_path.write_text("".join(kept_lines), encoding="utf-8")
        os.replace(temporary_path, LOG_PATH)
    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return removed
