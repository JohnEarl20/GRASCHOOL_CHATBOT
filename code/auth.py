"""Unified authentication for students and staff.

File-based auth stored in data/users.json with role field.
New passwords use salted PBKDF2-SHA256. Existing SHA-256 password hashes remain
supported so legacy accounts can continue to sign in.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
import streamlit as st
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
ADMIN_ENV_PATH = ROOT / ".env"

SESSION_KEY = "user_id"
SESSION_ROLE_KEY = "user_role"
SESSION_COOKIE_NAME = "gra_auth_session"
SESSION_COOKIE_TTL_SECONDS = 30 * 24 * 60 * 60
SESSION_COOKIE_MAX_AGE_SECONDS = 400 * 24 * 60 * 60
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ACCOUNT_LOCK = threading.RLock()


class AccountStoreError(RuntimeError):
    """Raised when the account store cannot be read or safely updated."""


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)


def _deployment_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value

    if ADMIN_ENV_PATH.is_file():
        try:
            for raw_line in ADMIN_ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                key, separator, raw_value = line.partition("=")
                if separator and key.strip() == name:
                    value = raw_value.strip().strip('"').strip("'")
                    if value:
                        return value
        except OSError:
            pass

    try:
        secret = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError, AttributeError, RuntimeError):
        secret = ""
    return str(secret).strip() if secret else ""


def _bootstrap_admin_values() -> tuple[str, str, str, str, str]:
    return (
        _deployment_setting("BOOTSTRAP_ADMIN_ID"),
        _deployment_setting("BOOTSTRAP_ADMIN_PASSWORD"),
        _deployment_setting("BOOTSTRAP_ADMIN_NAME") or "GRA SCHOOL Administrator",
        _deployment_setting("BOOTSTRAP_ADMIN_EMAIL"),
        _deployment_setting("BOOTSTRAP_ADMIN_DEPARTMENT") or "Administration",
    )


def _ensure_bootstrap_admin(users: dict) -> bool:
    """Create the initial admin from private deployment settings if configured."""
    admin_id, password, name, email, department = _bootstrap_admin_values()
    if not admin_id and not password:
        return False
    if not admin_id or not password:
        raise AccountStoreError(
            "Both BOOTSTRAP_ADMIN_ID and BOOTSTRAP_ADMIN_PASSWORD must be configured."
        )
    if len(admin_id) > 64 or any(ord(char) < 32 for char in admin_id):
        raise AccountStoreError(
            "BOOTSTRAP_ADMIN_ID must be a valid ID of at most 64 characters."
        )
    if len(password) < 8:
        raise AccountStoreError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 8 characters.")

    matching_id = next(
        (existing_id for existing_id in users if existing_id.casefold() == admin_id.casefold()),
        None,
    )
    if matching_id is not None:
        if users[matching_id].get("role") != "staff":
            raise AccountStoreError(
                "BOOTSTRAP_ADMIN_ID already belongs to a non-staff account."
            )
        return False

    normalized_email = email.casefold()
    if normalized_email:
        if len(normalized_email) > 254 or not EMAIL_PATTERN.fullmatch(normalized_email):
            raise AccountStoreError("BOOTSTRAP_ADMIN_EMAIL is invalid.")
        if any(
            isinstance(record.get("email"), str)
            and record["email"].strip().casefold() == normalized_email
            for record in users.values()
        ):
            raise AccountStoreError("BOOTSTRAP_ADMIN_EMAIL is already used by another account.")

    users[admin_id] = {
        "password_hash": _hash_password(password),
        "name": name,
        "email": normalized_email,
        "department": department,
        "role": "staff",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    return True


def _database_url() -> str:
    database_url = _deployment_setting("DATABASE_URL")
    if not database_url and os.environ.get("RENDER_SERVICE_ID"):
        raise AccountStoreError(
            "Persistent account storage is not configured. Set DATABASE_URL "
            "to the PostgreSQL connection URL in the Render environment."
        )
    return database_url


def _connect_to_database(database_url: str):
    return psycopg.connect(database_url, sslmode="require")


def _load_postgres_users(database_url: str) -> dict:
    try:
        with _connect_to_database(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gra_accounts (
                        user_id TEXT PRIMARY KEY,
                        normalized_id TEXT NOT NULL UNIQUE,
                        account_data JSONB NOT NULL
                    )
                    """
                )
                cursor.execute(
                    "SELECT user_id, account_data FROM gra_accounts"
                )
                rows = cursor.fetchall()
                users = {
                    user_id: account_data
                    for user_id, account_data in rows
                }

                migrate_json = os.environ.get(
                    "MIGRATE_USERS_JSON_TO_DATABASE", ""
                ).strip().casefold() in {"1", "true", "yes"}
                if not users and migrate_json and USERS_FILE.is_file():
                    legacy_users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
                    if not isinstance(legacy_users, dict) or any(
                        not isinstance(user_id, str)
                        or not isinstance(record, dict)
                        for user_id, record in legacy_users.items()
                    ):
                        raise AccountStoreError(
                            "The existing account file has an invalid format and "
                            "could not be migrated."
                        )
                    _upsert_postgres_users(cursor, legacy_users)
                    users = legacy_users
    except AccountStoreError:
        raise
    except (psycopg.Error, OSError, json.JSONDecodeError) as error:
        raise AccountStoreError(
            f"Could not read the PostgreSQL account database: {error}"
        ) from error
    return users


