"""GRA SCHOOL - Cognitive Campus Assistant.

    python -m streamlit run app.py

One app, four views behind a sidebar: the student AI assistant, a voice
upload page, the staff dashboard, and the developers page.

Presentation lives in `ui/`; everything about what the assistant knows and
says lives in `code/`. This file only wires the two together.

The application uses the existing role-aware login and file-backed account
store. Students use the assistant and voice upload; staff-only workspace routes
are checked against the authenticated staff role before rendering.
"""
from __future__ import annotations

import base64
import html
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import extra_streamlit_components as stx
import pandas as pd
import streamlit as st

from code import dialogue, forecast, knowledge, logger, conversation, handoff, staff_content, staff_presence
from code import intent_model as intent_model_module
from code import staff_gate, auth
from ui import components as C
from ui import theme
from ui import settings_dashboard
from ui import staff_workspace

st.set_page_config(
    page_title="GRA SCHOOL - Cognitive Campus Assistant",
    page_icon="G",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "About": (
            "Cognitive Campus Assistant - enrollment requirements and student "
            "services advisor for the Registrar Office (CS ELEC 6).\n\n"
            "[Open GRA SCHOOL on Render](https://graschool-chatbot.onrender.com)"
        )
    },
)

INTENT_LABELS = {
    "ask_requirements": "Requirements",
    "ask_schedule_deadline": "Deadlines",
    "ask_fees_payment": "Fees",
    "ask_office_hours_location": "Office hours",
    "ask_course_prereq": "Prerequisites",
    "ask_clearance_process": "Clearance",
    "check_eligibility": "Eligibility",
    "request_human": "Staff hand-off",
    "give_feedback": "Feedback",
    "greet": "Greetings",
    "unknown": "Not recognised",
}

NAV = [
    ("chat", "AI Assistant", "bot"),
    ("student_announcements", "School Announcements", "megaphone"),
    ("student_documents", "Shared Documents", "upload"),
    ("student_knowledge", "Knowledge Base", "book"),
]

# Auth views (shown in sidebar based on login state)
AUTH_NAV = [
    ("login", "Login", "login"),
    ("register", "Create Account", "user-plus"),
]

# Utility views sit at the bottom of the sidebar, below the staff entry, not in
# the main navigation. Order here is the order drawn: Settings, then Voice.
UTILITY_NAV = [
    ("settings", "Settings", "settings"),
    ("voice", "Voice Upload", "mic"),
]

ALL_VIEWS = (
    {key for key, _, _ in NAV}
    | {key for key, _, _ in UTILITY_NAV}
    | {key for key, _, _ in AUTH_NAV}
    | {"staff_login", "dashboard_chat"}
)

STAFF_NAV = [
    ("dashboard", "Staff Dashboard", "home"),
    ("inquiries", "Student Inquiries", "message"),
    ("knowledge_announcements", "Knowledge & Announcements", "book"),
    ("review", "Question Review", "file-text"),
    ("documents", "Document Management", "upload"),
    ("analytics", "Analytics & Reports", "chart"),
    ("staff_management", "Staff Management", "users"),
    ("settings", "Settings", "settings"),
]

SAMPLE_PROMPTS = [
    ("Enrollment requirements", "What do I need to enroll as a freshman?"),
    ("Can I enroll?", "Can I enroll? I am a transferee and I have my TOR"),
    ("Tuition and fees", "How much is the tuition fee and where do I pay?"),
    ("Academic calendar", "When is the payment deadline?"),
]


# --------------------------------------------------------------------------
# Persistent user preferences (data/app_prefs.json)
# --------------------------------------------------------------------------
_PREFS_PATH = ROOT / "data" / "app_prefs.json"

_PREFS_DEFAULTS: dict = {
    "answer_threshold": dialogue.ANSWER_THRESHOLD,
    "clarify_threshold": dialogue.CLARIFY_THRESHOLD,
    "app_theme": "dark",
    "language": "English (US)",
    "timezone": "UTC+08:00 (Asia/Manila)",
    "date_format": "YYYY-MM-DD",
    "ai_personality": "Helpful & Professional",
    "response_length": "Standard",
    "response_lang": "Bilingual (Taglish / English)",
    "ai_memory": True,
    "voice_response": False,
    "two_factor_auth": False,
    "auto_logout_mins": 30,
    "failed_login_protection": True,
    "sys_notifications": True,
    "announcements": True,
    "doc_reminders": True,
    "login_alerts": True,
    "sound_alerts": False,
    "auto_backup": True,
    "backup_freq": "Daily (Midnight)",
    "font_size": "Medium",
    "high_contrast": False,
    "reduced_motion": False,
    "screen_reader": False,
    "audit_logs": [
        {"action": "Updated AI response settings", "user": "System Admin", "time": "Today, 8:24 AM"},
        {"action": "Changed theme to Dark", "user": "System Admin", "time": "Today, 8:17 AM"},
        {"action": "Enabled system notifications", "user": "System Admin", "time": "Yesterday, 5:46 PM"},
    ],
}


def _load_prefs() -> dict:
    """Read saved prefs from disk; fall back to defaults on any error."""
    try:
        if _PREFS_PATH.exists():
            raw = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
            merged = dict(_PREFS_DEFAULTS)
            merged.update(raw)
            return merged
        return dict(_PREFS_DEFAULTS)
    except Exception:
        return dict(_PREFS_DEFAULTS)


def _save_prefs(prefs_dict: dict) -> None:
    """Write prefs to disk atomically."""
    _PREFS_PATH.write_text(
        json.dumps(prefs_dict, indent=2),
        encoding="utf-8",
    )


def _log_audit(action: str, user: str) -> None:
    """Append an action to recent audit logs and persist."""
    p = _load_prefs()
    logs = p.get("audit_logs", [])
    now_str = datetime.now().strftime("%Y-%m-%d, %I:%M %p")
    logs.insert(0, {"action": action, "user": user, "time": now_str})
    p["audit_logs"] = logs[:50]  # keep up to 50
    _save_prefs(p)



# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
def init_state() -> None:
    if "session" not in st.session_state:
        st.session_state.session = dialogue.new_session()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "view" not in st.session_state:
        st.session_state.view = "chat"
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "staff_section" not in st.session_state:
        st.session_state["staff_section"] = "dashboard"

    # Load saved behaviour prefs the first time this session starts
    if "prefs_loaded" not in st.session_state:
        prefs = _load_prefs()
        st.session_state["answer_threshold"] = prefs["answer_threshold"]
        st.session_state["clarify_threshold"] = prefs["clarify_threshold"]
        st.session_state["prefs_loaded"] = True

    # Deep links: ?view=dashboard opens that page directly. It still passes
    # through the passcode gate, so a shared link does not leak the analytics.
    requested = st.query_params.get("view")
    if requested in ALL_VIEWS:
        st.session_state.view = requested
    requested_section = st.query_params.get("section")
    if requested_section in {"knowledge", "announcements"}:
        st.session_state["staff_knowledge_announcements_tab"] = (
            "Knowledge Base" if requested_section == "knowledge"
            else "School Announcements"
        )
        requested_section = "knowledge_announcements"
    valid_sections = {key for key, _, _ in STAFF_NAV if key not in {"chat", "settings"}}
    if st.session_state["staff_section"] not in valid_sections:
        st.session_state["staff_section"] = "dashboard"
    if requested_section in valid_sections:
        st.session_state["staff_section"] = requested_section


def _restore_browser_login(cookie_manager) -> None:
    token = st.context.cookies.get(auth.SESSION_COOKIE_NAME)
    if st.session_state.get("auth_cookie_cleared"):
        _delete_browser_login(cookie_manager, "clear_logged_out_auth_session")
        return
    if auth.is_logged_in():
        if token:
            _set_browser_login_cookie(cookie_manager, token, "refresh_auth_session")
        elif not st.session_state.get("auth_cookie_initialized"):
            _remember_browser_login(cookie_manager)
        return
    if not token:
        return
    if not auth.restore_session_token(token):
        _delete_browser_login(cookie_manager, "delete_invalid_auth_session")
    else:
        _remember_browser_login(cookie_manager)


def _delete_browser_login(cookie_manager, key: str) -> None:
    cookie_manager.set(
        auth.SESSION_COOKIE_NAME,
        "",
        key=key,
        path="/",
        expires_at=datetime.now() - timedelta(seconds=1),
        max_age=0,
        secure=bool(os.environ.get("RENDER_SERVICE_ID")),
        same_site="lax",
    )


def _set_browser_login_cookie(cookie_manager, token: str, key: str) -> None:
    cookie_manager.set(
        auth.SESSION_COOKIE_NAME,
        token,
        key=key,
        path="/",
        expires_at=datetime.now() + timedelta(seconds=auth.SESSION_COOKIE_MAX_AGE_SECONDS),
        max_age=auth.SESSION_COOKIE_MAX_AGE_SECONDS,
        secure=bool(os.environ.get("RENDER_SERVICE_ID")),
        same_site="lax",
    )


def _remember_browser_login(cookie_manager) -> None:
    try:
        token = auth.create_session_token()
    except (auth.AccountStoreError, ValueError) as error:
        st.warning(
            f"You are signed in, but this browser could not save your login: {error}"
        )
        return
    st.session_state.pop("auth_cookie_cleared", None)
    st.session_state["auth_cookie_initialized"] = True
    _set_browser_login_cookie(cookie_manager, token, "save_auth_session")


