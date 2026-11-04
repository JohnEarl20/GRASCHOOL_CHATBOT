"""Staff-only workspace views built from the app's existing local records."""
from __future__ import annotations

import html
import io
import os
import pickle
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import altair as alt
import pandas as pd
import psutil
import streamlit as st

from code import analytics_reports, auth, conversation, dialogue, forecast, intent_model, knowledge, logger, staff_content
from ui import components as C
from ui.theme import icon

ROOT = Path(__file__).resolve().parent.parent
INTENT_LABELS = {
    "ask_requirements": "Requirements",
    "ask_schedule_deadline": "Academic Calendar",
    "ask_fees_payment": "Tuition and Fees",
    "ask_office_hours_location": "Student Services",
    "ask_course_prereq": "Requirements",
    "ask_clearance_process": "Student Services",
    "check_eligibility": "Enrollment",
    "request_human": "Student Services",
    "give_feedback": "Others",
    "greet": "Others",
    "unknown": "Others",
    "empty_input": "Others",
}


def _require_staff() -> bool:
    if auth.is_staff():
        return True
    st.error("This workspace is available to authorized staff accounts only.")
    return False


def render_staff_management(audit_fn: Callable[[str, str], None]) -> None:
    """Create and review staff accounts for explicitly configured admins."""
    if not auth.is_admin():
        st.error("Staff Management is restricted to authorized administrators.")
        return

    st.markdown("## Staff Management")
    st.caption(
        "Create individual staff accounts. New staff can sign in immediately "
        "using their Staff ID and password."
    )
    notice = st.session_state.pop("staff_account_created_notice", None)
    if notice:
        st.success(notice)

    with st.form("create_staff_account_form", clear_on_submit=True):
        id_col, name_col = st.columns(2)
        with id_col:
            staff_id = st.text_input("Staff ID", max_chars=64)
        with name_col:
            full_name = st.text_input("Full Name", max_chars=120)

        email_col, department_col = st.columns(2)
        with email_col:
            official_email = st.text_input("Official Email", max_chars=254)
        with department_col:
            department = st.text_input("Department", max_chars=100)

        password_col, confirm_col = st.columns(2)
        with password_col:
            password = st.text_input(
                "Password",
                type="password",
                help="Use at least 8 characters.",
            )
        with confirm_col:
            confirm_password = st.text_input("Confirm Password", type="password")

        submitted = st.form_submit_button(
            "Create Staff Account",
            type="primary",
            icon=":material/person_add:",
            width="stretch",
        )

    if submitted:
        created, message = auth.create_staff_account(
            staff_id,
            full_name,
            official_email,
            department,
            password,
            confirm_password,
        )
        if created:
            audit_fn(
                f"Created staff account '{staff_id.strip()}'",
                auth.get_current_user_name() or auth.get_current_user_id() or "admin",
            )
            st.session_state["staff_account_created_notice"] = message
            st.rerun()
        else:
            st.error(message)

    st.markdown("### Existing staff accounts")
    try:
        staff_rows = [
            {
                "Staff ID": user_id,
                "Full Name": record.get("name", ""),
                "Official Email": record.get("email", ""),
                "Department": record.get("department", ""),
                "Created": record.get("created_at", "")[:10],
            }
            for user_id, record in auth._load_users().items()
            if record.get("role") == "staff"
        ]
    except auth.AccountStoreError as error:
        st.error(f"Could not load staff accounts: {error}")
        return

    if staff_rows:
        st.dataframe(
            pd.DataFrame(staff_rows),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No staff accounts have been created yet.")


def _questions() -> list[dict]:
    rows = [
        row for row in logger.read_logs()
        if row.get("event") != "feedback" and row.get("intent") != "voice_recording"
    ]
    return sorted(rows, key=lambda row: str(row.get("ts", "")), reverse=True)


def _question_review_rows(
    log_rows: list[dict] | None = None,
    conversations: list[dict] | None = None,
) -> list[dict]:
    """Combine assistant analytics with student messages, including staff-routed turns."""
    logs = _questions() if log_rows is None else [
        row for row in log_rows
        if row.get("event") != "feedback" and row.get("intent") != "voice_recording"
    ]
    deleted_sessions = logger.deleted_session_ids()
    logs = [
        row for row in logs
        if str(row.get("session_id", "")) not in deleted_sessions
    ]
    logs.sort(key=lambda row: str(row.get("ts", "")), reverse=True)
    conversation_rows = (
        conversation.get_all_conversations()
        if conversations is None
        else conversations
    )

    logs_by_question: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in logs:
        key = (str(row.get("session_id", "")), str(row.get("text", "")))
        logs_by_question[key].append(row)

    review_rows: list[dict] = []
    matched_log_ids: set[int] = set()
    for conv in conversation_rows:
        session_id = str(conv.get("session_id", ""))
        messages = conv.get("messages", [])
        for index, message in enumerate(messages):
            if message.get("role") != "student":
                continue
            text = str(message.get("text", "")).strip()
            if (
                not text
                or text.startswith("🎙️")
                or message.get("meta", {}).get("intent") == "voice_recording"
            ):
                continue

            key = (session_id, text)
            matches = logs_by_question.get(key, [])
            logged = matches.pop() if matches else None
            if logged is not None:
                matched_log_ids.add(id(logged))

            following = []
            for next_message in messages[index + 1:]:
                if next_message.get("role") == "student":
                    break
                following.append(next_message)
            staff_replied = any(item.get("role") == "staff" for item in following)
            assistant_message = next(
                (item for item in following if item.get("role") == "assistant"),
                {},
            )
            meta = logged or assistant_message.get("meta", {})
            intent = str(meta.get("intent") or "Unknown")
            routed_to_staff = (
                intent == "staff_notified"
                or "staff routing" in str(meta.get("source", "")).casefold()
            )
            if logged is not None:
                status = (
                    "Unanswered" if not logged.get("answered")
                    else "Sent to staff" if logged.get("escalated")
                    else "AI answered"
                )
            elif staff_replied:
                status = "Staff replied"
            elif routed_to_staff or conv.get("status") == "waiting":
                status = "Sent to staff"
            elif assistant_message and assistant_message.get("meta", {}).get("answered") is False:
                status = "Unanswered"
            elif assistant_message:
                status = "AI answered"
            else:
                status = "Awaiting response"

            review_rows.append({
                "_review_id": f"{session_id}:{message.get('id', index)}",
                "ts": message.get("timestamp") or (logged or {}).get("ts", ""),
                "student_name": conv.get("student_name"),
                "student_id": conv.get("student_id"),
                "text": text,
                "intent": "Staff hand-off" if routed_to_staff else intent,
                "confidence": meta.get("confidence"),
                "answered": status != "Unanswered",
                "escalated": routed_to_staff or bool(meta.get("escalated")),
                "status": status,
                "session_id": session_id,
            })

    for index, row in enumerate(logs):
        if id(row) in matched_log_ids:
            continue
        status = (
            "Unanswered" if not row.get("answered")
            else "Sent to staff" if row.get("escalated")
            else "AI answered"
        )
        review_rows.append({
            **row,
            "_review_id": (
                f"log:{row.get('session_id', '')}:{row.get('ts', '')}:"
                f"{index}:{row.get('text', '')}"
            ),
            "status": status,
        })

    return sorted(
        review_rows,
        key=lambda row: str(row.get("ts", "")),
        reverse=True,
    )


def _category(row: dict) -> str:
    return INTENT_LABELS.get(str(row.get("intent", "")), "Other")


def _date_value(row: dict) -> date | None:
    try:
        return datetime.fromisoformat(str(row.get("ts", ""))).date()
    except (ValueError, TypeError):
        return None


def _count_ontology_records() -> int:
    ontology = knowledge.load()
    return sum(
        len(records)
        for section, records in ontology.items()
        if section != "meta" and isinstance(records, list)
    ) + sum(1 for row in staff_content.load_articles() if row.get("status") == "approved")


def _active_announcements() -> list[dict]:
    today = date.today()
    return [
        row for row in staff_content.load_announcements()
        if row.get("status") in {"published", "scheduled"}
        and row.get("publish_on", "") <= today.isoformat()
    ]


def _conversation_for(
    row: dict,
    conversations_by_id: dict[str, dict],
    conversations_by_question: dict[tuple[str, str], dict],
) -> dict | None:
    conv = conversations_by_id.get(str(row.get("session_id", "")))
    if conv is None:
        conv = conversations_by_question.get(
            (str(row.get("student_id", "")), str(row.get("text", "")))
        )
    return conv


def _status_for(
    row: dict,
    conversations_by_id: dict[str, dict],
    conversations_by_question: dict[tuple[str, str], dict],
) -> str:
    conv = _conversation_for(row, conversations_by_id, conversations_by_question)
    if conv and conv.get("status") == "closed":
        return "Resolved"
    if conv and conv.get("status") == "waiting":
        return "Pending"
    if not row.get("answered"):
        return "Unanswered"
    return "AI answered"


def _metric_card(label: str, value: str, note: str, icon_name: str, tone: str) -> str:
    tones = {
        "blue": "#35D5FF",
        "green": "#00E676",
        "yellow": "#FFC107",
        "red": "#FF6478",
        "violet": "#9B8CFF",
        "cyan": "#00DFFF",
    }
    colour = tones[tone]
    return (
        f"<div class='cca-staff-kpi cca-staff-kpi--{tone}'>"
        f"<div class='cca-staff-kpi-icon' style='color:{colour}'>{icon(icon_name, 20, colour)}</div>"
        f"<div class='cca-staff-kpi-value'>{html.escape(value)}</div>"
        f"<div class='cca-staff-kpi-label'>{html.escape(label)}</div>"
        f"<div class='cca-staff-kpi-note'>{html.escape(note)}</div>"
        "</div>"
    )


def _verified_metrics(rows: list[dict]) -> tuple[str, str, int]:
    verified = [
        row for row in rows
        if row.get("evaluation_verified") is True and isinstance(row.get("correct"), bool)
    ]
    accuracy = (
        f"{sum(row['correct'] for row in verified) / len(verified):.0%}"
        if verified else "Not measured"
    )
    timed = [
        row["response_time_ms"]
        for row in rows
        if isinstance(row.get("response_time_ms"), (int, float))
        and row["response_time_ms"] >= 0
    ]
    avg_time = f"{sum(timed) / len(timed) / 1000:.2f}s" if timed else "Not recorded"
    return accuracy, avg_time, len(verified)


def _verified_accuracy_value(rows: list[dict]) -> float | None:
    verified = [
        row for row in rows
        if row.get("evaluation_verified") is True and isinstance(row.get("correct"), bool)
    ]
    if not verified:
        return None
    return sum(row["correct"] for row in verified) / len(verified)


def _average_response_seconds(rows: list[dict]) -> float | None:
    times = [
        row["response_time_ms"] / 1000
        for row in rows
        if isinstance(row.get("response_time_ms"), (int, float))
        and row["response_time_ms"] >= 0
    ]
    return sum(times) / len(times) if times else None


def _comparison_note(current: float | None, previous: float | None, unit: str = "") -> str:
    if current is None:
        return "Not measured from available records"
    if previous is None:
        return "No previous-period data"
    difference = current - previous
    direction = "↑" if difference > 0 else "↓" if difference < 0 else "→"
    if unit == "pp":
        change = f"{abs(difference) * 100:.1f} pp"
    elif unit == "s":
        change = f"{abs(difference):.2f}s"
    else:
        change = f"{abs(difference):g}"
    return f"{direction} {change} vs previous period"


def _build_trend(
    rows: list[dict],
    interval: str,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    values = [row_date for row in rows if (row_date := _date_value(row)) is not None]
    if not values:
        return pd.DataFrame(columns=["period", "inquiries"])

    today = date.today()
    if interval == "Daily":
        start = start or today - timedelta(days=13)
        end = end or today
        period_key = lambda value: value.isoformat()
        label = "day"
    elif interval == "Weekly":
        start = start or today - timedelta(weeks=11)
        end = end or today
        period_key = lambda value: f"{value.isocalendar().year}-W{value.isocalendar().week:02d}"
        label = "week"
    elif interval == "Monthly":
        start = start or today.replace(day=1) - timedelta(days=335)
        end = end or today
        period_key = lambda value: value.strftime("%Y-%m")
        label = "month"
    else:
        start = start or date(today.year - 4, 1, 1)
        end = end or today
        period_key = lambda value: str(value.year)
        label = "year"

    counts: dict[str, int] = {}
    for value in values:
        if start <= value <= end:
            key = period_key(value)
            counts[key] = counts.get(key, 0) + 1
    frame = pd.DataFrame(
        [{"period": key, "inquiries": value} for key, value in sorted(counts.items())]
    )
    frame.attrs["interval_label"] = label
    return frame


def _analytics_status(
    row: dict,
    conversations_by_id: dict[str, dict],
    conversations_by_question: dict[tuple[str, str], dict],
) -> str:
    conv = _conversation_for(row, conversations_by_id, conversations_by_question)
    if row.get("escalated"):
        return "Escalated"
    if conv and conv.get("status") == "closed":
        return "Resolved"
    if conv and conv.get("status") == "waiting":
        return "Pending"
    return "Answered" if row.get("answered") else "Unanswered"


def _analytics_records(rows: list[dict], conversations: list[dict]) -> list[dict]:
    conversations_by_id = {str(item.get("session_id", "")): item for item in conversations}
    conversations_by_question: dict[tuple[str, str], dict] = {}
    for conv in conversations:
        for message in conv.get("messages", []):
            if message.get("role") == "student":
                key = (str(conv.get("student_id", "")), str(message.get("text", "")))
                conversations_by_question.setdefault(key, conv)

    records = []
    for row in rows:
        conv = _conversation_for(row, conversations_by_id, conversations_by_question)
        resolution_minutes = None
        if conv and conv.get("status") == "closed":
            try:
                created = datetime.fromisoformat(str(conv.get("created_at", "")))
                closed = datetime.fromisoformat(str(conv.get("updated_at", "")))
                resolution_minutes = max(0, int((closed - created).total_seconds() // 60))
            except (TypeError, ValueError):
                pass
        records.append({
            "Inquiry ID": str(row.get("session_id", "unlinked"))[:12],
            "Student Question": str(row.get("text", "")),
            "Category": _category(row),
            "Date Submitted": str(row.get("ts", "")),
            "Response Status": _analytics_status(row, conversations_by_id, conversations_by_question),
            "Assigned Staff": str((conv or {}).get("assigned_staff") or "Unassigned"),
            "Resolution Time (min)": resolution_minutes,
            "_row": row,
        })
    return records


def _render_header() -> None:
    art_path = ROOT / "assets" / "hero-edu.png"
    if art_path.is_file():
        left, right = st.columns([4, 1], vertical_alignment="center")
        with left:
            st.markdown(
                "<div class='cca-staff-hero'>"
                "<div class='cca-staff-hero-eyebrow'>GRA SCHOOL · COGNITIVE CAMPUS ASSISTANT</div>"
                "<h1>STAFF WORKSPACE</h1>"
                "<p>Manage student inquiries, school information, and AI-powered administrative assistance.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        with right:
            st.image(str(art_path), width="stretch")
    else:
        C.hero(
            "STAFF WORKSPACE",
            "Manage student inquiries, school information, and AI-powered administrative assistance.",
        )


def _render_kpis(rows: list[dict], conversations: list[dict]) -> None:
    pending = sum(1 for conv in conversations if conv.get("status") == "waiting")
    resolved = sum(1 for conv in conversations if conv.get("status") == "closed")
    unanswered = sum(1 for row in rows if not row.get("answered"))
    today = date.today()
    current_period = sum(1 for row in rows if (row_date := _date_value(row)) and row_date >= today - timedelta(days=6))
    previous_period = sum(
        1 for row in rows
        if (row_date := _date_value(row)) and today - timedelta(days=13) <= row_date < today - timedelta(days=6)
    )
    comparison = (
        f"{current_period} this week vs {previous_period} last week"
        if current_period or previous_period
        else "No dated previous-period data"
    )
    counts = (
        ("Total Inquiries", str(len(rows)), comparison, "message", "blue"),
        ("Resolved", str(resolved), "Closed staff conversations", "check", "green"),
        ("Pending", str(pending), "Waiting for staff", "clock", "yellow"),
        ("Unanswered", str(unanswered), "AI did not provide an answer", "help", "red"),
        ("Knowledge Articles", str(_count_ontology_records()), "Ontology records and approved articles", "book", "violet"),
        ("Active Announcements", str(len(_active_announcements())), "Published school updates", "megaphone", "cyan"),
    )
    with st.container(key="staff-kpi-row"):
        cols = st.columns(6, gap="small")
        for col, values in zip(cols, counts):
            with col:
                st.html(_metric_card(*values))


def _render_charts(rows: list[dict]) -> None:
    st.markdown("<div class='cca-staff-section-heading'>Workspace analytics</div>", unsafe_allow_html=True)
    trend_col, category_col, performance_col = st.columns([1.45, 1, 1], gap="small")

    with trend_col:
        st.markdown("<div class='cca-staff-panel-title'>Student inquiry trends</div>", unsafe_allow_html=True)
        interval = st.radio(
            "Trend interval",
            ["Daily", "Weekly", "Monthly"],
            horizontal=True,
            key="staff_trend_interval",
            label_visibility="collapsed",
        )
        frame = _build_trend(rows, interval)
        if frame.empty:
            st.caption("No dated inquiry records for this period.")
        else:
            chart = (
                alt.Chart(frame)
                .mark_area(
                    line={"color": "#00A8FF", "strokeWidth": 2.5},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="rgba(0,168,255,0.42)", offset=0),
                            alt.GradientStop(color="rgba(0,168,255,0.02)", offset=1),
                        ],
                        x1=1, x2=1, y1=1, y2=0,
                    ),
                    interpolate="monotone",
                )
                .encode(
                    x=alt.X("period:N", title=None, axis=alt.Axis(labelAngle=-35)),
                    y=alt.Y("inquiries:Q", title="Inquiries", scale=alt.Scale(zero=True)),
                    tooltip=["period", "inquiries"],
                )
                .properties(height=220)
                .configure(
                    background="transparent",
                    view={"stroke": "transparent"},
                    axis={
                        "labelColor": "#A9BCD8",
                        "titleColor": "#A9BCD8",
                        "gridColor": "rgba(122,146,214,0.16)",
                        "domainColor": "rgba(122,146,214,0.35)",
                    },
                )
            )
            st.altair_chart(chart, width="stretch")

    with category_col:
        st.markdown("<div class='cca-staff-panel-title'>Inquiries by category</div>", unsafe_allow_html=True)
        category_counts: dict[str, int] = {}
        for row in rows:
            category = _category(row)
            category_counts[category] = category_counts.get(category, 0) + 1
        if category_counts:
            category_total = sum(category_counts.values())
            category_frame = pd.DataFrame(
                [
                    {"category": key, "total": value, "share": value / category_total}
                    for key, value in category_counts.items()
                ]
            )
            donut = (
                alt.Chart(category_frame)
                .mark_arc(innerRadius=56, outerRadius=92, stroke="#082653", strokeWidth=2)
                .encode(
                    theta=alt.Theta("total:Q"),
                    color=alt.Color(
                        "category:N",
                        scale=alt.Scale(
                            range=["#087CFF", "#00DFFF", "#00E676", "#FFC107", "#9B8CFF", "#FF6478"]
                        ),
                        legend=alt.Legend(orient="bottom", title=None, labelColor="#A9BCD8"),
                    ),
                    tooltip=[
                        "category",
                        alt.Tooltip("total:Q", title="Inquiries"),
                        alt.Tooltip("share:Q", title="Share", format=".1%"),
                    ],
                )
                .properties(height=250)
                .configure(background="transparent", view={"stroke": "transparent"})
            )
            st.altair_chart(donut, width="stretch")
            st.caption(f"{len(rows)} recorded questions · share of logged inquiries")
        else:
            st.caption("Category breakdown will appear when inquiries are logged.")

    with performance_col:
        st.markdown("<div class='cca-staff-panel-title'>AI assistant performance</div>", unsafe_allow_html=True)
        accuracy, avg_time, verified_count = _verified_metrics(rows)
        answered = sum(1 for row in rows if row.get("answered"))
        escalated = sum(1 for row in rows if row.get("escalated"))
        threshold = float(st.session_state.get("answer_threshold", dialogue.ANSWER_THRESHOLD))
        low_confidence = sum(
            1 for row in rows
            if isinstance(row.get("confidence"), (int, float))
            and row.get("confidence", 1) < threshold
        )
        stats = [
            ("Verified accuracy", accuracy, f"{verified_count} verified evaluations", "activity"),
            ("Average response time", avg_time, "Recorded response timing", "clock"),
            ("AI answered inquiries", str(answered), "From chat answer records", "bot"),
            ("Escalated inquiries", str(escalated), "Flagged for staff hand-off", "users"),
            ("Low-confidence responses", str(low_confidence), f"Below configured {threshold:.0%} threshold", "help"),
        ]
        for name, value, note, glyph in stats:
            st.markdown(
                "<div class='cca-staff-stat-row'>"
                f"<span class='cca-staff-stat-icon'>{icon(glyph, 16, '#35D5FF')}</span>"
                f"<span class='cca-staff-stat-name'>{html.escape(name)}<small>{html.escape(note)}</small></span>"
                f"<strong>{html.escape(value)}</strong>"
                "</div>",
                unsafe_allow_html=True,
            )
        st.caption("Accuracy is calculated only from explicitly verified evaluations, never from confidence scores.")


def _render_inquiry_table(rows: list[dict], conversations: list[dict]) -> None:
    st.markdown("<div class='cca-staff-section-heading'>Recent student inquiries</div>", unsafe_allow_html=True)
    conv_by_id = {str(item.get("session_id", "")): item for item in conversations}
    conv_by_question: dict[tuple[str, str], dict] = {}
    for conv in conversations:
        student_id = str(conv.get("student_id", ""))
        for message in conv.get("messages", []):
            if message.get("role") == "student":
                key = (student_id, str(message.get("text", "")))
                conv_by_question.setdefault(key, conv)
    categories = ["All"] + sorted({_category(row) for row in rows})
    statuses = ["All", "Resolved", "Pending", "Unanswered", "AI answered"]
    search_col, category_col, status_col, date_col = st.columns([2, 1, 1, 1])
    query = search_col.text_input("Search questions", key="staff_inquiry_search", placeholder="Question or reference")
    category_filter = category_col.selectbox("Category", categories, key="staff_inquiry_category")
    status_filter = status_col.selectbox("Status", statuses, key="staff_inquiry_status")
    date_filter = date_col.selectbox("Date", ["All time", "Last 7 days", "Last 30 days"], key="staff_inquiry_date")

    filtered = []
    cutoff = date.today() - timedelta(days=7 if date_filter == "Last 7 days" else 30)
    for row in rows:
        category = _category(row)
        status = _status_for(row, conv_by_id, conv_by_question)
        row_date = _date_value(row)
        if category_filter != "All" and category != category_filter:
            continue
        if status_filter != "All" and status != status_filter:
            continue
        if date_filter != "All time" and (row_date is None or row_date < cutoff):
            continue
        if query and query.casefold() not in str(row.get("text", "")).casefold() and query.casefold() not in str(row.get("session_id", "")).casefold():
            continue
        filtered.append((row, category, status, row_date))

    page_size = 5
    page_count = max(1, (len(filtered) + page_size - 1) // page_size)
    if int(st.session_state.get("staff_inquiry_page", 1)) > page_count:
        st.session_state["staff_inquiry_page"] = page_count
    page = st.number_input("Page", min_value=1, max_value=page_count, value=1, step=1, key="staff_inquiry_page")
    visible = filtered[(page - 1) * page_size:page * page_size]
    if not visible:
        st.info("No student inquiries match the selected filters.")
        return

    table_rows = []
    for row, category, status, row_date in visible:
        reference = str(row.get("session_id", "unlinked"))[:8]
        question = str(row.get("text", ""))
        timestamp = str(row.get("ts", "")).replace("T", " ")[:16]
        table_rows.append(
            "<tr>"
            f"<td>#{html.escape(reference)}</td>"
            f"<td class='cca-staff-question'>{html.escape(question)}</td>"
            f"<td>{html.escape(category)}</td>"
            f"<td><span class='cca-staff-status cca-staff-status--{status.lower().replace(' ', '-')}'>"
            f"{html.escape(status)}</span></td>"
            f"<td>{html.escape(timestamp)}</td>"
            f"<td>{html.escape(str((_conversation_for(row, conv_by_id, conv_by_question) or {}).get('assigned_staff') or '—'))}</td>"
            "</tr>"
        )
    st.markdown(
        "<div class='cca-staff-table-wrap'><table class='cca-staff-table'>"
        "<thead><tr><th>Reference</th><th>Student question</th><th>Category</th><th>Status</th><th>Date</th><th>Assigned staff</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Showing {(page - 1) * page_size + 1}–{min(page * page_size, len(filtered))} of {len(filtered)} inquiries.")
    selected_index = st.selectbox(
        "View inquiry details",
        options=list(range(len(filtered))),
        format_func=lambda index: (
            f"{str(filtered[index][0].get('session_id', 'unlinked'))[:8]} · "
            f"{str(filtered[index][0].get('text', ''))[:70]}"
        ),
        key="staff_inquiry_detail",
    )
    chosen = filtered[selected_index][0]
    with st.expander("Selected inquiry details"):
        st.write(chosen.get("text", ""))
        st.caption(
            f"Intent: {chosen.get('intent', 'not recorded')} · "
            f"Source: {chosen.get('source', 'not recorded')} · "
            f"Confidence: {chosen.get('confidence', 'not recorded')}"
        )
    if st.button("Open inquiry management", key="open_staff_inquiries", type="primary"):
        st.session_state["staff_section"] = "inquiries"
        st.query_params["section"] = "inquiries"
        st.rerun()


def _render_insights(rows: list[dict]) -> None:
    st.markdown("<div class='cca-staff-section-heading'>Insights & recommendations</div>", unsafe_allow_html=True)
    topics: dict[str, int] = {}
    for row in rows:
        category = _category(row)
        topics[category] = topics.get(category, 0) + 1
    unanswered = sum(1 for row in rows if not row.get("answered"))
    negative_feedback = sum(1 for row in logger.read_logs() if row.get("event") == "feedback" and row.get("feedback") == "down")

    recommendations = []
    if topics:
        topic, count = max(topics.items(), key=lambda item: item[1])
        recommendations.append(
            ("Knowledge coverage", f"{topic} is the most frequent inquiry topic in the current log.", "Review or expand verified knowledge for this category.", count, "High" if count >= 5 else "Normal")
        )
    if unanswered:
        recommendations.append(
            ("Unanswered concerns", f"{unanswered} logged inquiries were not answered by the assistant.", "Review the questions and provide an official response or verified knowledge article.", unanswered, "High")
        )
    fee_count = topics.get("Tuition and Fees", 0)
    if fee_count:
        recommendations.append(
            ("Tuition information", f"{fee_count} inquiries relate to tuition and fees.", "Check that payment guidance and fee records are current and approved.", fee_count, "Normal")
        )
    if negative_feedback:
        recommendations.append(
            ("Answer feedback", f"{negative_feedback} answers received negative feedback.", "Inspect the related conversations and update verified guidance where needed.", negative_feedback, "High")
        )
    if not recommendations:
        st.info("Insights will appear when the workspace has inquiry or feedback records.")
        return

    for title, description, action, count, priority in recommendations:
        st.markdown(
            "<div class='cca-staff-insight'>"
            "<div class='cca-staff-insight-mark'>"
            f"{icon('sparkles', 18, '#35D5FF')}</div>"
            "<div class='cca-staff-insight-copy'>"
            f"<strong>{html.escape(title)}</strong>"
            f"<p>{html.escape(description)}</p>"
            f"<small>Suggested action: {html.escape(action)}</small>"
            "</div>"
            f"<div class='cca-staff-insight-meta'><span>{priority} priority</span><b>{count} related</b></div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.caption("Automated suggestions are derived from recorded activity; they are not verified school information.")


def _system_status() -> list[tuple[str, str, bool | None]]:
    try:
        intent_model.get_model()
        assistant = ("Ready", True)
    except (OSError, ValueError, EOFError, ImportError, AttributeError, TypeError, pickle.UnpicklingError):
        assistant = ("Unavailable", False)
    try:
        ontology_path = ROOT / "data" / "ontology.json"
        with ontology_path.open("rb") as data_file:
            data_file.read(1)
        storage = ("Connected", True)
    except OSError:
        storage = ("Disconnected", False)
    return [
        ("AI Assistant", assistant[0], assistant[1]),
        ("Local data store", storage[0], storage[1]),
        ("API Service", "Not configured", None),
        ("Application server", "Online", True),
    ]


def _render_system_card() -> None:
    st.markdown("<div class='cca-staff-section-heading'>System status</div>", unsafe_allow_html=True)
    rows = _system_status()
    for label, value, healthy in rows:
        state = "unknown" if healthy is None else ("healthy" if healthy else "unhealthy")
        st.markdown(
            "<div class='cca-staff-stat-row'>"
            f"<span class='cca-staff-stat-name'>{html.escape(label)}</span>"
            f"<strong class='cca-staff-system-value cca-staff-system-value--{state}'>{html.escape(value)}</strong>"
            "</div>",
            unsafe_allow_html=True,
        )
    try:
        process_uptime = max(0, int(time.time() - psutil.Process(os.getpid()).create_time()))
        days, remainder = divmod(process_uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        uptime = f"{days}d {hours}h {minutes}m"
    except (OSError, psutil.Error):
        uptime = "Unavailable"
    st.caption(
        f"Last checked {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')} · "
        f"Streamlit {st.__version__} · Python {os.sys.version_info.major}.{os.sys.version_info.minor}"
    )
    st.caption(f"Application process uptime: {uptime}")


def _render_quick_actions() -> None:
    st.markdown("<div class='cca-staff-section-heading'>Quick actions</div>", unsafe_allow_html=True)
    items = [
        ("Answer inquiry", "inquiries", "message"),
        ("Add knowledge", "knowledge_announcements", "book"),
        ("Upload document", "documents", "upload"),
        ("Create announcement", "knowledge_announcements", "megaphone"),
        ("Generate report", "analytics", "chart"),
    ]
    with st.container(key="staff-quick-actions"):
        cols = st.columns(5, gap="small")
        for col, (label, section, glyph) in zip(cols, items):
            with col:
                st.html(
                    f"<div class='cca-staff-action-icon'>{icon(glyph, 26, '#35D5FF')}</div>"
                )
                if st.button(f"{label}", key=f"staff_quick_{section}_{glyph}", width="stretch"):
                    st.session_state["staff_section"] = section
                    if section == "knowledge_announcements":
                        st.session_state["staff_knowledge_announcements_tab"] = (
                            "Knowledge Base" if label == "Add knowledge"
                            else "School Announcements"
                        )
                    st.query_params["section"] = section
                    st.rerun()


def render_dashboard() -> None:
    if not _require_staff():
        return
    _render_header()
    rows = _questions()
    conversations = conversation.get_all_conversations()
    if any(row.get("synthetic") for row in rows):
        C.sample_data_warning(sum(1 for row in rows if row.get("synthetic")), len(rows))
    _render_kpis(rows, conversations)
    _render_charts(rows)

    table_col, insights_col = st.columns([1.55, 1], gap="small")
    with table_col:
        _render_inquiry_table(rows, conversations)
    with insights_col:
        _render_insights(rows)

    action_col, status_col = st.columns([1.6, 1], gap="small")
    with action_col:
        _render_quick_actions()
    with status_col:
        _render_system_card()


def render_analytics(audit_fn: Callable[[str, str], None]) -> None:
    if not _require_staff():
        return
    st.markdown(
        "<div class='cca-analytics-hero'><div><span>GRA SCHOOL · ACADEMIC INTELLIGENCE</span>"
        "<h1>Analytics &amp; Reports</h1>"
        "<p>Monitor student inquiries, evaluate AI performance, and generate institutional reports.</p>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    all_rows = _questions()
    conversations = conversation.get_all_conversations()
    records = _analytics_records(all_rows, conversations)
    today = date.today()

    filter_cols = st.columns([1.2, 1.5, 1.4, 1.4, 0.8], vertical_alignment="bottom")
    period = filter_cols[0].selectbox(
        "Reporting period",
        ["Last 7 days", "Last 30 days", "Semester", "Year to date", "All records", "Custom range"],
        index=1,
        key="analytics_period",
    )
    if period == "Custom range":
        default_range = (today - timedelta(days=29), today)
        selected_range = filter_cols[1].date_input(
            "Date range", value=default_range, key="analytics_custom_range"
        )
        if not isinstance(selected_range, tuple) or len(selected_range) != 2:
            st.info("Choose both a start and end date to apply the custom range.")
            start_date, end_date = default_range
        else:
            start_date, end_date = selected_range
    elif period == "Last 7 days":
        start_date, end_date = today - timedelta(days=6), today
    elif period == "Last 30 days":
        start_date, end_date = today - timedelta(days=29), today
    elif period == "Semester":
        start_date, end_date = today - timedelta(days=181), today
    elif period == "Year to date":
        start_date, end_date = date(today.year, 1, 1), today
    else:
        available_dates = [_date_value(row) for row in all_rows]
        available_dates = [value for value in available_dates if value is not None]
        start_date = min(available_dates) if available_dates else today
        end_date = today

    category_options = sorted({_category(row) for row in all_rows})
    category_filter = filter_cols[2].multiselect(
        "Categories", category_options, default=category_options, key="analytics_categories"
    )
    status_options = ["Answered", "Unanswered", "Pending", "Resolved", "Escalated"]
    status_filter = filter_cols[3].multiselect(
        "Statuses", status_options, default=status_options, key="analytics_statuses"
    )
    staff_options = sorted({record["Assigned Staff"] for record in records})
    if "Unassigned" not in staff_options:
        staff_options.append("Unassigned")
    staff_options = sorted(set(staff_options))
    staff_filter = filter_cols[4].selectbox(
        "Staff", ["All staff", *staff_options], key="analytics_staff"
    )
    if st.button("Refresh analytics", icon=":material/refresh:", key="analytics_refresh"):
        st.rerun()

    if end_date < start_date:
        st.error("The date range is invalid: end date must be on or after start date.")
        return
    filtered_records = [
        record for record in records
        if (row_date := _date_value(record["_row"])) is not None
        and start_date <= row_date <= end_date
        and record["Category"] in category_filter
        and record["Response Status"] in status_filter
        and (staff_filter == "All staff" or record["Assigned Staff"] == staff_filter)
    ]
    rows = [record["_row"] for record in filtered_records]
    range_label = f"{start_date:%b %d, %Y} – {end_date:%b %d, %Y}"
    st.caption(
        f"Reporting period: **{period}** · {range_label} · "
        f"{len(filtered_records):,} matching inquiries from local records"
    )
    if any(row.get("synthetic") for row in rows):
        C.sample_data_warning(sum(1 for row in rows if row.get("synthetic")), len(rows))

    st.markdown("<div class='cca-staff-section-heading'>Performance overview</div>", unsafe_allow_html=True)
    answered = sum(
        bool(record["_row"].get("answered")) or record["Response Status"] == "Resolved"
        for record in filtered_records
    )
    unanswered = sum(not bool(record["_row"].get("answered")) for record in filtered_records)
    resolution_rate = f"{answered / len(filtered_records):.0%}" if filtered_records else "—"
    accuracy, avg_response, verified_count = _verified_metrics(rows)
    current_period_count = len(filtered_records)
    previous_start = start_date - (end_date - start_date + timedelta(days=1))
    previous_rows = [
        record for record in records
        if (row_date := _date_value(record["_row"])) is not None
        and previous_start <= row_date < start_date
        and record["Category"] in category_filter
        and record["Response Status"] in status_filter
        and (staff_filter == "All staff" or record["Assigned Staff"] == staff_filter)
    ]
    previous_question_rows = [record["_row"] for record in previous_rows]
    previous_answered = sum(
        bool(record["_row"].get("answered")) or record["Response Status"] == "Resolved"
        for record in previous_rows
    )
    previous_unanswered = sum(
        not bool(record["_row"].get("answered")) for record in previous_rows
    )
    previous_resolution_rate = (
        previous_answered / len(previous_rows) if previous_rows else None
    )
    current_resolution_rate = (
        answered / len(filtered_records) if filtered_records else None
    )
    current_response_seconds = _average_response_seconds(rows)
    previous_response_seconds = _average_response_seconds(previous_question_rows)
    current_accuracy = _verified_accuracy_value(rows)
    previous_accuracy = _verified_accuracy_value(previous_question_rows)
    kpi_values = [
        (
            "Total inquiries", f"{len(filtered_records):,}",
            _comparison_note(
                float(current_period_count),
                float(len(previous_rows)) if previous_rows else None,
            ),
            "message", "blue",
        ),
        (
            "Answered inquiries", f"{answered:,}",
            _comparison_note(
                float(answered),
                float(previous_answered) if previous_rows else None,
            ),
            "check", "green",
        ),
        (
            "Unanswered inquiries", f"{unanswered:,}",
            _comparison_note(
                float(unanswered),
                float(previous_unanswered) if previous_rows else None,
            ),
            "help", "red",
        ),
        (
            "Resolution rate", resolution_rate,
            _comparison_note(current_resolution_rate, previous_resolution_rate, "pp"),
            "activity", "cyan",
        ),
        (
            "Average response time", avg_response,
            _comparison_note(current_response_seconds, previous_response_seconds, "s"),
            "clock", "yellow",
        ),
        (
            "Verified AI accuracy", accuracy,
            _comparison_note(current_accuracy, previous_accuracy, "pp")
            + f" · {verified_count} verified evaluations",
            "shield", "violet",
        ),
    ]
    with st.container(key="analytics-kpi-row"):
        for column, values in zip(st.columns(3, gap="small"), kpi_values[:3]):
            with column:
                st.html(_metric_card(*values))
        for column, values in zip(st.columns(3, gap="small"), kpi_values[3:]):
            with column:
                st.html(_metric_card(*values))
    st.caption("Accuracy is based only on explicitly verified evaluations. Confidence scores are not used.")

    st.markdown("<div class='cca-staff-section-heading'>Inquiry and AI performance</div>", unsafe_allow_html=True)
    trend_col, category_col = st.columns([1.35, 1], gap="medium")
    with trend_col:
        st.markdown("<div class='cca-staff-panel-title'>Student inquiry trends</div>", unsafe_allow_html=True)
        interval = st.radio(
            "Trend interval",
            ["Daily", "Weekly", "Monthly", "Yearly"],
            horizontal=True,
            key="analytics_trend_interval",
        )
        trend = _build_trend(rows, interval, start_date, end_date)
        if trend.empty:
            st.info("No dated inquiry records match these filters.")
        else:
            chart = (
                alt.Chart(trend)
                .mark_area(
                    line={"color": "#00DFFF", "strokeWidth": 3},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="rgba(0,168,255,0.38)", offset=0),
                            alt.GradientStop(color="rgba(0,168,255,0.02)", offset=1),
                        ],
                        x1=1, x2=1, y1=1, y2=0,
                    ),
                    interpolate="monotone",
                )
                .encode(
                    x=alt.X("period:N", title=None, axis=alt.Axis(labelAngle=-25)),
                    y=alt.Y("inquiries:Q", title="Inquiries", scale=alt.Scale(zero=True)),
                    tooltip=["period", alt.Tooltip("inquiries:Q", title="Inquiries")],
                )
                .properties(height=320)
                .configure(
                    background="transparent",
                    view={"stroke": "transparent"},
                    axis={
                        "labelColor": "#A9BCD8",
                        "titleColor": "#A9BCD8",
                        "gridColor": "rgba(122,146,214,0.16)",
                        "domainColor": "rgba(122,146,214,0.35)",
                    },
                )
            )
            st.altair_chart(chart, width="stretch")
    with category_col:
        st.markdown("<div class='cca-staff-panel-title'>Inquiry by category</div>", unsafe_allow_html=True)
        category_counts = Counter(record["Category"] for record in filtered_records)
        if category_counts:
            category_frame = pd.DataFrame(
                [{"category": key, "inquiries": value} for key, value in category_counts.most_common()]
            )
            chart = (
                alt.Chart(category_frame)
                .mark_arc(innerRadius=78, outerRadius=125, stroke="#082653", strokeWidth=2)
                .encode(
                    theta=alt.Theta("inquiries:Q"),
                    color=alt.Color("category:N", legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=["category:N", alt.Tooltip("inquiries:Q", title="Inquiries")],
                )
                .properties(height=330)
                .configure(background="transparent", view={"stroke": "transparent"})
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("No category data for this selection.")

    performance_col, activity_col = st.columns([1, 1], gap="medium")
    with performance_col:
        st.markdown("<div class='cca-staff-panel-title'>Resolution performance</div>", unsafe_allow_html=True)
        status_counts = Counter(record["Response Status"] for record in filtered_records)
        status_frame = pd.DataFrame([
            {"status": status, "count": status_counts.get(status, 0)}
            for status in ["Answered", "Resolved", "Pending", "Unanswered", "Escalated"]
        ])
        status_chart = (
            alt.Chart(status_frame)
            .mark_bar(cornerRadiusEnd=6)
            .encode(
                x=alt.X("count:Q", title="Inquiries"),
                y=alt.Y("status:N", sort=["Answered", "Resolved", "Pending", "Unanswered", "Escalated"], title=None),
                color=alt.Color("status:N", legend=None),
                tooltip=["status:N", alt.Tooltip("count:Q", title="Inquiries")],
            )
            .properties(height=240)
            .configure(background="transparent", view={"stroke": "transparent"})
        )
        st.altair_chart(status_chart, width="stretch")
    with activity_col:
        st.markdown("<div class='cca-staff-panel-title'>Student activity by weekday</div>", unsafe_allow_html=True)
        weekday_counts = Counter(
            row_date.strftime("%A")
            for record in filtered_records
            if (row_date := _date_value(record["_row"])) is not None
        )
        weekday_frame = pd.DataFrame([
            {"weekday": day, "inquiries": weekday_counts.get(day, 0)}
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        ])
        activity_chart = (
            alt.Chart(weekday_frame)
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, color="#087CFF")
            .encode(
                x=alt.X("weekday:N", sort=None, title=None, axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("inquiries:Q", title="Inquiries"),
                tooltip=["weekday:N", alt.Tooltip("inquiries:Q", title="Inquiries")],
            )
            .properties(height=240)
            .configure(background="transparent", view={"stroke": "transparent"})
        )
        st.altair_chart(activity_chart, width="stretch")

    st.markdown("<div class='cca-staff-section-heading'>AI assistant performance</div>", unsafe_allow_html=True)
    escalated = sum(bool(row.get("escalated")) for row in rows)
    threshold = float(st.session_state.get("answer_threshold", dialogue.ANSWER_THRESHOLD))
    low_confidence = sum(
        isinstance(row.get("confidence"), (int, float)) and row["confidence"] < threshold
        for row in rows
    )
    ai_stats = [
        ("AI answered inquiries", str(sum(bool(row.get("answered")) for row in rows))),
        ("Escalated inquiries", str(escalated)),
        ("Low-confidence responses", str(low_confidence)),
        ("Average response time", avg_response),
        ("Verified accuracy", accuracy),
    ]
    cols = st.columns(len(ai_stats))
    for column, (label, value) in zip(cols, ai_stats):
        with column:
            st.html(_metric_card(label, value, "From recorded events", "activity", "cyan"))

    st.markdown("<div class='cca-staff-section-heading'>Detailed inquiry records</div>", unsafe_allow_html=True)
    search_col, sort_col, page_col = st.columns([2, 1, 1])
    search = search_col.text_input("Search inquiries", key="analytics_inquiry_search")
    sort_order = sort_col.selectbox("Sort by", ["Newest first", "Oldest first", "Question A–Z"], key="analytics_sort")
    page_size = page_col.selectbox("Rows per page", [10, 25, 50], key="analytics_page_size")
    table_records = [
        record for record in filtered_records
        if not search or search.casefold() in " ".join(
            str(record[field]) for field in ("Inquiry ID", "Student Question", "Category", "Assigned Staff")
        ).casefold()
    ]
    if sort_order == "Oldest first":
        table_records.sort(key=lambda record: record["Date Submitted"])
    elif sort_order == "Question A–Z":
        table_records.sort(key=lambda record: record["Student Question"].casefold())
    else:
        table_records.sort(key=lambda record: record["Date Submitted"], reverse=True)
    page_count = max(1, (len(table_records) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=page_count, step=1, key="analytics_table_page")
    visible_records = table_records[(page - 1) * page_size:page * page_size]
    if visible_records:
        table_frame = pd.DataFrame([
            {key: value for key, value in record.items() if not key.startswith("_")}
            for record in visible_records
        ])
        st.dataframe(table_frame, width="stretch", hide_index=True)
        st.caption(
            f"Showing {(page - 1) * page_size + 1}–{min(page * page_size, len(table_records))} "
            f"of {len(table_records)} matching inquiries."
        )
        selected = st.selectbox(
            "View inquiry details",
            range(len(visible_records)),
            format_func=lambda index: (
                f"{visible_records[index]['Inquiry ID']} · "
                f"{visible_records[index]['Student Question'][:75]}"
            ),
            key="analytics_selected_inquiry",
        )
        with st.expander("Inquiry details"):
            st.write(visible_records[selected]["Student Question"])
            st.caption(
                f"{visible_records[selected]['Category']} · "
                f"{visible_records[selected]['Response Status']} · "
                f"{visible_records[selected]['Date Submitted']}"
            )
    else:
        st.info("No inquiries match the selected date range and filters.")

    st.markdown("<div class='cca-staff-section-heading'>Academic insights</div>", unsafe_allow_html=True)
    if filtered_records:
        top_category, top_count = Counter(record["Category"] for record in filtered_records).most_common(1)[0]
        unanswered_categories = Counter(
            record["Category"] for record in filtered_records
            if record["Response Status"] == "Unanswered"
        )
        insight_rows = [
            (
                "Most common student concern",
                f"{top_category} accounts for {top_count} of {len(filtered_records)} matching inquiries.",
                "Review that category's approved knowledge and current school notices.",
            )
        ]
        if unanswered_categories:
            category, count = unanswered_categories.most_common(1)[0]
            insight_rows.append((
                "Frequently unanswered topic",
                f"{category} has {count} inquiries without a recorded answer.",
                "Review these questions and add verified school guidance where appropriate.",
            ))
        for title, evidence, action in insight_rows:
            st.markdown(
                "<div class='cca-staff-insight'><div class='cca-staff-insight-mark'>"
                f"{icon('sparkles', 18, '#35D5FF')}</div><div class='cca-staff-insight-copy'>"
                f"<strong>{html.escape(title)}</strong><p>{html.escape(evidence)}</p>"
                f"<small>Suggested action: {html.escape(action)}</small></div></div>",
                unsafe_allow_html=True,
            )
        st.caption("Activity-based recommendations, not AI-generated or verified school guidance.")
    else:
        st.info("Insights appear when matching inquiry records are available.")

    st.markdown("<div class='cca-staff-section-heading'>Report generator</div>", unsafe_allow_html=True)
    report_types = [
        "Student Inquiry Report",
        "AI Performance Report",
        "Unanswered Questions Report",
        "Category Distribution Report",
        "Staff Activity Report",
        "Academic Semester Report",
        "School Operations Report",
    ]
    report_type = st.selectbox("Report type", report_types, key="analytics_report_type")
    metric_options = [
        "Inquiry totals", "Resolution rate", "Response time", "Verified AI accuracy",
        "Category breakdown", "Status breakdown",
    ]
    metrics = st.multiselect(
        "Include metrics",
        metric_options,
        default=metric_options,
        key="analytics_report_metrics",
    )
    include_charts = st.checkbox("Include charts in Excel and PDF reports", value=True, key="analytics_include_charts")

    report_source_records = filtered_records
    if report_type == "Unanswered Questions Report":
        report_source_records = [
            record for record in report_source_records
            if not record["_row"].get("answered")
        ]
    elif report_type == "Staff Activity Report":
        report_source_records = [
            record for record in report_source_records
            if record["Assigned Staff"] != "Unassigned"
        ]
    report_frame = pd.DataFrame([
        {key: value for key, value in record.items() if not key.startswith("_")}
        for record in report_source_records
    ])

    report_summary = []
    report_answered = sum(
        bool(record["_row"].get("answered")) or record["Response Status"] == "Resolved"
        for record in report_source_records
    )
    report_resolution_rate = (
        f"{report_answered / len(report_source_records):.0%}"
        if report_source_records else "—"
    )
    report_accuracy, report_avg_time, report_verified_count = _verified_metrics(
        [record["_row"] for record in report_source_records]
    )
    metric_values = {
        "Inquiry totals": f"Inquiries: {len(report_frame)}",
        "Resolution rate": f"Resolution rate: {report_resolution_rate}",
        "Response time": f"Average response time: {report_avg_time}",
        "Verified AI accuracy": (
            f"Verified AI accuracy: {report_accuracy} "
            f"({report_verified_count} verified evaluations)"
        ),
        "Category breakdown": "Categories: " + ", ".join(
            f"{name} {count}" for name, count in Counter(
                report_frame["Category"] if "Category" in report_frame else []
            ).most_common()
        ),
        "Status breakdown": "Statuses: " + ", ".join(
            f"{name} {count}" for name, count in Counter(
                report_frame["Response Status"] if "Response Status" in report_frame else []
            ).most_common()
        ),
    }
    report_summary = [metric_values[metric] for metric in metrics]
    st.caption(f"Preview: {report_type} · {len(report_frame):,} rows · {range_label}")
    if report_frame.empty:
        st.info("There are no report records for these filters.")
    else:
        st.dataframe(report_frame, width="stretch", hide_index=True)

    generate_col, print_col = st.columns([1, 1])
    generate_report = generate_col.button(
        "Generate and save report",
        type="primary",
        icon=":material/description:",
        key="analytics_generate_report",
        disabled=report_frame.empty or not metrics,
        width="stretch",
    )
    print_col.html(
        "<button class='cca-print-button' onclick='window.print()' "
        "aria-label='Print this analytics page'>Print page</button>"
    )
    if generate_report:
        with st.spinner("Generating CSV, Excel, and PDF reports…"):
            try:
                csv_bytes = report_frame.to_csv(index=False).encode("utf-8-sig")
                xlsx_buffer = io.BytesIO()
                with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
                    pd.DataFrame({"Metric": metrics, "Value": report_summary}).to_excel(
                        writer, index=False, sheet_name="Summary"
                    )
                    report_frame.to_excel(writer, index=False, sheet_name="Inquiries")
                    category_report = Counter(
                        report_frame["Category"] if "Category" in report_frame else []
                    )
                    if include_charts:
                        pd.DataFrame(
                            category_report.most_common(),
                            columns=["Category", "Inquiries"],
                        ).to_excel(writer, index=False, sheet_name="Category data")
                if include_charts and category_report:
                    from openpyxl import load_workbook
                    from openpyxl.chart import BarChart, Reference

                    workbook = load_workbook(xlsx_buffer)
                    category_sheet = workbook["Category data"]
                    chart = BarChart()
                    chart.type = "bar"
                    chart.style = 10
                    chart.title = "Inquiries by category"
                    chart.y_axis.title = "Category"
                    chart.x_axis.title = "Inquiries"
                    chart.add_data(
                        Reference(category_sheet, min_col=2, min_row=1, max_row=category_sheet.max_row),
                        titles_from_data=True,
                    )
                    chart.set_categories(
                        Reference(category_sheet, min_col=1, min_row=2, max_row=category_sheet.max_row)
                    )
                    chart.height = 8
                    chart.width = 16
                    category_sheet.add_chart(chart, "D2")
                    xlsx_buffer = io.BytesIO()
                    workbook.save(xlsx_buffer)
                pdf_lines = [*report_summary, "", "INQUIRY RECORDS"]
                category_counts = list(category_report.most_common())
                pdf_lines.extend(["", " · ".join(report_frame.columns)])
                for values in report_frame.fillna("").itertuples(index=False, name=None):
                    pdf_lines.append(" | ".join(str(value)[:50] for value in values))
                report_name = f"{report_type} · {range_label}"
                record = analytics_reports.save_report(
                    report_name,
                    report_type,
                    auth.get_current_user_name() or auth.get_current_user_id() or "Staff",
                    {
                        "csv": csv_bytes,
                        "xlsx": xlsx_buffer.getvalue(),
                        "pdf": analytics_reports.make_pdf(
                            report_name,
                            pdf_lines,
                            category_counts if include_charts else None,
                        ),
                    },
                )
            except (OSError, ValueError, KeyError) as error:
                st.error(f"Could not generate the report: {error}")
            else:
                audit_fn(
                    f"Generated {report_type} ({len(report_frame)} records)",
                    auth.get_current_user_name() or auth.get_current_user_id() or "staff",
                )
                st.session_state["analytics_generated_report"] = record
                st.success("Report saved. Download links are available below and in Report History.")

    latest = st.session_state.get("analytics_generated_report")
    if latest:
        st.markdown(f"**Latest:** {html.escape(str(latest.get('name', 'Report')))}")
        download_cols = st.columns(3)
        mime_types = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pdf": "application/pdf",
        }
        for column, file_format in zip(download_cols, ("csv", "xlsx", "pdf")):
            filename = latest.get("files", {}).get(file_format)
            if filename:
                try:
                    file_bytes = analytics_reports.read_report_file(filename)
                except (OSError, ValueError) as error:
                    st.error(f"Could not read the generated {file_format.upper()} report: {error}")
                else:
                    column.download_button(
                        f"Download {file_format.upper()}",
                        file_bytes,
                        filename,
                        mime_types[file_format],
                        key=f"analytics_latest_{file_format}",
                        width="stretch",
                    )

    st.markdown("<div class='cca-staff-section-heading'>Report history</div>", unsafe_allow_html=True)
    try:
        history = analytics_reports.load_history()
    except ValueError as error:
        st.error(str(error))
        history = []
    if not history:
        st.info("No reports have been generated yet.")
    else:
        for index, report in enumerate(history[:20]):
            with st.container(border=True):
                title_col, metadata_col, actions_col = st.columns([2, 2, 2])
                title_col.markdown(f"**{html.escape(str(report.get('name', 'Report')))}**")
                metadata_col.caption(
                    f"{report.get('type', 'Report')} · {report.get('generated_by', 'Staff')} · "
                    f"{report.get('generated_at', '')}"
                )
                files = report.get("files", {})
                action_cols = actions_col.columns(max(1, len(files)))
                for action_col, (file_format, filename) in zip(action_cols, files.items()):
                    try:
                        content = analytics_reports.read_report_file(filename)
                    except (OSError, ValueError) as error:
                        action_col.caption(f"{file_format.upper()} unavailable")
                        st.warning(f"Saved report #{index + 1}: {error}")
                    else:
                        action_col.download_button(
                            file_format.upper(),
                            content,
                            filename,
                            mime_types.get(file_format, "application/octet-stream"),
                            key=f"analytics_history_{index}_{file_format}",
                        )

    st.caption(
        "Analytics are read from the existing local chat log and staff conversation files. "
        "This app has no separate analytics API or relational database configured."
    )


@st.fragment(run_every=2)
def _render_live_question_review(audit_fn: Callable[[str, str], None]) -> None:
    questions = _question_review_rows()
    if not questions:
        st.info("No student questions are recorded. New messages will appear automatically.")
        st.caption(f"Last checked {datetime.now().astimezone().strftime('%H:%M:%S')} · refreshes every 2 seconds")
        return
    unanswered_count = sum(row["status"] == "Unanswered" for row in questions)
    st.caption(
        f"{len(questions)} student messages · {unanswered_count} unanswered · "
        f"refreshes every 2 seconds · last checked "
        f"{datetime.now().astimezone().strftime('%H:%M:%S')}"
    )
    review_rows = [
        {
            "Date": str(row.get("ts", "")).replace("T", " ")[:19] or "Unknown",
            "Student": str(row.get("student_name") or "Student"),
            "Student ID": str(row.get("student_id") or "Not recorded"),
            "Question": str(row.get("text") or ""),
            "Predicted topic": str(row.get("intent") or "Unknown"),
            "Confidence": (
                f"{float(row['confidence']):.0%}"
                if isinstance(row.get("confidence"), (int, float))
                else "Not available"
            ),
            "Status": row.get("status", "Unknown"),
            "Escalated": "Yes" if row.get("escalated") else "No",
            "Reference": str(row.get("session_id") or "Not available"),
        }
        for row in questions
    ]
    st.dataframe(
        pd.DataFrame(review_rows),
        width="stretch",
        hide_index=True,
        height=min(600, max(180, 38 + 35 * len(review_rows))),
    )
    st.markdown("### Classify a question")
    question_by_id = {row["_review_id"]: row for row in questions}
    option_labels = {
        row["_review_id"]: (
            f"{str(row.get('ts', ''))[:19]} · {str(row.get('text', ''))[:100]}"
        )
        for row in questions
    }
    selected_id = st.selectbox(
        "Select a question to classify",
        list(question_by_id),
        format_func=option_labels.__getitem__,
        key="staff_review_question",
    )
    question = question_by_id[selected_id]
    st.info(question.get("text", ""))
    intents = sorted({row["intent"] for row in intent_model.load_corpus()})
    if not intents:
        st.warning("No intent labels are available in the existing training corpus.")
        return
    intent = st.selectbox("Correct intent", intents, key="staff_review_intent")
    if st.button("Save staff label", type="primary", key="staff_save_review"):
        intent_model.add_staff_label(str(question.get("text", "")), intent)
        audit_fn(
            f"Classified a student question as {intent}",
            auth.get_current_user_name() or auth.get_current_user_id() or "staff",
        )
        st.success("Staff label saved to the existing training corpus.")
    if st.button("Retrain intent model", key="staff_retrain_model"):
        try:
            metrics = intent_model.retrain()
        except (OSError, ValueError, RuntimeError) as error:
            st.error(f"Model retraining failed: {error}")
        else:
            audit_fn("Retrained intent model from the labelled corpus", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
            st.success(f"Model retrained using {metrics.get('corpus_size', 'available')} labelled questions.")


def render_question_review(audit_fn: Callable[[str, str], None]) -> None:
    if not _require_staff():
        return
    st.markdown("## Question Review")
    _render_live_question_review(audit_fn)


def render_knowledge_base(audit_fn: Callable[[str, str], None]) -> None:
    if not _require_staff():
        return
    st.markdown("## Knowledge Base")
    st.caption("New articles remain drafts until a staff member approves their school source. Only approved articles can be used by the assistant.")
    records = staff_content.load_articles()
    edit_options = {"Create a new draft": None}
    edit_options.update({
        f"{row.get('title', 'Untitled')} · {row.get('status', 'draft')} · {str(row.get('id', ''))[:8]}": row.get("id")
        for row in records
    })
    selected_label = st.selectbox("Article", list(edit_options), key="staff_article_selection")
    selected_id = edit_options[selected_label]
    current = next((row for row in records if row.get("id") == selected_id), {})
    with st.form("staff_article_form"):
        title = st.text_input("Title", value=current.get("title", ""), max_chars=160)
        category = st.selectbox(
            "Category",
            staff_content.ARTICLE_CATEGORIES,
            index=staff_content.ARTICLE_CATEGORIES.index(current.get("category"))
            if current.get("category") in staff_content.ARTICLE_CATEGORIES else 0,
        )
        source = st.text_input("School source / verification note", value=current.get("source", ""), max_chars=500)
        content = st.text_area("Official answer", value=current.get("content", ""), height=180, max_chars=12000)
        submitted = st.form_submit_button("Save as draft", type="primary")
    if submitted:
        try:
            staff_content.save_article(
                title, content, category, source,
                auth.get_current_user_id() or "",
                str(selected_id) if selected_id else None,
            )
        except (OSError, ValueError) as error:
            st.error(f"Could not save article: {error}")
        else:
            audit_fn("Saved a knowledge article draft", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
            st.success("Draft saved.")
            st.rerun()

    if selected_id:
        button_col, archive_col = st.columns(2)
        if button_col.button("Approve for AI answers", type="primary", key="staff_approve_article"):
            try:
                staff_content.set_article_status(str(selected_id), "approved", auth.get_current_user_id() or "")
            except (OSError, ValueError) as error:
                st.error(f"Could not approve article: {error}")
            else:
                audit_fn("Approved a knowledge article", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
                st.success("Article approved and available to the assistant.")
                st.rerun()
        if archive_col.button("Archive article", key="staff_archive_article"):
            try:
                staff_content.set_article_status(str(selected_id), "archived", auth.get_current_user_id() or "")
            except (OSError, ValueError) as error:
                st.error(f"Could not archive article: {error}")
            else:
                audit_fn("Archived a knowledge article", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
                st.success("Article archived.")
                st.rerun()
    st.markdown("### School ontology")
    st.caption("Existing official records stay in data/ontology.json and remain available to the assistant.")
    ontology = knowledge.load()
    st.write({
        section: len(records)
        for section, records in ontology.items()
        if section != "meta" and isinstance(records, list)
    })


def render_documents(audit_fn: Callable[[str, str], None]) -> None:
    if not _require_staff():
        return
    st.markdown("## Document Management")
    st.caption(
        "Upload documents and choose which student accounts can access them. "
        "Unassigned documents remain staff-only. Supported: PDF, DOCX, TXT, CSV, XLSX (500 MB maximum)."
    )
    try:
        users = auth._load_users()
    except auth.AccountStoreError as error:
        st.error(f"Could not load student accounts: {error}")
        return
    student_options = {
        user_id: f"{record.get('name') or user_id} · {user_id}"
        for user_id, record in users.items()
        if record.get("role") == "student"
    }
    documents = staff_content.load_documents()
    document_options = {"Upload as a new document": None}
    document_options.update({
        f"Replace: {row.get('filename', 'Untitled')} · {row.get('category', '')} · {str(row.get('id', ''))[:8]}": row.get("id")
        for row in documents
    })
    replacement_id = st.selectbox("Upload operation", list(document_options), key="staff_document_operation")
    replace_id = document_options[replacement_id]
    current_document = next(
        (row for row in documents if row.get("id") == replace_id),
        {},
    )
    default_recipients = [
        student_id
        for student_id in current_document.get("shared_with", [])
        if student_id in student_options
    ]
    with st.form("staff_document_upload", clear_on_submit=True):
        upload = st.file_uploader("Choose a supporting document", type=["pdf", "docx", "txt", "csv", "xlsx"])
        category = st.text_input("Category", max_chars=80, placeholder="For example: Enrollment")
        selected_students = st.multiselect(
            "Share with student(s)",
            options=list(student_options),
            default=default_recipients,
            format_func=lambda student_id: student_options[student_id],
            help="Only selected students can download this document from their Student AI Assistant. Leave blank for staff-only access.",
        )
        submitted = st.form_submit_button(
            "Replace document" if replace_id else "Upload and share document",
            type="primary",
        )
    if submitted:
        if upload is None:
            st.error("Select a file before uploading.")
        else:
            try:
                if replace_id:
                    record = staff_content.replace_document(
                        str(replace_id),
                        upload.name,
                        upload.getvalue(),
                        category,
                        auth.get_current_user_id() or "",
                        selected_students,
                    )
                else:
                    record = staff_content.save_document(
                        upload.name,
                        upload.getvalue(),
                        category,
                        auth.get_current_user_id() or "",
                        selected_students,
                    )
            except (OSError, ValueError) as error:
                st.error(f"Document upload failed: {error}")
            else:
                action = "Replaced" if replace_id else "Uploaded"
                audit_fn(f"{action} staff document '{record['filename']}'", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
                recipient_count = len(record.get("shared_with", []))
                st.success(
                    f"Document {action.lower()}. "
                    f"Shared with {recipient_count} student account(s)."
                )
                st.rerun()

    documents = staff_content.load_documents()
    query = st.text_input("Search documents", key="staff_document_search")
    visible = [
        row for row in documents
        if query.casefold() in str(row.get("filename", "")).casefold()
        or query.casefold() in str(row.get("category", "")).casefold()
    ]
    if not visible:
        st.info("No documents match this search." if documents else "No staff documents have been uploaded.")
        return
    labels = [
        f"{row.get('filename', '')} · {row.get('category', '')} · "
        f"{row.get('uploaded_at', '')[:10]} · "
        f"{len(row.get('shared_with', []))} student(s)"
        for row in visible
    ]
    selection = st.selectbox("Document", range(len(visible)), format_func=lambda value: labels[value], key="staff_document_selected")
    chosen = visible[selection]
    try:
        record, data = staff_content.read_document(str(chosen.get("id", "")))
    except (OSError, ValueError) as error:
        st.error(f"Could not open document: {error}")
        return
    mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[Path(record["filename"]).suffix.lower()]
    st.download_button("Download selected document", data, record["filename"], mime, key="staff_document_download")
    if Path(record["filename"]).suffix.lower() == ".txt":
        st.text(data.decode("utf-8", errors="replace")[:12000])
    elif Path(record["filename"]).suffix.lower() == ".csv":
        try:
            frame = pd.read_csv(io.BytesIO(data), nrows=100)
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as error:
            st.warning(f"CSV preview is unavailable: {error}")
        else:
            st.dataframe(frame, width="stretch")

    st.warning(
        "Deleting a document permanently removes it for staff and every student it was shared with."
    )
    confirmation_key = f"confirm_delete_staff_document_{record['id']}"
    if st.session_state.get(confirmation_key):
        st.error(f"Delete **{record['filename']}** permanently?")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button(
                "Delete document permanently",
                key=f"confirm_delete_staff_document_yes_{record['id']}",
                type="primary",
                icon=":material/delete_forever:",
                width="stretch",
            ):
                try:
                    deleted = staff_content.delete_document(str(record["id"]))
                except (OSError, PermissionError, ValueError) as error:
                    st.error(f"Could not delete the document: {error}")
                else:
                    if deleted:
                        audit_fn(
                            f"Deleted staff document '{record['filename']}'",
                            auth.get_current_user_name() or auth.get_current_user_id() or "staff",
                        )
                        st.session_state.pop(confirmation_key, None)
                        st.session_state.pop("staff_document_selected", None)
                        st.session_state.pop("staff_document_operation", None)
                        st.rerun()
                    else:
                        st.error("This document no longer exists.")
        with cancel_col:
            if st.button(
                "Cancel",
                key=f"confirm_delete_staff_document_no_{record['id']}",
                width="stretch",
            ):
                st.session_state.pop(confirmation_key, None)
                st.rerun()
    elif st.button(
        "Delete document",
        key=f"delete_staff_document_{record['id']}",
        type="secondary",
        icon=":material/delete:",
    ):
        st.session_state[confirmation_key] = True
        st.rerun()


def render_announcements(audit_fn: Callable[[str, str], None]) -> None:
    if not _require_staff():
        return
    st.markdown("## School Announcements")
    records = staff_content.load_announcements()
    options = {"Create announcement": None}
    options.update({
        f"{row.get('title', 'Untitled')} · {row.get('status', 'draft')} · {str(row.get('id', ''))[:8]}": row.get("id")
        for row in records
    })
    selected = st.selectbox("Announcement", list(options), key="staff_announcement_selection")
    selected_id = options[selected]
    current = next((row for row in records if row.get("id") == selected_id), {})
    with st.form("staff_announcement_form"):
        title = st.text_input("Title", value=current.get("title", ""), max_chars=160)
        body = st.text_area("Announcement", value=current.get("body", ""), height=180, max_chars=12000)
        schedule = st.checkbox("Schedule for a future date", value=False)
        publish_on = st.date_input(
            "Publication date",
            value=date.fromisoformat(current["publish_on"]) if current.get("publish_on") else date.today(),
            disabled=not schedule,
        )
        submitted = st.form_submit_button("Save and publish / schedule", type="primary")
    if submitted:
        try:
            record = staff_content.save_announcement(
                title,
                body,
                auth.get_current_user_id() or "",
                publish_on if schedule else None,
                str(selected_id) if selected_id else None,
            )
        except (OSError, ValueError) as error:
            st.error(f"Could not save announcement: {error}")
        else:
            audit_fn(f"Saved announcement '{record['title']}' ({record['status']})", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
            st.success(f"Announcement {record['status']}.")
            st.rerun()

    if selected_id and current.get("status") != "archived":
        if st.button("Archive announcement", key="staff_archive_announcement"):
            try:
                staff_content.set_announcement_status(str(selected_id), "archived", auth.get_current_user_id() or "")
            except (OSError, ValueError) as error:
                st.error(f"Could not archive announcement: {error}")
            else:
                audit_fn("Archived a school announcement", auth.get_current_user_name() or auth.get_current_user_id() or "staff")
                st.success("Announcement archived.")
                st.rerun()
    if records:
        st.markdown("### Announcement history")
        st.dataframe(
            pd.DataFrame([
                {
                    "Title": row.get("title"),
                    "Status": row.get("status"),
                    "Publication date": row.get("publish_on"),
                    "Last updated": row.get("updated_at"),
                    "Updated by": row.get("updated_by"),
                }
                for row in records
            ]),
            width="stretch",
            hide_index=True,
        )


def render(
    section: str,
    audit_fn: Callable[[str, str], None],
    chat_fn: Callable[[], None],
) -> None:
    if not _require_staff():
        return
    pages = {
        "analytics": lambda: render_analytics(audit_fn),
        "review": lambda: render_question_review(audit_fn),
        "documents": lambda: render_documents(audit_fn),
    }
    if section == "dashboard":
        render_dashboard()
    elif section == "inquiries":
        st.session_state["staff_chat_heading"] = "Student Inquiries"
        chat_fn()
    elif section == "knowledge_announcements":
        selected_area = st.radio(
            "Workspace",
            ["Knowledge Base", "School Announcements"],
            horizontal=True,
            key="staff_knowledge_announcements_tab",
            label_visibility="collapsed",
        )
        if selected_area == "Knowledge Base":
            render_knowledge_base(audit_fn)
        else:
            render_announcements(audit_fn)
    elif section in pages:
        pages[section]()
    else:
        render_dashboard()
