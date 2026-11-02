"""Unified authentication for students and staff.

File-based auth stored in data/users.json with role field.
Passwords are hashed with SHA-256 (not production grade, but fine for a class prototype).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"

SESSION_KEY = "user_id"
SESSION_ROLE_KEY = "user_role"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)


def _load_users() -> dict:
    _ensure_data_dir()
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_users(users: dict) -> None:
    _ensure_data_dir()
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_account(user_id: str, password: str, name: str = "", role: str = "student") -> tuple[bool, str]:
    """Create a new account. Returns (success, message)."""
    user_id = user_id.strip()
    users = _load_users()

    if not user_id:
        return False, "ID is required"

    if user_id in users:
        return False, f"{role.capitalize()} ID already exists"

    if len(password) < 4:
        return False, "Password must be at least 4 characters"

    if role not in ("student", "staff"):
        return False, "Invalid role"

    if role == "staff" and not is_staff():
        return False, "Only an authenticated staff member can create staff accounts"

    users[user_id] = {
        "password_hash": _hash_password(password),
        "name": name.strip(),
        "role": role,
        "created_at": datetime.now().isoformat(),
    }
    _save_users(users)
    return True, f"{role.capitalize()} account created successfully"


def login(user_id: str, password: str, expected_role: str | None = None) -> tuple[bool, str]:
    """Verify credentials and log in. Returns (success, message)."""
    users = _load_users()

    if user_id not in users:
        return False, "ID not found"

    if users[user_id]["password_hash"] != _hash_password(password):
        return False, "Incorrect password"

    if expected_role and users[user_id]["role"] != expected_role:
        return False, f"This account is not a {expected_role} account"

    st.session_state[SESSION_KEY] = user_id
    st.session_state[SESSION_ROLE_KEY] = users[user_id]["role"]
    return True, f"Welcome, {users[user_id].get('name', user_id)}"


def logout() -> None:
    """Log out the current user."""
    for key in (SESSION_KEY, SESSION_ROLE_KEY):
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return bool(st.session_state.get(SESSION_KEY))


def get_current_user_id() -> str | None:
    return st.session_state.get(SESSION_KEY)


def get_current_user_role() -> str | None:
    return st.session_state.get(SESSION_ROLE_KEY)


def get_current_user_name() -> str | None:
    user_id = get_current_user_id()
    if not user_id:
        return None
    users = _load_users()
    return users.get(user_id, {}).get("name")


def is_staff() -> bool:
    return get_current_user_role() == "staff"


def is_student() -> bool:
    return get_current_user_role() == "student"