def current_policy() -> dialogue.Policy:
    """The confidence policy in force, built from the Settings sliders.

    Falls back to the documented defaults when the stored pair is invalid, so
    a bad value can never make the assistant answer everything or nothing.
    """
    answer_at = float(st.session_state.get("answer_threshold", dialogue.ANSWER_THRESHOLD))
    clarify_below = float(st.session_state.get("clarify_threshold", dialogue.CLARIFY_THRESHOLD))
    try:
        return dialogue.Policy(answer_threshold=answer_at, clarify_threshold=clarify_below)
    except ValueError:
        return dialogue.Policy()


def profile() -> dict | None:
    path = ROOT / "data" / "developer.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
def _render_student_document_preview(record: dict, content: bytes) -> None:
    """Inline preview of a shared document, with a graceful fallback by type."""
    suffix = Path(record.get("filename", "")).suffix.lower()
    try:
        if suffix == ".txt":
            text = content.decode("utf-8", errors="replace")
            st.text(text[:8000])
            if len(text) > 8000:
                st.caption("Showing the first 8,000 characters.")
        elif suffix == ".csv":
            frame = pd.read_csv(io.BytesIO(content), nrows=100)
            st.dataframe(frame, width="stretch")
        elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
            st.image(content)
        elif suffix == ".pdf":
            encoded = base64.b64encode(content).decode("ascii")
            st.components.v1.html(
                f'<iframe src="data:application/pdf;base64,{encoded}" '
                'width="100%" height="600" type="application/pdf"></iframe>',
                height=620,
                scrolling=True,
            )
        else:
            st.info(
                "Preview is not available for this file type. "
                "Download the file to open it."
            )
    except Exception as error:
        st.warning(f"Could not generate a preview: {error}")


