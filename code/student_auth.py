"""Student authentication - create account, login, logout.

This is a simple file-based auth for students, stored in data/students.json.
Passwords are hashed with SHA-256 (not production grade, but fine for a class prototype).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STUDENTS_FILE = DATA_DIR / "students.json"

SESSION_KEY = "student_user"
SESSION_ID_KEY = "student_id"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)


def _load_students() -> dict:
    _ensure_data_dir()
    if not STUDENTS_FILE.exists():
        return {}
    try:
        return json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_students(students: dict) -> None:
    _ensure_data_dir()
    STUDENTS_FILE.write_text(json.dumps(students, indent=2), encoding="utf-8")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_account(student_id: str, password: str, name: str = "") -> tuple[bool, str]:
    """Create a new student account. Returns (success, message)."""
    students = _load_students()

    if student_id in students:
        return False, "Student ID already exists"

    if len(password) < 4:
        return False, "Password must be at least 4 characters"

    students[student_id] = {
        "password_hash": _hash_password(password),
        "name": name.strip(),
        "created_at": datetime.now().isoformat(),
    }
    _save_students(students)
    return True, "Account created successfully"


def login(student_id: str, password: str) -> tuple[bool, str]:
    """Verify credentials and log in. Returns (success, message)."""
    students = _load_students()

    if student_id not in students:
        return False, "Student ID not found"

    if students[student_id]["password_hash"] != _hash_password(password):
        return False, "Incorrect password"

    st.session_state[SESSION_KEY] = student_id
    st.session_state[SESSION_ID_KEY] = student_id
    return True, f"Welcome, {students[student_id].get('name', student_id)}"


def logout() -> None:
    """Log out the current student."""
    for key in (SESSION_KEY, SESSION_ID_KEY):
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return bool(st.session_state.get(SESSION_KEY))


def get_current_student_id() -> str | None:
    return st.session_state.get(SESSION_KEY)


def get_current_student_name() -> str | None:
    student_id = get_current_student_id()
    if not student_id:
        return None
    students = _load_students()
    return students.get(student_id, {}).get("name")


from datetime import datetime