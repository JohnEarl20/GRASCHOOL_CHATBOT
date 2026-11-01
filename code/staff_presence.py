"""Staff presence tracking for real-time chat routing.

Tracks which staff members are online/offline to determine
whether to route student messages to staff or AI.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PRESENCE_FILE = ROOT / "data" / "staff_presence.json"

# Staff is considered online if they've sent a heartbeat within this many seconds
STAFF_ONLINE_THRESHOLD = 30  # seconds


def _ensure_file() -> None:
    PRESENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PRESENCE_FILE.exists():
        PRESENCE_FILE.write_text("{}", encoding="utf-8")


def _load_presence() -> dict:
    _ensure_file()
    try:
        return json.loads(PRESENCE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_presence(data: dict) -> None:
    _ensure_file()
    PRESENCE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def staff_heartbeat(staff_id: str, staff_name: str | None = None) -> None:
    """Record a heartbeat for a staff member (call periodically from staff dashboard)."""
    data = _load_presence()
    now = time.time()
    data[staff_id] = {
        "staff_id": staff_id,
        "staff_name": staff_name or staff_id,
        "last_heartbeat": now,
        "last_seen": datetime.now().isoformat(timespec="seconds"),
    }
    _save_presence(data)


def is_staff_online(staff_id: str) -> bool:
    """Check if a specific staff member is online."""
    data = _load_presence()
    if staff_id not in data:
        return False
    last_heartbeat = data[staff_id].get("last_heartbeat", 0)
    return (time.time() - last_heartbeat) < STAFF_ONLINE_THRESHOLD


def get_online_staff() -> list[dict]:
    """Get list of currently online staff members."""
    data = _load_presence()
    now = time.time()
    online = []
    for staff_id, info in data.items():
        if (now - info.get("last_heartbeat", 0)) < STAFF_ONLINE_THRESHOLD:
            online.append({
                "staff_id": staff_id,
                "staff_name": info.get("staff_name", staff_id),
                "last_seen": info.get("last_seen", ""),
            })
    return online


def any_staff_online() -> bool:
    """Check if any staff member is currently online."""
    return len(get_online_staff()) > 0


def get_staff_status(staff_id: str) -> dict:
    """Get detailed status for a staff member."""
    data = _load_presence()
    if staff_id not in data:
        return {"staff_id": staff_id, "online": False, "last_seen": None}
    
    info = data[staff_id]
    last_heartbeat = info.get("last_heartbeat", 0)
    online = (time.time() - last_heartbeat) < STAFF_ONLINE_THRESHOLD
    return {
        "staff_id": staff_id,
        "staff_name": info.get("staff_name", staff_id),
        "online": online,
        "last_seen": info.get("last_seen"),
        "seconds_ago": int(time.time() - last_heartbeat) if last_heartbeat else None,
    }


def cleanup_stale_presence() -> None:
    """Remove staff entries that haven't sent heartbeat in a long time (optional cleanup)."""
    data = _load_presence()
    now = time.time()
    # Remove entries older than 1 hour
    cutoff = now - 3600
    cleaned = {k: v for k, v in data.items() if v.get("last_heartbeat", 0) > cutoff}
    if len(cleaned) != len(data):
        _save_presence(cleaned)