def _render_student_shared_documents(student_id: str) -> None:
    st.markdown("## Shared Documents")
    st.caption("Documents shared with your account by school staff.")
    try:
        documents = staff_content.documents_for_student(student_id)
    except (OSError, ValueError) as error:
        st.error(f"Could not load shared documents: {error}")
        return

    if not documents:
        st.info("Documents shared with you will appear here.")
        return
    mime_types = {
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    for document in documents:
        try:
            record, content = staff_content.read_document_for_student(
                str(document.get("id", "")),
                student_id,
            )
        except PermissionError:
            st.warning("A document is no longer shared with your account.")
            continue
        except (OSError, ValueError) as error:
            st.error(f"Could not open a shared document: {error}")
            continue
        document_id = str(record.get("id", ""))
        suffix = Path(record.get("filename", "")).suffix.lower()
        download_col, remove_col = st.columns([4, 1], gap="small")
        with download_col:
            st.download_button(
                f"Download · {record.get('filename', 'Document')}",
                data=content,
                file_name=record.get("filename", "document"),
                mime=mime_types.get(suffix, "application/octet-stream"),
                key=f"student_shared_document_{document_id}",
                width="stretch",
            )
        with remove_col:
            if st.button(
                "🗑",
                key=f"student_remove_shared_document_{document_id}",
                help="Remove this document from your shared documents",
            ):
                st.session_state[f"confirm_remove_shared_document_{document_id}"] = True
                st.rerun()
        st.caption(f"{record.get('category', 'School document')} · {record.get('uploaded_at', '')[:10]}")
        with st.expander(f"View · {record.get('filename', 'Document')}"):
            _render_student_document_preview(record, content)
        confirmation_key = f"confirm_remove_shared_document_{document_id}"
        if st.session_state.get(confirmation_key):
            st.warning(
                f"Remove **{record.get('filename', 'this document')}** from your shared documents? "
                "You will lose access, but it will remain available to other students."
            )
            confirm_col, cancel_col = st.columns(2, gap="small")
            with confirm_col:
                if st.button(
                    "Remove access",
                    key=f"confirm_remove_shared_document_yes_{document_id}",
                    type="primary",
                    width="stretch",
                ):
                    try:
                        removed = staff_content.remove_shared_document_for_student(
                            document_id,
                            student_id,
                        )
                    except (OSError, PermissionError, ValueError) as error:
                        st.error(f"Could not remove the shared document: {error}")
                    else:
                        if removed:
                            st.session_state.pop(confirmation_key, None)
                            st.rerun()
                        else:
                            st.error("This document is no longer shared with your account.")
            with cancel_col:
                if st.button(
                    "Cancel",
                    key=f"confirm_remove_shared_document_no_{document_id}",
                    width="stretch",
                ):
                    st.session_state.pop(confirmation_key, None)
                    st.rerun()


def render_sidebar(cookie_manager) -> None:
    session: dialogue.Session = st.session_state.session
    unlocked = staff_gate.is_unlocked()
    logged_in = auth.is_logged_in()
    user_name = auth.get_current_user_name()
    user_id = auth.get_current_user_id()
    user_role = auth.get_current_user_role()
    profile_picture = auth.get_profile_picture(user_id) if logged_in and user_id else ""
    with st.sidebar:
        C.brand()
        if not auth.is_staff():
            mascot_html = C.mascot("GRA AI", ROOT / "assets" / "gra-ai.png")
            if mascot_html:
                st.html(mascot_html)

        # Auth section
        if logged_in:
            C.user_profile_card(user_name or user_id, user_role, online=True, profile_picture=profile_picture)
            if st.button("Logout", key="logout", width="stretch"):
                auth.logout(cookie_manager)
                st.session_state["auth_cookie_cleared"] = True
                st.session_state.pop("auth_cookie_initialized", None)
                st.session_state.view = "login"
                st.query_params["view"] = "login"
                st.rerun()
        else:
            C.nav_label("Account")
            for key, label, icon_name in AUTH_NAV:
                active = st.session_state.view == key
                if st.button(
                    label,
                    key=f"auth_{key}",
                    width="stretch",
                    type="primary" if active else "secondary",
                ):
                    st.session_state.view = key
                    st.query_params["view"] = key
                    st.rerun()

        # Only show navigation and session info when logged in
        if not logged_in:
            st.divider()
            st.caption("Please log in or create an account to access GRA SCHOOL.")
            return

        if auth.is_staff():
            C.nav_label("Staff Workspace")
            waiting_count = len(conversation.get_waiting_conversations())
            unanswered_count = sum(
                1 for row in logger.read_logs()
                if row.get("event") != "feedback" and not row.get("answered")
            )
            for key, label, icon_name in STAFF_NAV:
                if key == "staff_management" and not auth.is_admin():
                    continue
                badge_count = waiting_count if key == "inquiries" else unanswered_count if key == "review" else 0
                active = (
                    st.session_state.view == "settings" if key == "settings"
                    else st.session_state.view == "chat" if key == "chat"
                    else st.session_state.view == "dashboard"
                    and st.session_state.get("staff_section", "dashboard") == key
                )
                if C.nav_button(label, icon_name, active, key=f"staff_nav_{key}", badge=badge_count):
                    if key == "chat":
                        st.session_state.view = "chat"
                        st.query_params["view"] = "chat"
                    elif key == "settings":
                        st.session_state.view = "settings"
                        st.query_params["view"] = "settings"
                    else:
                        st.session_state["staff_section"] = key
                        st.session_state.view = "dashboard"
                        st.query_params["view"] = "dashboard"
                        st.query_params["section"] = key
                    st.rerun()

            mascot_html = C.mascot("GRA AI", ROOT / "assets" / "gra-ai.png")
            if mascot_html:
                st.html(mascot_html)
            st.caption("Staff-only workspace · student tools remain separate")
            return

        st.divider()

        # Navigation - dashboard only visible to staff
        C.nav_label("Navigation")
        for key, label, icon_name in NAV:
            active = st.session_state.view == key
            if st.button(
                label,
                key=f"nav_{key}",
                width="stretch",
                type="primary" if active else "secondary",
            ):
                st.session_state.view = key
                st.query_params["view"] = key
                st.rerun()

        if auth.is_student():
            recent_conversations = conversation.get_student_conversations(user_id or "")
            with st.expander(f"Recent conversations ({len(recent_conversations)})"):
                if not recent_conversations:
                    st.caption("Your conversations will appear here.")
                for item in recent_conversations[:10]:
                    session_id = str(item.get("session_id", ""))
                    status = (
                        "Resolved" if item.get("status") == "closed"
                        else str(item.get("status", "active")).capitalize()
                    )
                    messages = item.get("messages") or []
                    last_text = str(
                        messages[-1].get("text", "New conversation")
                        if messages else "New conversation"
                    ).replace("\n", " ").strip()
                    if len(last_text) > 38:
                        last_text = f"{last_text[:35]}..."
                    updated = str(item.get("updated_at", ""))[:16].replace("T", " ")
                    current = session_id == st.session_state.get("conversation_id")
                    open_col, delete_col = st.columns([5, 1], gap="small")
                    with open_col:
                        if st.button(
                            f"{'● ' if current else ''}{status} · {last_text}",
                            key=f"student_recent_nav_{session_id}",
                            width="stretch",
                            type="primary" if current else "secondary",
                            help=f"Open conversation from {updated}",
                        ):
                            if _open_student_conversation(user_id or "", session_id):
                                st.rerun()
                    with delete_col:
                        if st.button(
                            "🗑",
                            key=f"student_recent_delete_{session_id}",
                            help="Delete this conversation permanently",
                        ):
                            st.session_state[f"confirm_student_delete_{session_id}"] = True
                            st.rerun()

                    if st.session_state.get(f"confirm_student_delete_{session_id}", False):
                        st.warning(
                            f"Hide this {status.lower()} conversation from your list? "
                            "It will be removed from your Recent conversations but "
                            "kept for staff records."
                        )
                        confirm_col, cancel_col = st.columns(2, gap="small")
                        with confirm_col:
                            if st.button(
                                "Delete permanently",
                                key=f"confirm_student_delete_yes_{session_id}",
                                type="primary",
                                icon=":material/delete_forever:",
                                width="stretch",
                            ):
                                try:
                                    deleted = conversation.delete_own_conversation(session_id)
                                except (OSError, PermissionError, ValueError) as error:
                                    st.error(f"Could not delete the conversation: {error}")
                                else:
                                    if deleted:
                                        st.session_state.pop(
                                            f"confirm_student_delete_{session_id}", None
                                        )
                                        if current:
                                            st.session_state.conversation_id = None
                                            st.session_state.messages = []
                                            st.session_state.session = dialogue.new_session()
                                        st.rerun()
                                    else:
                                        st.error("This conversation is no longer available.")
                        with cancel_col:
                            if st.button(
                                "Cancel",
                                key=f"confirm_student_delete_no_{session_id}",
                                width="stretch",
                            ):
                                st.session_state.pop(
                                    f"confirm_student_delete_{session_id}", None
                                )
                                st.rerun()

        # Staff dashboard - only show if logged in as staff
        if auth.is_staff():
            # Check for waiting conversations
            waiting_count = len(conversation.get_waiting_conversations())
            dashboard_label = "Staff Dashboard"
            if waiting_count > 0:
                dashboard_label += f" ({waiting_count} waiting)"
            active = st.session_state.view == "dashboard"
            if st.button(
                dashboard_label,
                key="nav_dashboard",
                width="stretch",
                type="primary" if active else "secondary",
            ):
                st.session_state.view = "dashboard"
                st.query_params["view"] = "dashboard"
                st.rerun()

        st.divider()
        C.nav_label("This session")
        st.caption("What the assistant remembers while you chat. Nothing personal is stored.")
        if logged_in:
            st.markdown(f"**User:** {user_name or user_id} ({user_role})")
        st.markdown(f"**Student type:** {session.student_type or 'not stated yet'}")
        held = sorted(knowledge.DOCUMENT_LABELS.get(d, d) for d in session.documents_held)
        missing = sorted(knowledge.DOCUMENT_LABELS.get(d, d) for d in session.documents_missing)
        st.markdown(f"**Documents you have:** {', '.join(held) if held else 'none yet'}")
        st.markdown(f"**Documents missing:** {', '.join(missing) if missing else 'none yet'}")
        if session.fees_paid is not None:
            st.markdown(f"**Assessment fees:** {'paid' if session.fees_paid else 'not paid'}")

        if st.button("Start over", key="reset_session", width="stretch"):
            if logged_in and auth.is_student() and user_id:
                _start_new_student_chat(user_id, user_name)
            else:
                st.session_state.session = dialogue.new_session()
                st.session_state.messages = []
                st.session_state.conversation_id = None
                st.rerun()

        st.divider()
        # Utility views live below the staff entry, never in the main navigation.
        for key, label, icon_name in UTILITY_NAV:
            active = st.session_state.view == key
            if st.button(
                label,
                key=f"utility_{key}",
                width="stretch",
                type="primary" if active else "secondary",
            ):
                st.session_state.view = key
                st.query_params["view"] = key
                st.rerun()

        st.divider()
        st.caption(
            "Students use the AI Assistant and Voice Upload. Staff access the "
            "dashboard after logging in with a staff account."
        )


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
def _render_answer_meta(index: int, message: dict) -> None:
    meta = message.get("meta", {})
    confidence = meta.get("confidence") or 0.0
    kind = "good" if confidence >= 0.60 else "warn"

    cols = st.columns([1, 1, 1, 2])
    cols[0].markdown(C.badge(f"Confidence {confidence:.0%}", kind), unsafe_allow_html=True)
    if meta.get("rules_fired"):
        cols[1].markdown(
            C.badge(f"{len(meta['rules_fired'])} rules fired", "info"), unsafe_allow_html=True
        )
    if meta.get("escalated"):
        cols[2].markdown(C.badge("Handed off", "danger"), unsafe_allow_html=True)

    with st.expander("Why this answer?"):
        st.write(f"Intent: `{meta.get('intent')}`")
        st.write(f"Source: `{meta.get('source', '')}`")
        if meta.get("decisive") and 0 < confidence < 0.60:
            st.write(
                f"Answered without a clarifying question: the top intent led the "
                f"runner-up by {meta.get('margin', 0):.2f}."
            )
        if meta.get("blockers"):
            st.write("**Backward chaining - what is blocking you:**")
            for line in meta["blockers"]:
                st.write(f"- {line}")
        if meta.get("facts"):
            st.write("**Facts after forward chaining:**")
            st.write(
                ", ".join(
                    f"`{f[0]}({f[1]})`" if len(f) > 1 else f"`{f[0]}`" for f in meta["facts"]
                )
            )
        if meta.get("rules_fired"):
            st.write("**Rules fired:** " + ", ".join(meta["rules_fired"]))
        if meta.get("options"):
            st.write("**Options offered:** " + ", ".join(meta["options"]))

    up, down, refresh, _ = st.columns([1, 1, 1, 2])
    if up.button("Helpful", key=f"up_{index}"):
        if message.get("feedback") != "up":
            message["feedback"] = "up"
            dialogue.log_feedback(st.session_state.session, message["text"], "up")
            st.rerun()
    if down.button("Not helpful", key=f"down_{index}"):
        if message.get("feedback") != "down":
            message["feedback"] = "down"
            dialogue.log_feedback(st.session_state.session, message["text"], "down")
            st.rerun()
    if refresh.button("Refresh", key=f"refresh_conversation_{index}", icon=":material/refresh:"):
        conversation_id = st.session_state.get("conversation_id")
        if not auth.is_student() or not conversation_id:
            st.error("Sign in to the student account to refresh this conversation.")
        else:
            latest_conversation = conversation.get_conversation(conversation_id)
            if (
                latest_conversation is None
                or latest_conversation.get("student_id") != auth.get_current_user_id()
            ):
                st.error("This conversation is unavailable to the current account.")
            else:
                st.session_state.messages = latest_conversation.get("messages", [])
                st.rerun()
    if message.get("feedback"):
        st.caption("Thanks - your feedback is logged for the registrar staff.")


def _start_new_student_chat(student_id: str, student_name: str | None) -> None:
    """Start a fresh student conversation without changing resolved history."""
    new_session = dialogue.new_session()
    try:
        new_conversation = conversation.create_conversation(
            student_id,
            student_name,
            session_id=new_session.session_id,
        )
    except OSError as error:
        st.error(f"Could not start a new conversation: {error}")
        return
    except ValueError as error:
        st.error(f"Could not start a new conversation: {error}")
        return

    st.session_state.conversation_id = new_conversation["session_id"]
    st.session_state.session = new_session
    st.session_state.messages = new_conversation.get("messages", [])
    st.session_state.pop("pending", None)
    st.rerun()


def _open_student_conversation(student_id: str, conversation_id: str) -> bool:
    """Open a conversation only when it belongs to the authenticated student."""
    if not auth.is_student() or auth.get_current_user_id() != student_id:
        st.error("Sign in to the student account that owns this conversation.")
        return False
    selected = next(
        (
            item for item in conversation.get_student_conversations(student_id)
            if item.get("session_id") == conversation_id
        ),
        None,
    )
    if selected is None:
        st.error("That conversation is unavailable.")
        return False
    st.session_state.conversation_id = selected["session_id"]
    st.session_state.session = dialogue.new_session()
    st.session_state.session.session_id = selected["session_id"]
    st.session_state.messages = selected.get("messages", [])
    st.session_state.pop("pending", None)
    return True


def _request_staff_response(conversation_id: str) -> None:
    try:
        updated, notice = handoff.request_staff_response(conversation_id)
    except (OSError, PermissionError, ValueError) as error:
        st.error(f"Could not request a staff response: {error}")
        return
    st.session_state.messages = updated.get("messages", []) + [notice]
    st.rerun()


def _apply_staff_quick_reply(conversation_id: str) -> None:
    selected_template = st.session_state.get(f"quick_{conversation_id}")
    if selected_template:
        st.session_state[f"staff_reply_{conversation_id}"] = selected_template


@st.fragment(run_every=5)
def _poll_staff_response_timeout(conversation_id: str, student_id: str) -> None:
    conv = conversation.get_conversation(conversation_id)
    if not conv or conv.get("student_id") != student_id:
        return
    waiting_since = conv.get("waiting_since")
    if not isinstance(waiting_since, str):
        return
    remaining = conversation.staff_response_seconds_remaining(conv)
    if remaining is None:
        return
    online_staff = conversation.get_available_staff()
    if online_staff:
        staff_names = ", ".join(
            str(member.get("staff_name") or member.get("staff_id") or "Staff")
            for member in online_staff
        )
        st.caption(
            f"Waiting for an online staff member ({staff_names}) to reply. "
            "Your question will stay in the staff queue."
        )
        return
    if remaining > 0:
        minutes, seconds = divmod(remaining, 60)
        st.caption(
            f"Waiting for staff · GRA AI will answer in {minutes}:{seconds:02d} "
            "if no staff member replies."
        )
        return

    try:
        saved = handoff.generate_timeout_fallback(
            conversation_id,
            student_id,
            current_policy(),
        )
    except (OSError, PermissionError, ValueError, RuntimeError) as error:
        st.error(f"GRA AI could not take over the unanswered request: {error}")
        return
    if saved is not None:
        st.rerun()


def render_chat() -> None:
    school = knowledge.load()["meta"]["school"]
    C.hero(
        "AI Assistant",
        f"Ask anything about enrollment, requirements, fees, clearance or your "
        f"documents. Answers come from the {school} rule base and knowledge base, "
        "with a confidence score and the source shown.",
    )
    active_announcements = [
        row for row in staff_content.load_announcements()
        if row.get("status") in {"published", "scheduled"}
        and row.get("publish_on", "") <= datetime.now().date().isoformat()
    ]
    if active_announcements:
        with st.expander(f"School announcements ({len(active_announcements)})", expanded=True):
            for announcement in active_announcements:
                st.markdown(f"**{announcement.get('title', 'School update')}**")
                st.write(announcement.get("body", ""))
                if announcement.get("publish_on"):
                    st.caption(f"Published {announcement['publish_on']}")

    logged_in = auth.is_logged_in()
    student_id = auth.get_current_user_id() if logged_in else None
    student_name = auth.get_current_user_name() if logged_in else None
    chat_principal = (
        auth.get_current_user_role() if logged_in else None,
        student_id,
    )
    if st.session_state.get("chat_principal") != chat_principal:
        st.session_state["chat_principal"] = chat_principal
        st.session_state.conversation_id = None
        st.session_state.messages = []
        st.session_state.session = dialogue.new_session()
    session: dialogue.Session = st.session_state.session

    # Get or create conversation for this student
    if logged_in and auth.is_student() and student_id:
        if not st.session_state.conversation_id:
            conv = conversation.get_student_conversation(student_id)
            if conv:
                st.session_state.conversation_id = conv["session_id"]
            else:
                conv = conversation.create_conversation(
                    student_id,
                    student_name,
                    session_id=session.session_id,
                )
                st.session_state.conversation_id = conv["session_id"]
        
        # Load messages from conversation
        conv = conversation.get_conversation(st.session_state.conversation_id)
        if conv and conv.get("student_id") == student_id:
            st.session_state.messages = conv["messages"]
            session.session_id = conv["session_id"]
        else:
            st.session_state.conversation_id = None
            st.session_state.messages = []
            st.rerun()
    elif not auth.is_student():
        st.session_state.conversation_id = None

    # Show connection status
    current_conversation = None
    if logged_in and auth.is_student() and st.session_state.conversation_id:
        current_conversation = conversation.get_conversation(st.session_state.conversation_id)
        if current_conversation and current_conversation.get("student_id") == student_id:
            status = current_conversation.get("status", "active")
            waiting_for_staff_reply = bool(current_conversation.get("waiting_since"))
            if waiting_for_staff_reply:
                _poll_staff_response_timeout(
                    current_conversation["session_id"],
                    student_id,
                )
                st.info(
                    "🕐 **Your request is in the staff queue.** Online staff can reply here; "
                    "GRA AI will answer after 5 seconds if no staff are available."
                )
            elif status == "waiting":
                st.info("🕐 **Waiting for staff response...** Your message is in the staff queue.")
            elif (
                status == "active"
                and current_conversation.get("assigned_staff")
                and staff_presence.is_staff_online(current_conversation["assigned_staff"])
            ):
                st.success("🟢 **Connected with staff** - You can chat with a registrar staff member now.")
            elif status == "active" and current_conversation.get("assigned_staff"):
                st.info(
                    "📨 **Staff assigned** - They are currently offline. "
                    "Your messages will stay in the staff queue."
                )
            elif status == "active":
                st.info("💬 **AI Assistant active** - Type your question below or ask for a staff member.")
            elif status == "closed":
                st.success("✅ **Conversation resolved** - Start a new chat whenever you're ready.")
                if student_id and st.button(
                    "Start over",
                    key="start_new_chat_after_resolution",
                    type="primary",
                    icon=":material/add_comment:",
                ):
                    _start_new_student_chat(student_id, student_name)
        else:
            # Conversation was deleted - show fresh start message
            st.info("💬 **New conversation started** - How can I help you today?")

    conversation_resolved = bool(
        current_conversation and current_conversation.get("status") == "closed"
    )
    if not st.session_state.messages and not conversation_resolved:
        st.markdown("##### Suggested questions")
        cols = st.columns(2)
        for i, (label, prompt) in enumerate(SAMPLE_PROMPTS):
            with cols[i % 2]:
                if st.button(label, key=f"sample_{i}", width="stretch"):
                    st.session_state.pending = prompt
                    st.rerun()

    # Render all messages from conversation
    # Get profile pictures
    student_profile_pic = auth.get_profile_picture(student_id) if student_id else ""
    # Get assigned staff profile picture if available
    assigned_staff_id = current_conversation.get("assigned_staff") if current_conversation else None
    assigned_staff_profile_pic = auth.get_profile_picture(assigned_staff_id) if assigned_staff_id else ""
    
    for index, message in enumerate(st.session_state.messages):
        role = message.get("role", "assistant")
        if role in {"user", "student"}:
            with st.chat_message("user", avatar=student_profile_pic or "👤"):
                C.user_bubble(message["text"], message.get("timestamp", "")[:5] if message.get("timestamp") else "")
                if message.get("audio"):
                    st.audio(message["audio"], format="audio/wav")
        elif role == "staff":
            # Use the message's sender_name to find their profile picture
            sender_name = message.get("sender_name", "")
            sender_id = message.get("sender_id", "")
            staff_pic = auth.get_profile_picture(sender_id) if sender_id else assigned_staff_profile_pic
            with st.chat_message("assistant", avatar=staff_pic or "👨‍💼"):
                st.markdown(f"**Staff:** {message['text']}")
                if message.get("timestamp"):
                    st.caption(f"Sent at {message['timestamp'][:19].replace('T', ' ')}")
        else:  # assistant
            with st.chat_message("assistant", avatar="🤖"):
                C.bot_bubble(message["text"])
                if message.get("meta") and message["meta"].get("intent") != "voice_recording":
                    _render_answer_meta(index, message)
                response_meta = message.get("meta", {})
                can_request_staff = bool(
                    current_conversation
                    and current_conversation.get("status") == "active"
                    and not current_conversation.get("assigned_staff")
                    and (
                        response_meta.get("answered") is False
                        or response_meta.get("escalated")
                    )
                )
                if can_request_staff and auth.is_student():
                    online_staff = conversation.get_available_staff()
                    if online_staff:
                        names = ", ".join(
                            str(member.get("staff_name") or member.get("staff_id") or "Staff")
                            for member in online_staff
                        )
                        st.caption(
                            f"GRA AI could not answer this question. Online staff: {names}. "
                            "Send it to the staff queue for a reply."
                        )
                    else:
                        st.caption(
                            "GRA AI could not answer this question. No staff are online now, "
                            "but you can still send it to the staff queue."
                        )
                    if st.button(
                        "Ask online staff to answer" if online_staff else "Send to staff queue",
                        key=f"request_staff_{current_conversation['session_id']}_{index}",
                        icon=":material/support_agent:",
                        type="primary",
                    ):
                        _request_staff_response(current_conversation["session_id"])

    if conversation_resolved:
        st.caption("This resolved conversation is read-only. Start a new chat to send another message.")
    else:
        # Microphone / Voice recorder tool directly above chat input
        voice_col1, voice_col2 = st.columns([1, 4])
        with voice_col1:
            with st.popover("🎙️ Voice / Mic", help="Record audio using your microphone"):
                st.markdown("##### 🎙️ Voice Recorder")
                st.caption("Record your question or voice message. The audio will be played back in the chat.")
                voice_clip = st.audio_input("Record voice question", key="chat_voice_mic", label_visibility="collapsed")
                if voice_clip is not None:
                    st.audio(voice_clip, format="audio/wav")
                    if st.button("Send Voice to Chat 🚀", key="chat_send_voice_btn", type="primary", width="stretch"):
                        audio_raw = voice_clip.getvalue()
                        st.session_state.messages.append(
                            {
                                "role": "user",
                                "text": "🎙️ [Voice Question Recorded]",
                                "audio": audio_raw,
                                "timestamp": datetime.now().isoformat(timespec="seconds"),
                            }
                        )
                        if st.session_state.conversation_id:
                            conversation.add_message(
                                st.session_state.conversation_id,
                                "student",
                                "🎙️ [Voice Question Recorded]",
                                sender_id=student_id,
                                sender_name=student_name,
                            )
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "text": (
                                    "🎙️ **Voice recording received and played back!** You can replay your audio above.\n\n"
                                    "💡 *Tip: Our cognitive handbook rules provide instant verified answers for typed queries. "
                                    "Type your question in the text box below to view your confidence score, official requirements, and eligibility rules.*"
                                ),
                                "timestamp": datetime.now().isoformat(timespec="seconds"),
                                "meta": {
                                    "intent": "voice_recording",
                                    "confidence": 1.0,
                                    "source": "microphone - browser audio",
                                    "rules_fired": [],
                                    "facts": {},
                                },
                                "feedback": None,
                            }
                        )
                        if st.session_state.conversation_id:
                            conversation.add_message(
                                st.session_state.conversation_id,
                                "assistant",
                                "🎙️ Voice recording received and played back!",
                            )
                        st.rerun()

        with voice_col2:
            st.caption("💡 *Click 🎙️ **Voice / Mic** to record your voice or type your question below.*")

        prompt = st.session_state.pop("pending", None)
        typed = st.chat_input("Type your message here...")
        if typed:
            prompt = typed

    if not conversation_resolved and prompt:
        ts = datetime.now().isoformat(timespec="seconds")
        if st.session_state.conversation_id:
            try:
                student_message = conversation.add_message(
                    st.session_state.conversation_id,
                    "student",
                    prompt,
                    sender_id=student_id,
                    sender_name=student_name,
                )
            except (OSError, PermissionError, ValueError) as error:
                st.error(f"Could not send your message: {error}")
                return
            if student_message is None:
                st.error("This conversation is no longer available. Open a recent chat or start over.")
                return
            message_timestamp = student_message["timestamp"]
        else:
            message_timestamp = ts
        st.session_state.messages.append(
            {"role": "user", "text": prompt, "timestamp": message_timestamp}
        )

        assigned_staff = (
            current_conversation.get("assigned_staff")
            if current_conversation else None
        )
        waiting_for_staff = bool(
            current_conversation
            and current_conversation.get("status") == "waiting"
        )
        route_to_staff = bool(assigned_staff or waiting_for_staff)
        staff_online = bool(
            assigned_staff and staff_presence.is_staff_online(assigned_staff)
        )

        if route_to_staff and st.session_state.conversation_id:
            if not staff_online and current_conversation.get("status") != "waiting":
                try:
                    conversation.update_conversation_status(
                        st.session_state.conversation_id, "waiting"
                    )
                except (OSError, PermissionError, ValueError) as error:
                    st.error(f"Your message was saved, but staff routing failed: {error}")
                    return

            notice = (
                "📩 Your message was sent to the assigned staff member, who is online."
                if staff_online
                else (
                    "📩 Your message is saved in the assigned staff member's queue. They are currently offline."
                    if assigned_staff
                    else "📩 Your message is saved in the staff queue for review."
                )
            )
            try:
                stored_notice = conversation.add_message(
                    st.session_state.conversation_id,
                    "assistant",
                    notice,
                    meta={
                        "intent": "staff_notified",
                        "source": "conversation - staff routing",
                    },
                )
            except (OSError, PermissionError, ValueError) as error:
                st.error(f"Your message was saved, but the staff notice failed: {error}")
                return
            if stored_notice is None:
                st.error("Your message was saved, but the conversation is unavailable.")
                return
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "text": notice,
                    "timestamp": stored_notice["timestamp"],
                    "meta": stored_notice["meta"],
                    "feedback": None,
                }
            )
        else:
            try:
                reply = dialogue.handle(
                    prompt,
                    session,
                    policy=current_policy(),
                    student_id=student_id if auth.is_student() else None,
                    student_name=student_name if auth.is_student() else None,
                )
            except (OSError, ValueError, RuntimeError) as error:
                st.error(f"The assistant could not answer right now: {error}")
                return

            reply_timestamp = datetime.now().isoformat(timespec="seconds")
            reply_meta = {
                "intent": reply.intent,
                "confidence": reply.confidence,
                "source": reply.source,
                "rules_fired": reply.rules_fired,
                "facts": reply.facts,
                "blockers": reply.blockers,
                "clarified": reply.clarified,
                "escalated": reply.escalated,
                "sentiment": reply.sentiment,
                "answered": reply.answered,
                "options": reply.options,
                "decisive": reply.decisive,
                "margin": reply.margin,
            }
            if st.session_state.conversation_id:
                try:
                    stored_reply = conversation.add_message(
                        st.session_state.conversation_id,
                        "assistant",
                        reply.text,
                        meta={
                            "intent": reply.intent,
                            "confidence": reply.confidence,
                            "source": reply.source,
                            "escalated": reply.escalated,
                            "answered": reply.answered,
                        },
                    )
                except (OSError, PermissionError, ValueError) as error:
                    st.error(f"The answer was generated but could not be saved: {error}")
                    return
                if stored_reply is None:
                    st.error("The answer was generated but the conversation is unavailable.")
                    return
                reply_timestamp = stored_reply["timestamp"]

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "text": reply.text,
                    "timestamp": reply_timestamp,
                    "meta": reply_meta,
                    "feedback": None,
                }
            )

        st.rerun()


