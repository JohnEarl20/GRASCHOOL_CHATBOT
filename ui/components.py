"""Reusable presentation components.

Every function here draws markup or a widget and returns nothing the caller
needs. Business logic stays in `code/` - these helpers only decide how
something looks. Anything that could mislead a reader (sample data, a draft
value, an unsupported feature) is labelled inside the component that shows it,
so the warning cannot be dropped by forgetting to add it on a screen.
"""
from __future__ import annotations

import base64
import html

import streamlit as st

from ui.theme import icon


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


# --------------------------------------------------------------------------
# Brand and navigation
# --------------------------------------------------------------------------
def brand(subtitle: str = "Cognitive Campus Assistant") -> None:
    """The school mark and wordmark shown at the top of the sidebar."""
    st.markdown(
        f"<div class='cca-brand'>"
        f"<div class='cca-brand-mark'>{icon('shield', 21, '#FFFFFF')}</div>"
        f"<div><div class='cca-brand-name'>GRA SCHOOL</div>"
        f"<div class='cca-brand-sub'>{_esc(subtitle)}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def nav_label(text: str) -> None:
    """A small uppercase section label above a group of nav buttons."""
    st.markdown(f"<div class='cca-nav-label'>{_esc(text)}</div>", unsafe_allow_html=True)


def nav_button(label: str, icon_name: str, active: bool, key: str) -> bool:
    """One sidebar nav entry. Returns True when it was clicked."""
    colour = "#FFFFFF" if active else "#A3B0D4"
    st.markdown(
        f"<div class='cca-nav-row' data-active='{str(active).lower()}'>"
        f"{icon(icon_name, 17, colour)}"
        f"<span>{_esc(label)}</span></div>",
        unsafe_allow_html=True,
    )
    # The visible row above is decoration; the real control is invisible but
    # focusable, so keyboard users can still reach it.
    return st.button(label, key=key, width="stretch")


def section_title(title: str, subtitle: str = "") -> None:
    st.markdown(f"### {_esc(title)}")
    if subtitle:
        st.markdown(
            f"<p class='cca-source' style='margin-top:-8px'>{_esc(subtitle)}</p>",
            unsafe_allow_html=True,
        )


def hero(title: str, body: str) -> None:
    st.markdown(
        f"<div class='cca-hero'><h1>{_esc(title)}</h1><p>{_esc(body)}</p></div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------
def kpi(label: str, value, note: str = "") -> None:
    """A KPI tile: label, big number, and an optional footnote."""
    note_html = f"<p class='cca-kpi-note'>{_esc(note)}</p>" if note else ""
    st.markdown(
        f"<div class='cca-kpi'><p class='cca-kpi-label'>{_esc(label)}</p>"
        f"<p class='cca-kpi-value'>{_esc(value)}</p>{note_html}</div>",
        unsafe_allow_html=True,
    )


def card(body_html: str) -> None:
    """Generic glass panel wrapping caller-supplied markup."""
    st.markdown(f"<div class='cca-card'>{body_html}</div>", unsafe_allow_html=True)


def badge(text: str, kind: str = "info") -> str:
    """Badge markup. kind is one of good, warn, info, danger."""
    return f"<span class='cca-badge cca-badge--{kind}'>{_esc(text)}</span>"


def sample_data_warning(synthetic: int, total: int) -> None:
    """Say plainly when the numbers on screen are synthetic."""
    if synthetic:
        st.warning(
            f"{synthetic} of the {total} logged turns are synthetic sample data from "
            "`scripts/seed_sample_logs.py`. They are not real students."
        )


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
def user_bubble(text: str, timestamp: str = "") -> None:
    ts = f"<div class='cca-ts'>{_esc(timestamp)}</div>" if timestamp else ""
    st.markdown(
        f"<div class='cca-bubble cca-bubble-user'>{_esc(text)}{ts}</div>",
        unsafe_allow_html=True,
    )


def bot_bubble(body_markdown: str) -> None:
    """Assistant bubble. The body is markdown, rendered by Streamlit itself."""
    with st.container():
        st.markdown("<div class='cca-bubble cca-bubble-bot'>", unsafe_allow_html=True)
        st.markdown(body_markdown)
        st.markdown("</div>", unsafe_allow_html=True)


def suggested_prompt(label: str, prompt: str, key: str) -> bool:
    """A suggested-prompt pill. Returns True when clicked."""
    return st.button(label, key=key, width="stretch")


# --------------------------------------------------------------------------
# Developer profiles
# --------------------------------------------------------------------------
def _portrait(photo_path, name: str) -> str:
    """Circular portrait markup: the real photo, or a gradient initial fallback.

    The image is inlined as a base64 data URI so the CSS mask can crop it to a
    circle - st.image cannot do that (it always draws a rectangle).
    """
    initial = _esc(name[:1].upper()) if name else "?"
    fallback = f"<div class='cca-dev-initial' aria-hidden='true'>{initial}</div>"
    if photo_path is None or not photo_path.is_file():
        return fallback
    try:
        encoded = base64.b64encode(photo_path.read_bytes()).decode("ascii")
    except OSError:
        return fallback
    return f"<img src='data:image/jpeg;base64,{encoded}' alt=''/>"


def developer_card(dev: dict, photo_path) -> None:
    """One profile card: circular portrait, name, role, and only what exists.

    No biography, links, or credentials are invented - if the profile file
    does not carry them, the card does not show them.

    Rendered with st.html, not st.markdown: the portrait is an inlined data
    URI of roughly 200 KB, and st.markdown's sanitizer drops a payload that
    large, which leaves the whole card blank.
    """
    name = dev.get("name", "")
    portrait = _portrait(photo_path, name)

    bio = dev.get("bio")
    bio_html = f"<p class='cca-dev-bio'>{_esc(bio)}</p>" if bio else ""
    st.html(
        f"<div class='cca-dev-card'>"
        f"<div class='cca-dev-portrait'>{portrait}</div>"
        f"<p class='cca-dev-name'>{_esc(name)}</p>"
        f"<p class='cca-dev-role'>{_esc(dev.get('role', ''))}</p>"
        f"{bio_html}</div>"
    )
