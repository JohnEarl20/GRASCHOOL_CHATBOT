"""GRA SCHOOL - Cognitive Campus Assistant.

    python -m streamlit run app.py

One app, four views behind a sidebar: the student AI assistant, a voice
upload page, the staff dashboard, and the developers page.

Presentation lives in `ui/`; everything about what the assistant knows and
says lives in `code/`. This file only wires the two together.

There is no login screen on purpose: this project has no authentication
system, and a password box that accepts anything would be fake security.
A student sees the student views only. The staff dashboard is reached through
a discreet "Staff access" entry at the bottom of the sidebar, behind a shared
passcode read from .env - see code/staff_gate.py for what that does and does
not protect.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from code import dialogue, forecast, knowledge, logger
from code import intent_model as intent_model_module
from code import staff_gate
from ui import components as C
from ui import theme

st.set_page_config(
    page_title="GRA SCHOOL - Cognitive Campus Assistant",
    page_icon="G",
    layout="wide",
    initial_sidebar_state="auto",
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
    ("dashboard", "Staff Dashboard", "chart"),
    ("developers", "Developers", "users"),
]

# Utility views sit at the bottom of the sidebar, below the staff entry, not in
# the main navigation. Order here is the order drawn: Settings, then Voice.
UTILITY_NAV = [
    ("settings", "Settings", "settings"),
    ("voice", "Voice Upload", "mic"),
]

ALL_VIEWS = {key for key, _, _ in NAV} | {key for key, _, _ in UTILITY_NAV}

SAMPLE_PROMPTS = [
    ("Enrollment requirements", "What do I need to enroll as a freshman?"),
    ("Can I enroll?", "Can I enroll? I am a transferee and I have my TOR"),
    ("Tuition and fees", "How much is the tuition fee and where do I pay?"),
    ("Academic calendar", "When is the payment deadline?"),
]


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

    # Deep links: ?view=dashboard opens that page directly. It still passes
    # through the passcode gate, so a shared link does not leak the analytics.
    requested = st.query_params.get("view")
    if requested in ALL_VIEWS:
        st.session_state.view = requested


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
def render_sidebar() -> None:
    session: dialogue.Session = st.session_state.session
    unlocked = staff_gate.is_unlocked()
    with st.sidebar:
        C.brand()

        # No Student/Staff switch: a student sees the student views only. Staff
        # reach the dashboard through the discreet "Staff access" entry at the
        # bottom, which leads to the passcode gate.
        C.nav_label("Navigation")
        for key, label, icon_name in NAV:
            if key == "dashboard" and not unlocked:
                continue
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

        st.divider()
        C.nav_label("This session")
        st.caption("What the assistant remembers while you chat. Nothing personal is stored.")
        st.markdown(f"**Student type:** {session.student_type or 'not stated yet'}")
        held = sorted(knowledge.DOCUMENT_LABELS.get(d, d) for d in session.documents_held)
        missing = sorted(knowledge.DOCUMENT_LABELS.get(d, d) for d in session.documents_missing)
        st.markdown(f"**Documents you have:** {', '.join(held) if held else 'none yet'}")
        st.markdown(f"**Documents missing:** {', '.join(missing) if missing else 'none yet'}")
        if session.fees_paid is not None:
            st.markdown(f"**Assessment fees:** {'paid' if session.fees_paid else 'not paid'}")

        if st.button("Start over", key="reset_session", width="stretch"):
            st.session_state.session = dialogue.new_session()
            st.session_state.messages = []
            st.rerun()

        st.divider()
        if unlocked:
            if st.button("Lock staff dashboard", key="lock_dashboard", width="stretch"):
                staff_gate.lock()
                st.session_state.view = "chat"
                st.query_params.pop("view", None)
                st.rerun()
        else:
            if st.button("Staff access", key="staff_entry", width="stretch"):
                st.session_state.view = "dashboard"
                st.query_params["view"] = "dashboard"
                st.rerun()

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
            "The staff dashboard opens through **Staff access** with the registrar "
            "passcode. Students stay on these pages."
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

    up, down, _ = st.columns([1, 1, 3])
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
    if message.get("feedback"):
        st.caption("Thanks - your feedback is logged for the registrar staff.")


def render_chat() -> None:
    school = knowledge.load()["meta"]["school"]
    C.hero(
        "AI Assistant",
        f"Ask anything about enrollment, requirements, fees, clearance or your "
        f"documents. Answers come from the {school} rule base and knowledge base, "
        "with a confidence score and the source shown.",
    )

    session: dialogue.Session = st.session_state.session
    if not st.session_state.messages:
        st.markdown("##### Suggested questions")
        cols = st.columns(2)
        for i, (label, prompt) in enumerate(SAMPLE_PROMPTS):
            with cols[i % 2]:
                if st.button(label, key=f"sample_{i}", width="stretch"):
                    st.session_state.pending = prompt
                    st.rerun()

    for index, message in enumerate(st.session_state.messages):
        if message["role"] == "user":
            with st.chat_message("user"):
                C.user_bubble(message["text"], message.get("ts", ""))
        else:
            with st.chat_message("assistant"):
                C.bot_bubble(message["text"])
                _render_answer_meta(index, message)

    prompt = st.session_state.pop("pending", None)
    typed = st.chat_input("Type your message here...")
    if typed:
        prompt = typed

    if prompt:
        st.session_state.messages.append(
            {"role": "user", "text": prompt, "ts": datetime.now().strftime("%H:%M")}
        )
        reply = dialogue.handle(prompt, session, policy=current_policy())
        st.session_state.messages.append(
            {
                "role": "assistant",
                "text": reply.text,
                "ts": datetime.now().strftime("%H:%M"),
                "meta": {
                    "intent": reply.intent,
                    "confidence": reply.confidence,
                    "source": reply.source,
                    "rules_fired": reply.rules_fired,
                    "facts": reply.facts,
                    "blockers": reply.blockers,
                    "clarified": reply.clarified,
                    "escalated": reply.escalated,
                    "sentiment": reply.sentiment,
                    "options": reply.options,
                    "decisive": reply.decisive,
                    "margin": reply.margin,
                },
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
    C.hero(
        "Dashboard",
        "What students asked, what the assistant could not answer, and what the "
        "registrar's office should do about it.",
    )

    head_left, head_right = st.columns([3, 1])
    with head_right:
        auto = st.toggle("Live update", value=True, key="live_update")
        interval = st.select_slider(
            "Refresh every",
            options=[2, 5, 10, 30, 60],
            value=5,
            key="live_interval",
            format_func=lambda s: f"{s}s",
            disabled=not auto,
        )

    # run_every re-runs only this fragment, so the dashboard keeps up with a
    # student chatting in another tab without reloading the whole page (which
    # would throw away the filter and search state).
    if auto:
        st.fragment(_dashboard_body, run_every=interval)()
    else:
        _dashboard_body()


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

    st.markdown("##### Unanswered questions")
    st.caption(
        "Every question the AI Assistant could not answer lands here, newest first. "
        "Add a question to the training set to teach the assistant about it."
    )
    if not missed:
        st.success("Nothing unanswered - every logged question got an answer.")
    else:
        real_count = sum(1 for row in missed if not row.get("synthetic"))
        fake_count = len(missed) - real_count

        filter_col, search_col = st.columns([1, 2])
        source = filter_col.radio(
            "Source",
            ["All", "Through the chat", "Sample seed"],
            horizontal=False,
            key="miss_source",
            help=(
                "Through the chat: a question typed into the AI Assistant, logged by the "
                "conversation layer. Sample seed: rows written by "
                "scripts/seed_sample_logs.py, which are not real students."
            ),
        )
        search = search_col.text_input("Search", key="miss_search")

        picked = missed
        if source == "Through the chat":
            picked = [r for r in missed if not r.get("synthetic")]
        elif source == "Sample seed":
            picked = [r for r in missed if r.get("synthetic")]

        if search:
            needle = search.lower()
            picked = [
                r for r in picked
                if needle in str(r.get("text", "")).lower()
                or needle in INTENT_LABELS.get(r.get("intent"), str(r.get("intent"))).lower()
            ]

        st.caption(
            f"{real_count} logged through the chat, {fake_count} from the sample seed. "
            f"Showing {len(picked)}, newest first."
        )

        if not picked:
            st.info("No unanswered questions match this filter.")
        else:
            rows = [
                {
                    "when": row.get("ts"),
                    "question": row.get("text"),
                    "guessed intent": INTENT_LABELS.get(row.get("intent"), row.get("intent")),
                    "confidence": row.get("confidence"),
                    "source": "sample seed" if row.get("synthetic") else "chat",
                }
                for row in reversed(picked)
            ]
            # A styled HTML table, not st.dataframe: the dataframe renders on
            # Streamlit's own light surface and cannot be recoloured, which left
            # dark text on white rows inside this dark dashboard.
            st.markdown(_unanswered_table_html(rows[:50]), unsafe_allow_html=True)

            # Label the row the staff member actually chose, not always the last one.
            labels = [f"{r['question']}  ({r['when']})" for r in rows[:50]]
            choice = st.selectbox("Question to label", labels, key="label_pick")
            options = list(intents.keys()) or ["ask_requirements"]
            label_col, button_col = st.columns([3, 1])
            chosen = label_col.selectbox("Label as", options, key="label_intent")
            if button_col.button("Add to training set", width="stretch"):
                index = labels.index(choice)
                text = rows[index]["question"]
                if text:
                    intent_model_module.add_staff_label(text, chosen)
                    st.success(f"Added to the training set: {text[:70]}")
        if st.button("Retrain the intent model"):
            with st.spinner("Retraining the intent model..."):
                metrics = intent_model_module.retrain()
            st.success(
                f"Retrained on {metrics['corpus_size']} labelled questions - "
                f"hold-out macro F1 {metrics['holdout_macro_f1']:.2f}."
            )

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
    C.hero(
        "Settings",
        "Everything on this page changes how the app behaves right now. Values that "
        "live in a file are saved to disk; session settings reset when you reload.",
    )

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("##### Assistant behaviour")
        st.caption(
            "These override the defaults in `code/dialogue.py` for this session only."
        )
        answer_at = st.slider(
            "Answer without asking back at confidence of at least",
            min_value=0.30,
            max_value=0.95,
            value=float(st.session_state.get("answer_threshold", dialogue.ANSWER_THRESHOLD)),
            step=0.05,
            format="%.2f",
            key="set_answer_threshold",
        )
        clarify_below = st.slider(
            "Fall back to 'I did not understand' below confidence",
            min_value=0.05,
            max_value=0.55,
            value=float(st.session_state.get("clarify_threshold", dialogue.CLARIFY_THRESHOLD)),
            step=0.05,
            format="%.2f",
            key="set_clarify_threshold",
        )
        if clarify_below >= answer_at:
            st.error(
                "The fallback threshold must stay below the answer threshold, "
                "otherwise no range is left for a clarifying question."
            )
        else:
            st.session_state["answer_threshold"] = answer_at
            st.session_state["clarify_threshold"] = clarify_below
            st.success(
                f"Active now: answer at {answer_at:.0%}, clarify between "
                f"{clarify_below:.0%} and {answer_at:.0%}, fall back below "
                f"{clarify_below:.0%}. The AI Assistant uses this immediately."
            )
            st.caption(
                "Stored for this session only. A page reload restores the defaults "
                "in `code/dialogue.py`."
            )

        st.markdown("")
        st.markdown("##### Dashboard")
        st.toggle("Live update", value=True, key="live_update")
        st.select_slider(
            "Refresh every",
            options=[2, 5, 10, 30, 60],
            value=st.session_state.get("live_interval", 5),
            key="set_live_interval",
            format_func=lambda s: f"{s}s",
            disabled=not st.session_state.get("live_update", True),
        )
        st.session_state["live_interval"] = st.session_state.get("set_live_interval", 5)

    with right:
        st.markdown("##### Appearance")
        st.radio(
            "Theme",
            ["Dark", "Light"],
            index=1 if st.session_state.get("app_theme") == "light" else 0,
            horizontal=True,
            key="theme_choice",
            help="Changes the whole interface immediately.",
        )
        chosen = st.session_state.get("theme_choice", "Dark")
        new_theme = "light" if chosen == "Light" else "dark"
        if new_theme != st.session_state.get("app_theme", "dark"):
            st.session_state["app_theme"] = new_theme
            st.rerun()

        st.markdown("")
        st.markdown("##### School and access")
        meta = knowledge.load()["meta"]
        st.markdown(f"**School:** {meta['school']}")
        st.markdown(f"**Term:** {meta['term']}")
        st.markdown(
            C.badge("Dashboard locked", "warn")
            if not staff_gate.is_unlocked()
            else C.badge("Dashboard unlocked", "good"),
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown("##### Session")
    session_data = st.session_state.session
    c1, c2, c3 = st.columns(3)
    with c1:
        C.kpi("Turns this session", session_data.turns)
    with c2:
        C.kpi("Chat messages", len(st.session_state.messages))
    with c3:
        C.kpi("Passcode attempts", staff_gate.MAX_ATTEMPTS - staff_gate.attempts_left())

    clear_col, reset_col = st.columns(2)
    if clear_col.button("Clear chat messages", width="stretch"):
        st.session_state.messages = []
        st.rerun()
    if reset_col.button("Reset the whole session", width="stretch"):
        st.session_state.session = dialogue.new_session()
        st.session_state.messages = []
        st.rerun()


# --------------------------------------------------------------------------
def main() -> None:
    init_state()
    theme.inject(st.session_state.get("app_theme", "dark"))
    render_sidebar()

    view = st.session_state.view
    if view == "chat":
        render_chat()
    elif view == "voice":
        render_voice()
    elif view == "dashboard":
        # The staff dashboard sits behind a passcode. Students keep the chat.
        if staff_gate.gate():
            render_dashboard()
    elif view == "developers":
        render_developers()
    elif view == "settings":
        render_settings()
    else:
        render_chat()


if __name__ == "__main__":
    main()