# --------------------------------------------------------------------------
# Voice
# --------------------------------------------------------------------------
def render_voice() -> None:
    C.hero(
        "Voice Upload",
        "Record your question or upload an audio file with the browser microphone. "
        "The clip is played back here; type the question in the AI Assistant to get "
        "an answer.",
    )

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("##### Record voice")
        st.caption("Click start, speak, then stop. The clip stays in your browser.")
        clip = st.audio_input("Record a question", key="recorder")
        if clip is not None:
            st.audio(clip, format="audio/wav")
            st.caption(f"Recorded {len(clip.getvalue()) / 1024:.0f} KB")

    with right:
        st.markdown("##### Upload an audio file")
        st.caption("WAV, MP3, M4A or WEBM.")
        uploaded = st.file_uploader(
            "Drag and drop an audio file here",
            type=["wav", "mp3", "m4a", "webm"],
            key="audio_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            st.audio(uploaded, format=uploaded.type)
            st.caption(f"{uploaded.name} - {uploaded.size / 1024:.0f} KB")

    if clip is None and uploaded is None:
        st.info("Record or upload a clip to play it back here.")
        return

    st.divider()
    st.caption(
        "The assistant answers typed questions. Type what you asked in the "
        "AI Assistant page and it will answer with the same rules and knowledge base."
    )
    if st.button("Go to the AI Assistant", type="primary"):
        st.session_state.view = "chat"
        st.query_params["view"] = "chat"
        st.rerun()


# --------------------------------------------------------------------------
# Staff dashboard
# --------------------------------------------------------------------------
def _chart_theme() -> dict:
    """Altair config matching the dark palette.

    Streamlit's built-in charts render to canvas and ignore CSS, so they stay
    a white box on this canvas. Altair renders to SVG, which does take the
    palette - that is why the charts are built here instead of st.line_chart.
    """
    return {
        "config": {
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "axis": {
                "labelColor": "#A3B0D4",
                "titleColor": "#A3B0D4",
                "domainColor": "rgba(122,146,214,0.35)",
                "gridColor": "rgba(122,146,214,0.14)",
                "tickColor": "rgba(122,146,214,0.35)",
                "labelFont": "Inter",
                "titleFont": "Inter",
                "labelFontSize": 11,
            },
            "legend": {"labelColor": "#A3B0D4", "titleColor": "#A3B0D4"},
        }
    }


def weekly_chart(weekly: dict):
    """Weekly question volume as a themed area line."""
    frame = pd.DataFrame({"week": list(weekly), "questions": list(weekly.values())})
    return (
        alt.Chart(frame)
        .mark_area(
            line={"color": "#2F6BFF", "strokeWidth": 2.4},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="rgba(47,107,255,0.42)", offset=0),
                    alt.GradientStop(color="rgba(47,107,255,0.02)", offset=1),
                ],
                x1=1, x2=1, y1=1, y2=0,
            ),
            interpolate="monotone",
        )
        .encode(
            x=alt.X("week:N", title=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("questions:Q", title="Questions"),
            tooltip=["week", "questions"],
        )
        .properties(height=260)
        .configure(**_chart_theme()["config"])
    )


