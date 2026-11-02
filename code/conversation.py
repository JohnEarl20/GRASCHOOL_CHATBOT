"""Conversation storage for real-time student-staff chat.

Each conversation is a JSON file in data/conversations/ with the session_id as filename.
Students see their own conversation; staff see all conversations and can reply.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from code import staff_presence

ROOT = Path(__file__).resolve().parent.parent
CONV_DIR = ROOT / "data" / "conversations"
STAFF_RESPONSE_TIMEOUT_SECONDS = 5


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


def _next_message_timestamp(conv: dict) -> str:
    """Return a timestamp strictly later than the previous message."""
    now = datetime.now()
    messages = conv.get("messages", [])
    if messages:
        previous_value = messages[-1].get("timestamp")
        if previous_value:
            try:
                previous = datetime.fromisoformat(previous_value)
                if previous.tzinfo is not None:
                    now = datetime.now(previous.tzinfo)
                if now <= previous:
                    now = previous + timedelta(microseconds=1)
            except (TypeError, ValueError):
                pass
    return now.isoformat(timespec="microseconds")


def create_conversation(
    student_id: str,
    student_name: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Create a new conversation for a student."""
    from code import auth

    if not auth.is_student() or auth.get_current_user_id() != student_id:
        raise PermissionError("Only a student can create their own conversation.")
    session_id = session_id or uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[a-f0-9]{12}", session_id):
        raise ValueError("Conversation ID must be 12 lowercase hexadecimal characters.")
    if _conv_path(session_id).exists():
        raise ValueError("A conversation with this ID already exists.")
    now = datetime.now().isoformat(timespec="microseconds")
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


def delete_conversation(session_id: str) -> bool:
    """Permanently delete one conversation and its logged inquiry rows."""
    from code import auth

    if not auth.is_staff():
        raise PermissionError("Only authorized staff can delete student conversations.")
    return _permanently_delete_conversation(session_id)


def delete_own_conversation(session_id: str) -> bool:
    """Allow a student to permanently delete only their own conversation."""
    from code import auth

    if not auth.is_student():
        raise PermissionError("Only the student who owns a conversation can delete it.")
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{12}", session_id):
        raise ValueError("Invalid conversation ID.")
    student_id = auth.get_current_user_id()
    conv = _load_conversation(session_id)
    if not student_id or not conv or conv.get("student_id") != student_id:
        raise PermissionError("You can only delete your own conversations.")
    return _permanently_delete_conversation(session_id)


def _permanently_delete_conversation(session_id: str) -> bool:
    if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{12}", session_id):
        raise ValueError("Invalid conversation ID.")
    path = _conv_path(session_id)
    if not path.is_file():
        return False
    deleting_path = path.with_suffix(".deleting")
    if deleting_path.exists():
        raise OSError("This conversation is already being deleted.")

    try:
        os.replace(path, deleting_path)
        from code import logger

        logger.delete_session_logs(session_id)
        deleting_path.unlink()
    except OSError:
        if deleting_path.exists() and not path.exists():
            os.replace(deleting_path, path)
        raise
    return True


def get_student_conversation(student_id: str) -> dict | None:
    """Get the newest non-resolved conversation for a student."""
    return next(
        (
            conv for conv in get_student_conversations(student_id)
            if conv.get("status") in {"active", "waiting"}
        ),
        None,
    )


def get_student_conversations(student_id: str) -> list[dict]:
    """Get conversation history for one student, newest first."""
    if not student_id:
        return []
    _ensure_dir()
    conversations = []
    for path in CONV_DIR.glob("*.json"):
        try:
            conv = json.loads(path.read_text(encoding="utf-8"))
            if conv.get("student_id") == student_id:
                conversations.append(conv)
        except (json.JSONDecodeError, OSError):
            continue
    conversations.sort(key=lambda conv: conv.get("updated_at", ""), reverse=True)
    return conversations


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
    """Append a role-authorized message to a conversation."""
    from code import auth

    conv = _load_conversation(session_id)
    if not conv:
        return None
    if role not in {"student", "assistant", "staff"}:
        raise ValueError("Message role must be student, assistant, or staff.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Message text cannot be empty.")
    if conv.get("status") == "closed":
        raise ValueError("Resolved conversations are read-only.")

    current_user_id = auth.get_current_user_id()
    if role == "staff":
        if (
            not auth.is_staff()
            or not current_user_id
            or sender_id != current_user_id
        ):
            raise PermissionError("Only the authenticated staff member can reply as staff.")
        if conv.get("assigned_staff") != current_user_id:
            raise PermissionError("Take over this inquiry before replying to the student.")
    elif role in {"student", "assistant"}:
        if (
            not auth.is_student()
            or not current_user_id
            or conv.get("student_id") != current_user_id
        ):
            raise PermissionError("Only the student who owns this conversation can add messages.")
        if role == "student" and sender_id and sender_id != current_user_id:
            raise PermissionError("Student messages must use the authenticated student's ID.")

    now = _next_message_timestamp(conv)
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

    if role == "student" and (
        conv.get("status") == "waiting" or conv.get("assigned_staff")
    ):
        conv["status"] = "waiting"
        conv["waiting_since"] = now
    elif role == "staff":
        conv["status"] = "active"
        conv["assigned_staff"] = sender_id
        conv.pop("waiting_since", None)

    _save_conversation(conv)
    return msg