def _upsert_postgres_users(cursor, users: dict) -> None:
    cursor.executemany(
        """
        INSERT INTO gra_accounts (user_id, normalized_id, account_data)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            normalized_id = EXCLUDED.normalized_id,
            account_data = EXCLUDED.account_data
        """,
        [
            (user_id, user_id.casefold(), Jsonb(record))
            for user_id, record in users.items()
        ],
    )


def _load_users() -> dict:
    with _ACCOUNT_LOCK:
        database_url = _database_url()
        if database_url:
            users = _load_postgres_users(database_url)
            if not isinstance(users, dict) or any(
                not isinstance(user_id, str) or not isinstance(record, dict)
                for user_id, record in users.items()
            ):
                raise AccountStoreError(
                    "The PostgreSQL account database has an invalid format."
                )
            if _ensure_bootstrap_admin(users):
                _save_users(users)
            return users

        try:
            _ensure_data_dir()
            users = (
                json.loads(USERS_FILE.read_text(encoding="utf-8"))
                if USERS_FILE.exists()
                else {}
            )
        except (json.JSONDecodeError, OSError) as error:
            raise AccountStoreError(f"Could not read the account database: {error}") from error
        if not isinstance(users, dict) or any(
            not isinstance(user_id, str) or not isinstance(record, dict)
            for user_id, record in users.items()
        ):
            raise AccountStoreError("The account database has an invalid format.")
        if _ensure_bootstrap_admin(users):
            _save_users(users)
        return users