def topic_chart(intents: dict):
    """Questions per category as a themed horizontal bar chart."""
    frame = pd.DataFrame(
        {
            "topic": [INTENT_LABELS.get(k, k) for k in intents],
            "count": list(intents.values()),
        }
    ).sort_values("count", ascending=False)
    return (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=6, height=18)
        .encode(
            y=alt.Y("topic:N", title=None, sort="-x"),
            x=alt.X("count:Q", title="Questions"),
            color=alt.Color(
                "count:Q",
                scale=alt.Scale(range=["#2F6BFF", "#6D4AFF", "#8B5CF6"]),
                legend=None,
            ),
            tooltip=["topic", "count"],
        )
        .properties(height=260)
        .configure(**_chart_theme()["config"])
    )


def render_dashboard() -> None:
    section = str(st.session_state.get("staff_section", "dashboard"))
    if section == "staff_management":
        staff_workspace.render_staff_management(_log_audit)
        return
    if section == "inquiries":
        inquiries_tab, assistant_tab = st.tabs(
            ["Student Inquiries", "Staff AI Assistant"]
        )
        with inquiries_tab:
            _render_staff_chat()
        with assistant_tab:
            render_chat()
        return
    staff_workspace.render(section, _log_audit, _render_staff_chat)


def _render_staff_chat() -> None:
    """Real-time chat interface for staff to communicate with students."""
    heading = st.session_state.pop("staff_chat_heading", "Student Inquiries")
    st.markdown(f"## {html.escape(str(heading))}")
    staff_id = auth.get_current_user_id()
    staff_name = auth.get_current_user_name() or staff_id

    # Send heartbeat to mark staff as online
    staff_presence.staff_heartbeat(staff_id, staff_name)

    # Get all conversations
    conversations = conversation.get_all_conversations()
    
    # Separate by status
    waiting = [c for c in conversations if c.get("status") == "waiting"]
    active = [c for c in conversations if c.get("status") == "active"]
    closed = [c for c in conversations if c.get("status") == "closed"]

    # Show online staff count
    online_staff = staff_presence.get_online_staff()
    
    st.markdown("##### Active Conversations")
    
    # Summary metrics with online staff indicator
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        C.kpi("Waiting for Response", len(waiting))
    with c2:
        C.kpi("Active Chats", len(active))
    with c3:
        C.kpi("Resolved", len(closed))
    with c4:
        C.kpi("Staff Online", len(online_staff), "🟢" if online_staff else "🔴")

    # Show online staff names
    if online_staff:
        staff_names = ", ".join([s["staff_name"] for s in online_staff])
        st.caption(f"🟢 Online staff: {staff_names}")
    else:
        st.caption("🔴 No staff currently online - AI will handle student messages")

    # Conversation list
    all_convs = waiting + active + closed
    
    if not all_convs:
        st.info("No conversations yet. Students will appear here when they request a staff member.")
        return

    # Create a selectbox for conversation selection
    conv_options = []
    for conv in all_convs:
        summary = conversation.get_conversation_summary(conv)
        status_icon = (
            "🔴" if summary["status"] == "waiting"
            else "🟢" if summary["status"] == "active"
            else "✅"
        )
        staff_icon = "🟢" if summary.get("staff_online") else ("🔴" if summary.get("assigned_staff") else "⚪")
        label = f"{status_icon}{staff_icon} {summary['student_name']} ({summary['student_id']}) - {summary['last_message'][:40]}... ({summary['message_count']} msgs)"
        conv_options.append((summary["session_id"], label))

    selected_session_id = st.selectbox(
        "Select a conversation",
        options=[c[0] for c in conv_options],
        format_func=lambda x: next((c[1] for c in conv_options if c[0] == x), x),
        key="staff_conv_select"
    )

    if not selected_session_id:
        return

    conv = conversation.get_conversation(selected_session_id)
    if not conv:
        st.error("Conversation not found")
        return

    summary = conversation.get_conversation_summary(conv)
    
    # Conversation header with status controls
    assigned_staff = conv.get("assigned_staff")
    staff_online = False
    if assigned_staff:
        staff_online = staff_presence.is_staff_online(assigned_staff)
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"**{summary['student_name']}** (`{summary['student_id']}`) — {summary['message_count']} messages")
        display_status = "Resolved" if summary["status"] == "closed" else summary["status"].capitalize()
        status_parts = [f"Status: {display_status}"]
        if assigned_staff:
            status_parts.append(f"Assigned: {summary.get('assigned_staff', 'unknown')}")
            status_parts.append(f"Staff: {'🟢 Online' if staff_online else '🔴 Offline'}")
        status_parts.append(f"Started: {summary['created_at'][:19].replace('T', ' ')}")
        status_parts.append(f"Last: {summary['updated_at'][:19].replace('T', ' ')}")
        st.caption(" • ".join(status_parts))
    
    if summary["status"] == "closed":
        st.success("✅ Resolved — this conversation remains available in staff history.")
    else:
        with col2:
            status_options = ["active", "waiting"]
            new_status = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(summary["status"]),
                key=f"status_{selected_session_id}",
            )
            if new_status != summary["status"]:
                try:
                    conversation.update_conversation_status(
                        selected_session_id, new_status, staff_id
                    )
                except (OSError, PermissionError, ValueError) as error:
                    st.error(f"Could not update inquiry status: {error}")
                else:
                    _log_audit(f"Changed inquiry status to {new_status}", staff_name)
                    st.rerun()

        with col3:
            if assigned_staff == staff_id:
                st.success("You are handling this inquiry.")
            elif not assigned_staff or not staff_online:
                if st.button("Take Over", key=f"takeover_{selected_session_id}", type="primary", width="stretch"):
                    try:
                        assigned = conversation.assign_staff_to_conversation(
                            selected_session_id, staff_id, staff_name
                        )
                    except (OSError, PermissionError, ValueError) as error:
                        st.error(f"Could not take over this inquiry: {error}")
                    else:
                        if assigned:
                            _log_audit("Assigned a student inquiry", staff_name)
                            st.rerun()
                        else:
                            st.error(
                                "This inquiry is no longer available, has been resolved, "
                                "or is being handled by another online staff member."
                            )

            if st.session_state.get(f"confirm_close_{selected_session_id}", False):
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Confirm resolve", key=f"confirm_yes_{selected_session_id}", type="primary", width="stretch"):
                        try:
                            resolved = conversation.update_conversation_status(
                                selected_session_id, "closed", staff_id
                            )
                        except (OSError, PermissionError, ValueError) as error:
                            st.error(f"Could not resolve this inquiry: {error}")
                        else:
                            if resolved:
                                _log_audit("Resolved a student inquiry", staff_name)
                                st.session_state[f"confirm_close_{selected_session_id}"] = False
                                st.rerun()
                            else:
                                st.error("This inquiry is no longer available.")
                with col_b:
                    if st.button("Cancel", key=f"confirm_no_{selected_session_id}", width="stretch"):
                        st.session_state[f"confirm_close_{selected_session_id}"] = False
                        st.rerun()
            elif st.button("Resolve inquiry", key=f"close_{selected_session_id}", type="secondary", width="stretch"):
                st.session_state[f"confirm_close_{selected_session_id}"] = True
                st.rerun()

    if st.session_state.get(f"confirm_delete_{selected_session_id}", False):
        st.warning(
            "This permanently deletes the selected conversation and its inquiry-log records. "
            "The student's account will not be deleted."
        )
        delete_col, cancel_col = st.columns(2)
        with delete_col:
            if st.button(
                "Confirm permanent delete",
                key=f"confirm_delete_yes_{selected_session_id}",
                type="primary",
                icon=":material/delete_forever:",
                width="stretch",
            ):
                try:
                    deleted = conversation.delete_conversation(selected_session_id)
                except (OSError, PermissionError, ValueError) as error:
                    st.error(f"Could not delete the conversation: {error}")
                else:
                    if deleted:
                        _log_audit(
                            f"Permanently deleted student conversation {selected_session_id}",
                            staff_name,
                        )
                        st.session_state.pop(f"confirm_delete_{selected_session_id}", None)
                        st.session_state.pop("staff_conv_select", None)
                        st.success("Conversation permanently deleted.")
                        st.rerun()
                    else:
                        st.error("This conversation was already deleted or is no longer available.")
        with cancel_col:
            if st.button(
                "Cancel delete",
                key=f"confirm_delete_no_{selected_session_id}",
                width="stretch",
            ):
                st.session_state.pop(f"confirm_delete_{selected_session_id}", None)
                st.rerun()
    elif st.button(
        "Delete conversation",
        key=f"delete_conversation_{selected_session_id}",
        type="secondary",
        icon=":material/delete:",
    ):
        st.session_state[f"confirm_delete_{selected_session_id}"] = True
        st.rerun()

    st.divider()

    # Chat messages
    st.markdown("##### Conversation")
    
    # Get profile pictures
    student_id = conv.get("student_id", "")
    student_profile_pic = auth.get_profile_picture(student_id) if student_id else ""
    staff_profile_pic = auth.get_profile_picture(staff_id) if staff_id else ""
    
    # Display messages
    for msg in conv.get("messages", []):
        role = msg.get("role", "assistant")
        text = msg.get("text", "")
        timestamp = msg.get("timestamp", "")
        sender_name = msg.get("sender_name", "")
        meta = msg.get("meta", {})
        
        if role == "student":
            with st.chat_message("user", avatar=student_profile_pic or "👤"):
                st.markdown(f"**{sender_name or 'Student'}**")
                st.markdown(text)
                if timestamp:
                    st.caption(timestamp[:19].replace('T', ' '))
        elif role == "staff":
            with st.chat_message("assistant", avatar=staff_profile_pic or "👨‍💼"):
                st.markdown(f"**Staff: {sender_name or staff_name}**")
                st.markdown(text)
                if timestamp:
                    st.caption(timestamp[:19].replace('T', ' '))
        else:  # assistant
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(f"**GRA AI**")
                st.markdown(text)
                if meta.get("intent") and meta.get("intent") != "voice_recording":
                    conf = meta.get("confidence", 0)
                    conf_color = "green" if conf >= 0.6 else ("orange" if conf >= 0.4 else "red")
                    st.caption(f"Intent: {meta.get('intent')} • Confidence: :{conf_color}[{conf:.0%}] • Source: {meta.get('source', 'unknown')}")
                if timestamp:
                    st.caption(timestamp[:19].replace('T', ' '))

    st.divider()

    # Staff reply input
    if summary["status"] != "closed":
        if assigned_staff != staff_id:
            st.info("Click **Take Over** before replying to this student.")
        else:
            reply_heading, refresh_col = st.columns([5, 1], vertical_alignment="center")
            reply_heading.markdown("##### Reply as Staff")
            if refresh_col.button(
                "Refresh",
                key=f"refresh_{selected_session_id}",
                icon=":material/refresh:",
                width="stretch",
                help="Check for new messages from the student.",
            ):
                st.rerun()
            quick_replies = [
                "Hello! I'm a registrar staff member. How can I help you?",
                "I've checked your records and here's what I found...",
                "Please visit the Registrar's Office at Main Building Room 101 during office hours.",
                "Your request has been processed. You'll receive a confirmation email shortly.",
                "Let me transfer you to the appropriate department.",
            ]
            st.selectbox(
                "Quick reply",
                [""] + quick_replies,
                key=f"quick_{selected_session_id}",
                on_change=_apply_staff_quick_reply,
                args=(selected_session_id,),
                help="Choose a template to place it in Your response.",
            )
            reply_text = st.text_area("Your response", key=f"staff_reply_{selected_session_id}", height=100)
            col1, _ = st.columns([1, 4])
            with col1:
                if st.button("Send reply", key=f"send_{selected_session_id}", type="primary", width="stretch"):
                    if reply_text.strip():
                        try:
                            message = conversation.add_message(
                                selected_session_id,
                                "staff",
                                reply_text.strip(),
                                sender_id=staff_id,
                                sender_name=staff_name,
                            )
                        except (OSError, PermissionError, ValueError) as error:
                            st.error(f"Could not send your reply: {error}")
                        else:
                            if message is None:
                                st.error("This inquiry is no longer available.")
                            else:
                                _log_audit("Replied to a student inquiry", staff_name)
                                st.rerun()
                    else:
                        st.warning("Please enter a message")


