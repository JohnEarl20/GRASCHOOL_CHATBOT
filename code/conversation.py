"""Conversation storage for real-time student-staff chat.

Each conversation is a JSON file in data/conversations/ with the session_id as filename.
Students see their own conversation; staff see all conversations and can reply.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from code import staff_presence

ROOT = Path(__file__).resolve().parent.parent
CONV_DIR = ROOT / "data" / "conversations"


def _ensure_dir() -> None:
    CONV_DIR.mkdir(parents=True, exist_ok=True)


def _conv_path(session_id: str) -> Path:
    return CONV_DIR / f"{session_id}.json"


def _load_conversation(session_id: str) -> dict | None:
    """Load a conversation by session_id."""
    path = _conv_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_conversation(conv: dict) -> None:
    """Save a conversation atomically."""
    _ensure_dir()
    path = _conv_path(conv["session_id"])
    # Use a simpler approach for Windows compatibility
    try:
        path.write_text(json.dumps(conv, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # Fallback: try with temp file
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(conv, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp.replace(path)
        except OSError:
            # Last resort: remove and rewrite
            if path.exists():
                path.unlink()
            tmp.rename(path)


def create_conversation(student_id: str, student_name: str | None = None) -> dict:
    """Create a new conversation for a student."""
    session_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat(timespec="seconds")
    conv = {
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student_name or student_id,
        "status": "active",  # active, waiting, closed
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "assigned_staff": None,
    }
    _save_conversation(conv)
    return conv


def get_conversation(session_id: str) -> dict | None:
    """Get a conversation by session_id."""
    return _load_conversation(session_id)


def get_student_conversation(student_id: str) -> dict | None:
    """Get the active conversation for a student."""
    _ensure_dir()
    for path in CONV_DIR.glob("*.json"):
        try:
            conv = json.loads(path.read_text(encoding="utf-8"))
            if conv.get("student_id") == student_id and conv.get("status") == "active":
                return conv
        except (json.JSONDecodeError, OSError):
            continue
    return None


def get_all_conversations() -> list[dict]:
    """Get all conversations for staff dashboard."""
    _ensure_dir()
    conversations = []
    for path in CONV_DIR.glob("*.json"):
        try:
            conv = json.loads(path.read_text(encoding="utf-8"))
            conversations.append(conv)
        except (json.JSONDecodeError, OSError):
            continue
    # Sort by updated_at descending (newest first)
    conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    return conversations


def add_message(session_id: str, role: str, text: str, sender_id: str | None = None, sender_name: str | None = None, meta: dict | None = None) -> dict | None:
    """Add a message to a conversation."""
    conv = _load_conversation(session_id)
    if not conv:
        return None

    now = datetime.now().isoformat(timespec="seconds")
    msg = {
        "id": uuid.uuid4().hex[:8],
        "role": role,  # "student", "assistant", "staff"
        "text": text,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "timestamp": now,
        "meta": meta or {},
    }
    conv["messages"].append(msg)
    conv["updated_at"] = now

    # Update status based on role
    if role == "student" and conv["status"] == "closed":
        conv["status"] = "active"
    elif role == "staff":
        conv["status"] = "active"
        conv["assigned_staff"] = sender_id

    _save_conversation(conv)
    return msg


def update_conversation_status(session_id: str, status: str, staff_id: str | None = None) -> dict | None:
    """Update conversation status (active, waiting, closed).
    
    When status is 'closed', the conversation file is deleted.
    """
    conv = _load_conversation(session_id)
    if not conv:
        return None
    
    if status == "closed":
        # Delete the conversation file
        path = _conv_path(session_id)
        if path.exists():
            path.unlink()
        return {"session_id": session_id, "status": "closed", "deleted": True}
    
    conv["status"] = status
    if staff_id:
        conv["assigned_staff"] = staff_id
    conv["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_conversation(conv)
    return conv


def get_waiting_conversations() -> list[dict]:
    """Get conversations waiting for staff response."""
    all_conv = get_all_conversations()
    return [c for c in all_conv if c.get("status") == "waiting"]


def get_active_conversations() -> list[dict]:
    """Get active conversations."""
    all_conv = get_all_conversations()
    return [c for c in all_conv if c.get("status") == "active"]


def get_closed_conversations() -> list[dict]:
    """Get closed conversations."""
    all_conv = get_all_conversations()
    return [c for c in all_conv if c.get("status") == "closed"]


def conversation_exists(session_id: str) -> bool:
    """Check if a conversation exists."""
    return _conv_path(session_id).exists()


def get_conversation_summary(conv: dict) -> dict:
    """Get a summary of a conversation for listing."""
    messages = conv.get("messages", [])
    last_msg = messages[-1] if messages else None
    student_msgs = sum(1 for m in messages if m.get("role") == "student")
    staff_msgs = sum(1 for m in messages if m.get("role") == "staff")
    ai_msgs = sum(1 for m in messages if m.get("role") == "assistant")

    assigned_staff = conv.get("assigned_staff")
    staff_online = False
    if assigned_staff:
        staff_online = staff_presence.is_staff_online(assigned_staff)

    return {
        "session_id": conv["session_id"],
        "student_id": conv["student_id"],
        "student_name": conv["student_name"],
        "status": conv["status"],
        "created_at": conv["created_at"],
        "updated_at": conv["updated_at"],
        "message_count": len(messages),
        "student_messages": student_msgs,
        "staff_messages": staff_msgs,
        "ai_messages": ai_msgs,
        "last_message": last_msg["text"][:80] if last_msg else "",
        "last_message_time": last_msg["timestamp"] if last_msg else "",
        "last_message_role": last_msg["role"] if last_msg else "",
        "assigned_staff": assigned_staff,
        "staff_online": staff_online,
    }


def is_assigned_staff_online(session_id: str) -> bool:
    """Check if the assigned staff for a conversation is currently online."""
    conv = get_conversation(session_id)
    if not conv:
        return False
    assigned_staff = conv.get("assigned_staff")
    if not assigned_staff:
        return False
    return staff_presence.is_staff_online(assigned_staff)


def get_available_staff() -> list[dict]:
    """Get list of online staff who can take conversations."""
    return staff_presence.get_online_staff()


def assign_staff_to_conversation(session_id: str, staff_id: str, staff_name: str | None = None) -> dict | None:
    """Assign a staff member to a conversation."""
    conv = get_conversation(session_id)
    if not conv:
        return None
    conv["assigned_staff"] = staff_id
    conv["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_conversation(conv)
    return conv