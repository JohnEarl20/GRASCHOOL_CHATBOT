"""Staff passcode gate for the dashboard.

Students see the AI assistant; the staff dashboard sits behind a passcode.

How the passcode is stored
--------------------------
The passcode is **not** written in the source. It is read, in this order, from:

1. `STAFF_PASSCODE` in the environment, or in a `.env` file at the project root
2. `staff.passcode` in `.streamlit/secrets.toml` (Streamlit's own secret store)

If neither exists the dashboard stays locked and says so. There is no default
passcode, because a default passcode is the same as no passcode - it would be
in the source, in git, and in every copy of the project.

This is a lightweight gate for a class prototype, not real authentication:
there is one shared passcode, no per-user accounts, and no audit trail of who
entered it. It keeps a student from wandering into the staff analytics by
accident, which is what it is for.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

SESSION_KEY = "staff_unlocked"
ATTEMPTS_KEY = "staff_attempts"
MAX_ATTEMPTS = 5


def _read_dotenv() -> dict[str, str]:
    """Minimal .env reader: KEY=VALUE per line, # comments, optional quotes.

    Not python-dotenv, so the project keeps one less dependency.
    """
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    try:
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            values[key.strip()] = value
    except OSError:
        return {}
    return values


def expected_passcode() -> str | None:
    """The configured passcode, or None when none is configured."""
    from_env = os.environ.get("STAFF_PASSCODE")
    if from_env:
        return from_env

    dotenv = _read_dotenv()
    if dotenv.get("STAFF_PASSCODE"):
        return dotenv["STAFF_PASSCODE"]

    try:
        secret = st.secrets.get("staff", {}).get("passcode")
    except (FileNotFoundError, KeyError, AttributeError):
        secret = None
    if secret:
        return str(secret)

    return None


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def check(candidate: str) -> bool:
    """Compare in constant time, so timing does not leak the passcode."""
    configured = expected_passcode()
    if not configured or not candidate:
        return False
    return hmac.compare_digest(_digest(candidate), _digest(configured))


def is_unlocked() -> bool:
    return bool(st.session_state.get(SESSION_KEY))


def lock() -> None:
    st.session_state[SESSION_KEY] = False
    st.session_state[ATTEMPTS_KEY] = 0


def attempts_left() -> int:
    return max(0, MAX_ATTEMPTS - int(st.session_state.get(ATTEMPTS_KEY, 0)))


def gate() -> bool:
    """Draw the passcode form. Returns True once the dashboard may render."""
    if is_unlocked():
        return True

    configured = expected_passcode()
    C_icon = "&#128274;"

    st.markdown(
        "<div class='cca-hero'>"
        "<h1>Staff dashboard - passcode required</h1>"
        "<p>The analytics, the question log and the model retraining are for "
        "registrar staff. Students can keep using the AI Assistant.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not configured:
        st.error(
            "No staff passcode is configured, so the dashboard is locked. Set "
            "`STAFF_PASSCODE` in a `.env` file at the project root, or "
            "`staff.passcode` in `.streamlit/secrets.toml`, then restart the app."
        )
        st.code(
            "# .env\nSTAFF_PASSCODE=your-passcode-here",
            language="bash",
        )
        return False

    if attempts_left() <= 0:
        st.error(
            f"Too many wrong attempts ({MAX_ATTEMPTS}). The dashboard is locked for "
            "this session - reload the page to try again."
        )
        if st.button("Reload the page"):
            st.rerun()
        return False

    with st.form("staff_gate", clear_on_submit=False):
        code = st.text_input("Passcode", type="password", key="staff_code")
        submitted = st.form_submit_button("Unlock dashboard", type="primary")

    if submitted:
        if check(code):
            st.session_state[SESSION_KEY] = True
            st.session_state[ATTEMPTS_KEY] = 0
            st.rerun()
        else:
            st.session_state[ATTEMPTS_KEY] = int(st.session_state.get(ATTEMPTS_KEY, 0)) + 1
            left = attempts_left()
            if left:
                st.error(f"Wrong passcode. {left} attempt{'s' if left != 1 else ''} left.")
            else:
                st.error(f"Wrong passcode. The dashboard is locked for this session.")
                st.rerun()

    st.caption(
        f"{C_icon} One shared passcode for registrar staff. Not a per-user login - "
        "see the note in `code/staff_gate.py`."
    )
    return False