def _unanswered_table_html(rows: list[dict]) -> str:
    """Unanswered rows as a themed HTML table.

    st.dataframe draws on Streamlit's own light surface, which app CSS cannot
    reach - the result is dark text on white rows inside a dark dashboard. A
    plain table keeps the palette and stays readable.
    """
    if not rows:
        return "<p class='cca-source'>No rows to show.</p>"
    head = "".join(
        f"<th>{h}</th>" for h in ("When", "Question", "Guessed intent", "Confidence", "Source")
    )
    body = []
    for row in rows:
        confidence = row.get("confidence")
        conf_text = f"{confidence:.0%}" if isinstance(confidence, (int, float)) else "-"
        kind = "warn" if row.get("source") == "sample seed" else "info"
        source_badge = (
            f"<span class='cca-badge cca-badge--{kind}'>{row.get('source')}</span>"
        )
        body.append(
            "<tr>"
            f"<td class='cca-td-ts'>{html.escape(str(row.get('when', '')))}</td>"
            f"<td>{html.escape(str(row.get('question', '')))}</td>"
            f"<td>{html.escape(str(row.get('guessed intent', '')))}</td>"
            f"<td class='cca-td-conf'>{conf_text}</td>"
            f"<td>{source_badge}</td>"
            "</tr>"
        )
    return (
        "<div class='cca-table-wrap'><table class='cca-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )


def _live_conversations_table_html(rows: list[dict]) -> str:
    """Live conversations as a themed HTML table."""
    if not rows:
        return "<p class='cca-source'>No conversations to show.</p>"
    head = "".join(
        f"<th>{h}</th>" for h in ("Student", "Status", "Assigned Staff", "Messages", "Last Message", "Time", "Session")
    )
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('student', '')))}</td>"
            f"<td>{row.get('status', '')}</td>"
            f"<td>{html.escape(str(row.get('staff', '')))}</td>"
            f"<td class='cca-td-conf'>{html.escape(str(row.get('messages', '')))}</td>"
            f"<td>{html.escape(str(row.get('last_message', '')))}</td>"
            f"<td class='cca-td-ts'>{html.escape(str(row.get('last_time', '')))}</td>"
            f"<td class='cca-td-ts'>{html.escape(str(row.get('session_id', '')))}</td>"
            "</tr>"
        )
    return (
        "<div class='cca-table-wrap'><table class='cca-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )


def _dashboard_body() -> None:
    logs = logger.read_logs()
    questions = [row for row in logs if row.get("event") != "feedback"]

    if not logs:
        st.info(
            "No questions logged yet. The log fills up as students use the chat. "
            "Run `python scripts/seed_sample_logs.py` to see the dashboard with sample data."
        )
        return

    C.sample_data_warning(sum(1 for row in questions if row.get("synthetic")), len(questions))

    answered = sum(1 for row in questions if row.get("answered"))
    intents = forecast.intent_counts(questions)
    top_intent = next(iter(intents), "-")
    weekly = forecast.forecast_next_week(questions)
    missed = forecast.unanswered(questions)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        C.kpi("Total questions", len(questions))
    with k2:
        C.kpi("Answered", f"{answered / len(questions):.0%}" if questions else "-")
    with k3:
        C.kpi("Unanswered", len(missed))
    with k4:
        C.kpi("Next week forecast", f"{weekly['forecast']:.0f}", "moving average, last 3 weeks")

    st.markdown("")
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown("##### Questions per week")
        weekly_counts = forecast.weekly_counts(questions)
        if weekly_counts:
            st.altair_chart(weekly_chart(weekly_counts), width="stretch")
    with right:
        st.markdown("##### Top question categories")
        if intents:
            st.altair_chart(topic_chart(intents), width="stretch")

    st.markdown("")
    recommendation = forecast.recommend(questions)
    st.markdown("##### Recommendation")
    C.card(
        f"<p style='margin:0 0 8px 0;font-weight:600;font-size:1.02rem'>"
        f"{recommendation['headline']}</p>"
        f"<p style='margin:0 0 10px 0;color:#A3B0D4;font-size:0.88rem'>"
        f"{recommendation['evidence']}</p>"
        f"<p style='margin:0;font-size:0.88rem'><strong>Next action:</strong> "
        f"{recommendation['action']}</p>"
        f"<p style='margin:8px 0 0 0' class='cca-source'>Confidence in this "
        f"recommendation: {recommendation['confidence']:.0%}</p>"
    )

    st.markdown("##### Live Conversations")
    st.caption(
        "Real-time view of all student conversations (AI + Staff). Updates automatically. "
        "Shows the latest message from each conversation."
    )

    # Get all conversations from the conversation module
    all_conversations = conversation.get_all_conversations()
    
    if not all_conversations:
        st.info("No conversations yet. Students will appear here when they start chatting.")
    else:
        # Filter options
        filter_col, search_col = st.columns([1, 2])
        status_filter = filter_col.radio(
            "Status",
            ["All", "active", "waiting", "closed"],
            format_func=lambda value: {
                "All": "All",
                "active": "Active",
                "waiting": "Waiting",
                "closed": "Resolved",
            }[value],
            horizontal=True,
            key="conv_status_filter",
        )
        search = search_col.text_input("Search", key="conv_search")

        # Filter conversations
        filtered = all_conversations
        if status_filter != "All":
            filtered = [c for c in filtered if c.get("status") == status_filter]

        if search:
            needle = search.lower()
            filtered = [
                c for c in filtered
                if needle in c.get("student_name", "").lower()
                or needle in c.get("student_id", "").lower()
                or any(needle in m.get("text", "").lower() for m in c.get("messages", []))
            ]

        st.caption(f"Showing {len(filtered)} of {len(all_conversations)} conversations, newest first.")

        if not filtered:
            st.info("No conversations match this filter.")
        else:
            # Build rows for table
            rows = []
            for conv in filtered:
                messages = conv.get("messages", [])
                last_msg = messages[-1] if messages else None
                
                # Get last message details
                if last_msg:
                    last_text = last_msg.get("text", "")[:80]
                    last_time = last_msg.get("timestamp", "")[:19].replace("T", " ")
                    last_role = last_msg.get("role", "")
                    role_label = "🎓 Student" if last_role == "student" else ("👨‍💼 Staff" if last_role == "staff" else "🤖 AI")
                else:
                    last_text = "(no messages)"
                    last_time = ""
                    role_label = ""

                # Status badge
                status = conv.get("status", "active")
                status_badge = {
                    "active": "<span class='cca-badge cca-badge--good'>🟢 Active</span>",
                    "waiting": "<span class='cca-badge cca-badge--warn'>🟡 Waiting</span>",
                    "closed": "<span class='cca-badge cca-badge--good'>✅ Resolved</span>",
                }.get(status, f"<span class='cca-badge cca-badge--info'>{status}</span>")

                # Staff online indicator
                assigned_staff = conv.get("assigned_staff")
                staff_online = ""
                if assigned_staff:
                    is_online = staff_presence.is_staff_online(assigned_staff)
                    staff_online = "🟢" if is_online else "🔴"

                rows.append({
                    "student": f"{conv.get('student_name', 'Unknown')} ({conv.get('student_id', 'N/A')})",
                    "status": status_badge,
                    "staff": f"{staff_online} {assigned_staff or '—'}",
                    "messages": str(len(messages)),
                    "last_message": f"{role_label}: {last_text}",
                    "last_time": last_time,
                    "session_id": conv.get("session_id", "")[:8],
                })

            # Render HTML table
            st.markdown(_live_conversations_table_html(rows), unsafe_allow_html=True)

    st.markdown("##### Feedback")
    feedback_rows = [row for row in logs if row.get("event") == "feedback"]
    ups = sum(1 for row in feedback_rows if row.get("feedback") == "up")
    downs = sum(1 for row in feedback_rows if row.get("feedback") == "down")
    f1, f2 = st.columns(2)
    with f1:
        C.kpi("Helpful answers", ups)
    with f2:
        C.kpi("Not helpful", downs)

    metrics_path = ROOT / "models" / "intent_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        st.caption(
            f"Intent model: {metrics['corpus_size']} labelled questions, "
            f"{metrics['intents']} intents, hold-out macro F1 {metrics['holdout_macro_f1']}, "
            f"5-fold CV macro F1 {metrics['cv5_macro_f1_mean']}. {metrics['caveat']}"
        )