def update_conversation_status(session_id: str, status: str, staff_id: str | None = None) -> dict | None:
    """Update conversation status while retaining the record for staff history."""
    from code import auth

    conv = _load_conversation(session_id)
    if not conv:
        return None
    if status not in {"active", "waiting", "closed"}:
        raise ValueError("Conversation status must be active, waiting, or closed.")
    current_user_id = auth.get_current_user_id()
    if auth.is_staff():
        if not current_user_id:
            raise PermissionError("A signed-in staff account is required.")
        if staff_id and staff_id != current_user_id:
            raise PermissionError("Staff can only update status as their own account.")
        staff_id = current_user_id
    elif (
        not auth.is_student()
        or current_user_id != conv.get("student_id")
        or status != "waiting"
    ):
        raise PermissionError("Only staff can change this conversation status.")
    if conv.get("status") == "closed" and status != "closed":
        raise ValueError("Resolved conversations cannot be reopened.")

    conv["status"] = status
    if staff_id:
        conv["assigned_staff"] = staff_id
    now = datetime.now().isoformat(timespec="microseconds")
    if status == "waiting":
        conv["waiting_since"] = now
    elif status == "closed":
        conv.pop("waiting_since", None)
    conv["updated_at"] = now
    _save_conversation(conv)
    return conv


def staff_response_seconds_remaining(conv: dict) -> int | None:
    """Return seconds until AI fallback, or None when no staff reply is pending."""
    waiting_since = conv.get("waiting_since")
    if not isinstance(waiting_since, str) or not waiting_since:
        return None
    try:
        started = datetime.fromisoformat(waiting_since)
    except ValueError:
        return None
    now = datetime.now(started.tzinfo) if started.tzinfo else datetime.now()
    elapsed = (now - started).total_seconds()
    return max(0, int(STAFF_RESPONSE_TIMEOUT_SECONDS - elapsed))


def add_staff_timeout_reply(
    session_id: str,
    expected_waiting_since: str,
    text: str,
    meta: dict | None = None,
) -> dict | None:
    """Atomically let AI answer after the staff response deadline expires."""
    from code import auth

    conv = _load_conversation(session_id)
    current_user_id = auth.get_current_user_id()
    if (
        not auth.is_student()
        or not current_user_id
        or not conv
        or conv.get("student_id") != current_user_id
    ):
        raise PermissionError("Only the student who owns this conversation can trigger AI fallback.")
    if (
        conv.get("status") == "closed"
        or conv.get("waiting_since") != expected_waiting_since
        or staff_response_seconds_remaining(conv) != 0
    ):
        return None

    if not isinstance(text, str) or not text.strip():
        raise ValueError("AI response cannot be empty.")

    now = _next_message_timestamp(conv)
    message = {
        "id": uuid.uuid4().hex[:8],
        "role": "assistant",
        "text": text.strip(),
        "sender_id": None,
        "sender_name": None,
        "timestamp": now,
        "meta": meta or {},
    }
    conv["messages"].append(message)
    conv["status"] = "active"
    conv.pop("waiting_since", None)
    conv["updated_at"] = now
    _save_conversation(conv)
    return message


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
    from code import auth

    if not auth.is_staff() or auth.get_current_user_id() != staff_id:
        raise PermissionError("Only an authenticated staff member can assign themselves.")
    conv = get_conversation(session_id)
    if not conv or conv.get("status") == "closed":
        return None
    current_assignment = conv.get("assigned_staff")
    if (
        current_assignment
        and current_assignment != staff_id
        and staff_presence.is_staff_online(current_assignment)
    ):
        return None
    conv["assigned_staff"] = staff_id
    conv["status"] = "active"
    conv["updated_at"] = datetime.now().isoformat(timespec="microseconds")
    _save_conversation(conv)
    return conv