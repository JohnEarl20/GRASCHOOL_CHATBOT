"""Analytics layer: the chat log the staff dashboard reads.

Every turn is one JSON line in data/chat_log.jsonl. Nothing personal is
written: no name, no id number, no contact details - the assistant never asks
for them (proposal section 14). The log holds the question, the intent, the
confidence, whether it was answered, the rules that fired and the feedback.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "chat_log.jsonl"


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