# --------------------------------------------------------------------------
# Developers
# --------------------------------------------------------------------------
def render_developers() -> None:
    C.hero(
        "Meet the Developers",
        "The team behind the Cognitive Campus Assistant. Only the details recorded "
        "in data/developer.json are shown - nothing here is invented.",
    )

    profile_data = profile()
    if not profile_data:
        st.info("No profile file found at `data/developer.json`.")
        return

    developers = profile_data.get("developers") or []
    if not developers:
        st.info("The profile file has no developers listed.")
        return

    cols = st.columns(len(developers))
    for col, dev in zip(cols, developers):
        photo = ROOT / (dev.get("photo") or "")
        with col:
            C.developer_card(dev, photo)

    st.markdown("")
    C.card(
        f"<p style='margin:0;font-size:0.9rem'><strong>{profile_data.get('course', '')}</strong>"
        f" &middot; {profile_data.get('school', '')}</p>"
        f"<p style='margin:6px 0 0 0;color:#A3B0D4;font-size:0.85rem'>"
        f"{profile_data.get('team', '')}</p>"
    )


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
def render_settings() -> None:
    prefs = _load_prefs()
    settings_dashboard.render_advanced_settings(
        prefs=prefs,
        save_prefs_fn=_save_prefs,
        log_audit_fn=_log_audit,
    )


def render_student_announcements() -> None:
    if not auth.is_student():
        st.error("This page is available to student accounts only.")
        return
    st.markdown("## School Announcements")
    today = datetime.now().date().isoformat()
    try:
        announcements = [
            item
            for item in staff_content.load_announcements()
            if item.get("status") in {"published", "scheduled"}
            and str(item.get("publish_on", "")) <= today
        ]
    except (OSError, ValueError) as error:
        st.error(f"Could not load school announcements: {error}")
        return
    announcements.sort(
        key=lambda item: str(item.get("publish_on", "")),
        reverse=True,
    )
    if not announcements:
        st.info("There are no current school announcements.")
        return
    for item in announcements:
        with st.container(border=True):
            st.markdown(f"### {item.get('title', 'School announcement')}")
            st.write(item.get("body", ""))
            if item.get("publish_on"):
                st.caption(f"Published {item['publish_on']}")