def _save_users(users: dict) -> None:
    database_url = _database_url()
    if database_url:
        try:
            with _connect_to_database(database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS gra_accounts (
                            user_id TEXT PRIMARY KEY,
                            normalized_id TEXT NOT NULL UNIQUE,
                            account_data JSONB NOT NULL
                        )
                        """
                    )
                    _upsert_postgres_users(cursor, users)
        except psycopg.Error as error:
            raise AccountStoreError(
                f"Could not save the PostgreSQL account database: {error}"
            ) from error
        return

    temporary_path = None
    try:
        _ensure_data_dir()
        temporary_path = USERS_FILE.with_name(
            f"{USERS_FILE.name}.{secrets.token_hex(8)}.tmp"
        )
        temporary_path.write_text(
            json.dumps(users, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(USERS_FILE)
    except OSError as error:
        try:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise AccountStoreError(f"Could not save the account database: {error}") from error


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return (
        f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}"
        f"${salt.hex()}${digest.hex()}"
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith(f"{PASSWORD_SCHEME}$"):
        try:
            scheme, iteration_value, salt_hex, digest_hex = stored_hash.split("$")
            if scheme != PASSWORD_SCHEME:
                return False
            iterations = int(iteration_value)
            if not 100_000 <= iterations <= 2_000_000:
                return False
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                iterations,
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(actual, expected)

    # Keep accounts created by the original SHA-256 implementation usable.
    legacy_digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, legacy_digest)


def _account_id_exists(users: dict, user_id: str) -> bool:
    normalized_id = user_id.casefold()
    return any(existing_id.casefold() == normalized_id for existing_id in users)


def _configured_admin_ids() -> set[str]:
    configured = os.environ.get("STAFF_ADMIN_IDS", "").strip()
    if not configured:
        configured = _deployment_setting("STAFF_ADMIN_IDS")
    admin_ids: set[str] = set()
    if configured:
        admin_ids.update(
            value.strip().casefold()
            for value in configured.split(",")
            if value.strip()
        )
    if not admin_ids:
        try:
            configured_list = st.secrets.get("STAFF_ADMIN_IDS")
            if configured_list is None:
                configured_list = st.secrets.get("staff", {}).get("admin_ids", [])
        except (FileNotFoundError, KeyError, AttributeError, RuntimeError):
            configured_list = []
        if isinstance(configured_list, str):
            configured_list = configured_list.split(",")
        if isinstance(configured_list, (list, tuple, set)):
            admin_ids.update(
                str(value).strip().casefold()
                for value in configured_list
                if str(value).strip()
            )

    bootstrap_admin_id, _, _, _, _ = _bootstrap_admin_values()
    if bootstrap_admin_id:
        admin_ids.add(bootstrap_admin_id.casefold())
    return admin_ids


def _find_account(users: dict, user_id: str) -> tuple[str | None, dict | None]:
    """Find an account by ID without making identifier casing significant."""
    normalized_id = user_id.strip().casefold()
    matches = [
        (stored_id, record)
        for stored_id, record in users.items()
        if stored_id.casefold() == normalized_id
    ]
    if len(matches) > 1:
        return None, None
    return matches[0] if matches else (None, None)


def create_account(user_id: str, password: str, name: str = "", role: str = "student") -> tuple[bool, str]:
    """Create a public student account; staff must use the admin-only flow."""
    if role != "student":
        return False, "Staff accounts can only be created by an authorized administrator."
    user_id = user_id.strip() if isinstance(user_id, str) else ""
    if not user_id:
        return False, "ID is required."
    if len(user_id) > 64 or any(ord(char) < 32 for char in user_id):
        return False, "ID must be at most 64 characters and contain no control characters."
    if not isinstance(password, str) or len(password) < 4:
        return False, "Password must be at least 4 characters."
    try:
        with _ACCOUNT_LOCK:
            users = _load_users()
            if _account_id_exists(users, user_id):
                return False, "An account with this ID already exists."
            users[user_id] = {
                "password_hash": _hash_password(password),
                "name": name.strip() if isinstance(name, str) else "",
                "role": "student",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "profile_picture": "",
            }
            _save_users(users)
    except AccountStoreError as error:
        return False, str(error)
    return True, "Student account created successfully."


def create_staff_account(
    user_id: str,
    full_name: str,
    email: str,
    department: str,
    password: str,
    confirm_password: str,
) -> tuple[bool, str]:
    """Create a staff account only for an explicitly allowlisted administrator."""
    if not is_admin():
        return False, "Only an authorized administrator can create staff accounts."

    user_id = user_id.strip() if isinstance(user_id, str) else ""
    full_name = full_name.strip() if isinstance(full_name, str) else ""
    email = email.strip().casefold() if isinstance(email, str) else ""
    department = department.strip() if isinstance(department, str) else ""

    if not user_id or len(user_id) > 64 or any(ord(char) < 32 for char in user_id):
        return False, "Enter a valid Staff ID (1-64 characters)."
    if len(full_name) < 2 or len(full_name) > 120:
        return False, "Full Name must be between 2 and 120 characters."
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return False, "Enter a valid Official Email address."
    if len(department) < 2 or len(department) > 100:
        return False, "Department must be between 2 and 100 characters."
    if not isinstance(password, str) or len(password) < 8:
        return False, "Password must be at least 8 characters."
    if password != confirm_password:
        return False, "Password and Confirm Password do not match."

    try:
        with _ACCOUNT_LOCK:
            users = _load_users()
            if _account_id_exists(users, user_id):
                return False, "An account with this Staff ID already exists."
            if any(
                isinstance(record.get("email"), str)
                and record["email"].strip().casefold() == email
                for record in users.values()
            ):
                return False, "An account with this email address already exists."

            users[user_id] = {
                "password_hash": _hash_password(password),
                "name": full_name,
                "email": email,
                "department": department,
                "role": "staff",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "profile_picture": "",
            }
            _save_users(users)
    except AccountStoreError as error:
        return False, str(error)
    return True, "Staff account created successfully. The new staff member can log in now."


def login(user_id: str, password: str, expected_role: str | None = None) -> tuple[bool, str]:
    """Verify credentials and log in. Returns (success, message)."""
    user_id = user_id.strip() if isinstance(user_id, str) else ""
    if not user_id or not isinstance(password, str):
        return False, "Please enter both ID and password."
    try:
        users = _load_users()
    except AccountStoreError as error:
        return False, str(error)

    stored_id, account = _find_account(users, user_id)
    if account is None:
        return False, "ID not found"

    stored_hash = account.get("password_hash")
    if not isinstance(stored_hash, str) or not _verify_password(password, stored_hash):
        return False, "Incorrect password"

    role = account.get("role")
    if role not in {"student", "staff"}:
        return False, "This account has an invalid role. Contact an administrator."
    if expected_role and role != expected_role:
        return False, f"This account is not a {expected_role} account"

    st.session_state[SESSION_KEY] = stored_id
    st.session_state[SESSION_ROLE_KEY] = role
    return True, f"Welcome, {account.get('name', user_id)}"


def logout(cookie_manager=None) -> None:
    """Log out the current user.

    Clears the session state *and* the browser login cookie so that a page
    refresh cannot restore the login through ``restore_session_token``.
    """
    for key in (SESSION_KEY, SESSION_ROLE_KEY):
        st.session_state.pop(key, None)
    if cookie_manager is not None:
        cookie_manager.set(
            SESSION_COOKIE_NAME,
            "",
            key="logout_auth_session",
            path="/",
            expires_at=datetime.now() - timedelta(seconds=1),
            max_age=0,
            secure=bool(os.environ.get("RENDER_SERVICE_ID")),
            same_site="lax",
        )


def update_profile_picture(user_id: str, picture_data: str) -> tuple[bool, str]:
    """Update the profile picture for a user.
    
    Args:
        user_id: The user ID
        picture_data: Base64 encoded image data (with data URI prefix)
    
    Returns:
        Tuple of (success, message)
    """
    if not user_id:
        return False, "User ID is required."
    
    try:
        with _ACCOUNT_LOCK:
            users = _load_users()
            stored_id, account = _find_account(users, user_id)
            if account is None:
                return False, "User not found."
            
            # Validate it's a valid data URI
            if picture_data and not picture_data.startswith("data:image/"):
                return False, "Invalid image format. Must be a data URI."
            
            # Limit size to ~2MB (base64 encoded)
            if picture_data and len(picture_data) > 2_500_000:
                return False, "Image too large. Maximum size is 2MB."
            
            users[stored_id]["profile_picture"] = picture_data
            _save_users(users)
    except AccountStoreError as error:
        return False, str(error)
    return True, "Profile picture updated successfully."


def get_profile_picture(user_id: str) -> str:
    """Get the profile picture for a user.
    
    Returns:
        Base64 encoded image data URI, or empty string if not set.
    """
    if not user_id:
        return ""
    users = _load_users()
    _, account = _find_account(users, user_id)
    if account:
        return account.get("profile_picture", "")
    return ""


def create_session_token() -> str:
    """Create a signed token for restoring this browser's login until revoked."""
    user_id = get_current_user_id()
    if not user_id:
        raise ValueError("An authenticated account is required to create a session token.")

    account = _load_users().get(user_id)
    if not account or account.get("role") not in {"student", "staff"}:
        raise AccountStoreError("The signed-in account is no longer available.")
    password_hash = account.get("password_hash")
    if not isinstance(password_hash, str) or not password_hash:
        raise AccountStoreError("The signed-in account has no valid password record.")

    payload = {
        "user_id": user_id,
        "nonce": secrets.token_urlsafe(16),
    }
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signing_key = hashlib.sha256(
        f"gra-auth-session-v1:{password_hash}".encode("utf-8")
    ).digest()
    signature = hmac.new(
        signing_key,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def restore_session_token(token: str) -> bool:
    """Restore a login only when its signature and account still match.

    The expiry check remains for tokens issued by the previous 30-day format.
    """
    if not isinstance(token, str) or len(token) > 2048:
        return False
    encoded_payload, separator, supplied_signature = token.partition(".")
    if (
        not separator
        or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded_payload)
        or not re.fullmatch(r"[0-9a-f]{64}", supplied_signature)
    ):
        return False

    try:
        padding = "=" * (-len(encoded_payload) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False

    user_id = payload.get("user_id")
    expires_at = payload.get("expires_at")
    nonce = payload.get("nonce")
    if (
        not isinstance(user_id, str)
        or not user_id
        or not isinstance(nonce, str)
        or not nonce
        or (
            expires_at is not None
            and (
                not isinstance(expires_at, int)
                or isinstance(expires_at, bool)
                or expires_at <= int(time.time())
                or expires_at > int(time.time()) + SESSION_COOKIE_TTL_SECONDS + 60
            )
        )
    ):
        return False

    stored_id, account = _find_account(_load_users(), user_id)
    if not stored_id or not account or account.get("role") not in {"student", "staff"}:
        return False
    password_hash = account.get("password_hash")
    if not isinstance(password_hash, str) or not password_hash:
        return False

    signing_key = hashlib.sha256(
        f"gra-auth-session-v1:{password_hash}".encode("utf-8")
    ).digest()
    expected_signature = hmac.new(
        signing_key,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        return False

    st.session_state[SESSION_KEY] = stored_id
    st.session_state[SESSION_ROLE_KEY] = account["role"]
    return True


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
    _, account = _find_account(users, user_id)
    return account.get("name") if account else None


def is_staff() -> bool:
    return get_current_user_role() == "staff"


def is_student() -> bool:
    return get_current_user_role() == "student"


def is_admin() -> bool:
    """Return whether the signed-in staff ID is configured as an administrator."""
    user_id = get_current_user_id()
    return bool(
        is_staff()
        and user_id
        and user_id.strip().casefold() in _configured_admin_ids()
    )