def render_student_knowledge() -> None:
    if not auth.is_student():
        st.error("This page is available to student accounts only.")
        return
    st.markdown("## Knowledge Base")
    st.caption("Official school information approved for student access.")
    try:
        articles = [
            article
            for article in staff_content.load_articles()
            if article.get("status") == "approved"
        ]
    except (OSError, ValueError) as error:
        st.error(f"Could not load the school knowledge base: {error}")
        return
    articles.sort(key=lambda article: str(article.get("category", "")).casefold())
    if not articles:
        st.info("There are no approved knowledge articles yet.")
        return
    for article in articles:
        with st.container(border=True):
            st.markdown(f"### {article.get('title', 'School information')}")
            st.caption(str(article.get("category", "School information")))
            st.write(article.get("content", ""))
            if article.get("source"):
                st.caption(f"Verified school source: {article['source']}")


def render_student_documents() -> None:
    if not auth.is_student():
        st.error("This page is available to student accounts only.")
        return
    student_id = auth.get_current_user_id()
    if not student_id:
        st.error("Could not identify your student account.")
        return
    _render_student_shared_documents(student_id)



# --------------------------------------------------------------------------
# Staff login page (separate from main navigation)
# --------------------------------------------------------------------------
def render_staff_login() -> None:
    """Standalone staff login page - not accessible from main navigation."""
    C.hero(
        "Staff Login",
        "Enter the registrar passcode to access the staff dashboard. "
        "This page is not linked from the student navigation."
    )

    if staff_gate.is_unlocked():
        st.success("Already unlocked. Redirecting to dashboard...")
        st.session_state.view = "dashboard"
        st.query_params["view"] = "dashboard"
        st.rerun()

    configured = staff_gate.expected_passcode()
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
        return

    if staff_gate.attempts_left() <= 0:
        st.error(
            f"Too many wrong attempts ({staff_gate.MAX_ATTEMPTS}). The dashboard is locked for "
            "this session - reload the page to try again."
        )
        if st.button("Reload the page"):
            st.rerun()
        return

    with st.form("staff_login_form", clear_on_submit=False):
        code = st.text_input("Passcode", type="password", key="staff_login_code")
        submitted = st.form_submit_button("Login to Dashboard", type="primary", width="stretch")

    if submitted:
        if staff_gate.check(code):
            st.session_state[staff_gate.SESSION_KEY] = True
            st.session_state[staff_gate.ATTEMPTS_KEY] = 0
            st.session_state.view = "dashboard"
            st.query_params["view"] = "dashboard"
            st.rerun()
        else:
            st.session_state[staff_gate.ATTEMPTS_KEY] = int(st.session_state.get(staff_gate.ATTEMPTS_KEY, 0)) + 1
            left = staff_gate.attempts_left()
            if left:
                st.error(f"Wrong passcode. {left} attempt{'s' if left != 1 else ''} left.")
            else:
                st.error(f"Wrong passcode. The dashboard is locked for this session.")
                st.rerun()

    st.caption(
        "🔐 One shared passcode for registrar staff. Not a per-user login - "
        "access this page directly via ?view=staff_login"
    )

    st.divider()
    if st.button("← Back to AI Assistant", type="secondary"):
        st.session_state.view = "chat"
        st.query_params["view"] = "chat"
        st.rerun()


# --------------------------------------------------------------------------
# Unified login page (student or staff)
# --------------------------------------------------------------------------
def render_login(cookie_manager) -> None:
    """Unified login page for students and staff."""
    if auth.is_logged_in():
        st.success("Already logged in. Redirecting...")
        st.session_state.view = "chat"
        st.query_params["view"] = "chat"
        st.rerun()

    st.markdown("<div class='cca-login-aurora'></div>", unsafe_allow_html=True)

    C.banner(
        "GRA",
        "SCHOOL",
        "Cognitive Campus Assistant",
        "An intelligent campus platform that helps students and staff access "
        "school services, learning tools, and AI-powered assistance.",
        art_path=ROOT / "assets" / "hero-edu.png",
    )

    C.login_card_open(
        "Login",
        "Enter your ID and password. Select your role to access the appropriate features.",
        "users",
    )

    st.markdown("<p class='cca-role-label'>Select your role</p>", unsafe_allow_html=True)
    role = st.segmented_control(
        "Login as",
        ["Student", "Staff"],
        default="Student",
        key="login_role",
        label_visibility="collapsed",
        width="stretch",
    ) or "Student"
    expected_role = "student" if role == "Student" else "staff"

    with st.form("login_form", clear_on_submit=False):
        user_id = st.text_input("ID (Student ID or Staff ID)", key="login_id")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Login", type="primary", width="stretch")

    if submitted:
        if not user_id or not password:
            st.error("Please enter both ID and password")
        else:
            success, message = auth.login(user_id, password, expected_role)
            if success:
                _remember_browser_login(cookie_manager)
                st.success(message)
                if expected_role == "staff":
                    st.session_state.view = "dashboard"
                    st.session_state["staff_section"] = "dashboard"
                    st.query_params["view"] = "dashboard"
                else:
                    st.session_state.view = "chat"
                    st.query_params["view"] = "chat"
            else:
                st.error(message)

    # No footer row here: the sidebar already carries Login and Create Account,
    # and a second pair of buttons under the card duplicated those routes.


# --------------------------------------------------------------------------
# Unified register page (student or staff)
# --------------------------------------------------------------------------
def render_register(cookie_manager) -> None:
    """Public student-only account registration."""
    C.hero(
        "Create Account",
        "Create a student account to access the GRA SCHOOL AI Assistant."
    )

    if auth.is_logged_in():
        st.success("Already logged in. Redirecting...")
        st.session_state.view = "chat"
        st.query_params["view"] = "chat"
        st.rerun()

    st.info("Student accounts can self-register. Staff accounts are created by authorized administrators only.")

    with st.form("register_form", clear_on_submit=False):
        user_id = st.text_input("Student ID", key="register_id")
        name = st.text_input("Name (optional)", key="register_name")
        password = st.text_input("Password", type="password", key="register_password")
        confirm = st.text_input("Confirm Password", type="password", key="register_confirm")
        submitted = st.form_submit_button("Create Account", type="primary", width="stretch")

    if submitted:
        if not user_id or not password:
            st.error("Please enter Student ID and password.")
        elif password != confirm:
            st.error("Passwords do not match")
        elif len(password) < 4:
            st.error("Password must be at least 4 characters")
        else:
            success, message = auth.create_account(user_id, password, name)
            if success:
                st.success(message)
                # Auto-login after registration
                success, login_message = auth.login(user_id, password, "student")
                if not success:
                    st.error(f"Your account was created, but automatic sign-in failed: {login_message}")
                    return
                _remember_browser_login(cookie_manager)
                st.session_state.view = "chat"
                st.query_params["view"] = "chat"
            else:
                st.error(message)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to AI Assistant", type="secondary"):
            st.session_state.view = "chat"
            st.query_params["view"] = "chat"
            st.rerun()
    with col2:
        if st.button("Login Instead", type="secondary"):
            st.session_state.view = "login"
            st.query_params["view"] = "login"
            st.rerun()


# --------------------------------------------------------------------------
# Staff login page (legacy - kept for backward compatibility with ?view=staff_login)
# --------------------------------------------------------------------------
def render_staff_login() -> None:
    """Legacy staff login page - redirects to unified login."""
    st.info("Redirecting to unified login page...")
    st.session_state.view = "login"
    st.query_params["view"] = "login"
    st.rerun()


# --------------------------------------------------------------------------
def main() -> None:
    cookie_manager = stx.CookieManager(key="auth_session_cookie_manager")
    try:
        _restore_browser_login(cookie_manager)
    except auth.AccountStoreError as error:
        st.error(f"Could not restore your sign-in because the account store is unavailable: {error}")
        return

    init_state()
    theme.inject(st.session_state.get("app_theme", "dark"))

    view = st.session_state.view

    # Pages that don't require authentication
    public_views = {"login", "register", "staff_login"}

    # If not logged in and trying to access a protected view, redirect to login
    if not auth.is_logged_in() and view not in public_views:
        st.session_state.view = "login"
        st.query_params["view"] = "login"
        view = "login"

    try:
        render_sidebar(cookie_manager)
    except auth.AccountStoreError as error:
        st.error(f"The account database is unavailable: {error}")
        return

    if view == "chat":
        render_chat()
    elif view == "student_announcements":
        render_student_announcements()
    elif view == "student_documents":
        render_student_documents()
    elif view == "student_knowledge":
        render_student_knowledge()
    elif view == "voice":
        render_voice()
    elif view == "login":
        render_login(cookie_manager)
    elif view == "register":
        render_register(cookie_manager)
    elif view == "staff_login":
        render_staff_login()
    elif view == "dashboard":
        # Staff dashboard - only accessible to logged-in staff
        if auth.is_staff():
            render_dashboard()
        else:
            st.error("Staff access required. Please log in as staff.")
            st.session_state.view = "login"
            st.query_params["view"] = "login"
            st.rerun()
    elif view == "dashboard_chat":
        if auth.is_staff():
            _render_staff_chat()
        else:
            st.error("Staff access required. Please log in as staff.")
            st.session_state.view = "login"
            st.query_params["view"] = "login"
            st.rerun()
    elif view == "developers":
        render_developers()
    elif view == "settings":
        render_settings()
    else:
        render_chat()


if __name__ == "__main__":
    main()
