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
from pathlib import Path

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
        f"<div class='cca-brand-mark'>{icon('shield', 21)}</div>"
        f"<div><div class='cca-brand-name'>GRA SCHOOL</div>"
        f"<div class='cca-brand-sub'>{_esc(subtitle)}</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def nav_label(text: str) -> None:
    """A small uppercase section label above a group of nav buttons."""
    st.markdown(f"<div class='cca-nav-label'>{_esc(text)}</div>", unsafe_allow_html=True)


def _data_uri(path) -> str:
    """Inline an image as a data URI.

    Streamlit's static file route is not guaranteed to be served in every
    deployment, and a broken <img> silently leaves an empty box. Inlining keeps
    the artwork with the markup. Returns "" when the file is missing, so the
    caller can fall back to the gradient rather than render a broken icon.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return ""
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def banner(title: str, accent: str, subtitle: str, note: str, art_path=None) -> None:
    """The hero banner at the top of the login page.

    Copy sits on the left; the artwork (a real PNG, inlined) sits on the right.
    The gradient and neon seam are CSS. When art_path is missing the banner
    keeps the copy and simply omits the image column.
    """
    art = _data_uri(art_path) if art_path else ""
    art_html = (
        f"<div class='cca-banner-art'><img src='{art}' alt='Holographic graduation "
        f"cap above books and a laptop' /></div>"
        if art
        else ""
    )
    style = "" if art else " style='grid-template-columns: 1fr;'"
    # st.html, not st.markdown: the inlined artwork is ~200 KB of base64 and
    # st.markdown's sanitizer drops a payload that large, leaving a blank card.
    st.html(
        f"<div class='cca-banner'{style}>"
        f"<div class='cca-banner-copy'>"
        f"<div class='cca-banner-mark'>{icon('cap', 28)}</div>"
        f"<p class='cca-banner-eyebrow'>Welcome to</p>"
        f"<h1 class='cca-banner-title'>GRA <span class='cca-banner-accent'>{_esc(accent)}</span></h1>"
        f"<p class='cca-banner-sub'>{_esc(subtitle)}</p>"
        f"<p class='cca-banner-note'>{_esc(note)}</p>"
        f"</div>"
        f"{art_html}"
        f"</div>"
    )


def mascot(caption: str = "GRA AI", path=None) -> str:
    """The friendly robot mascot markup, or "" when the image is missing.

    Returns the markup instead of drawing it so the caller can place it inside
    a wider block (the login row puts it beside the card) without Streamlit
    creating a new top-level element between them.
    """
    art = _data_uri(path) if path else ""
    if not art:
        return ""
    return (
        f"<div class='cca-mascot-wrap'>"
        f"<img class='cca-mascot' src='{art}' alt='GRA AI robot mascot' />"
        f"<p class='cca-mascot-caption'>{_esc(caption)}</p>"
        f"</div>"
    )


def login_card_open(title: str, lede: str, icon_name: str = "users") -> None:
    """Draw the login card's heading block.

    Only the heading lives here. The form below it is styled as its own glass
    panel by `[data-testid="stForm"]` in ui/theme.py - Streamlit cannot nest a
    widget inside a raw <div>, and the earlier attempt to fake that with
    sibling selectors left the inputs outside the card.
    """
    st.html(
        f"<div class='cca-login-card'>"
        f"<div class='cca-login-head'>"
        f"<span class='cca-login-icon'>{icon(icon_name, 20)}</span>"
        f"<h2 class='cca-login-title'>{_esc(title)}</h2></div>"
        f"<p class='cca-login-lede'>{_esc(lede)}</p>"
        f"</div>"
    )


def nav_button(label: str, icon_name: str, active: bool, key: str) -> bool:
    """One sidebar nav entry. Returns True when it was clicked."""
    # Icons inherit `currentColor` so they follow the same light/dark palette as
    # the label. A hard-coded hex here painted near-white glyphs on the pale
    # light-theme sidebar, where they were invisible.
    colour = "currentColor"
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


def user_profile_card(name: str, role: str, online: bool = True) -> None:
    """Futuristic User Profile Card matching the reference design."""
    avatar_svg = icon("user", 22, "#35D5FF")
    role_display = role.capitalize() if role else "Student"
    display_name = _esc(name or "User")
    st.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 12px;
            background: linear-gradient(135deg, rgba(8, 38, 83, 0.70) 0%, rgba(4, 18, 44, 0.85) 100%);
            border: 1px solid rgba(0, 153, 255, 0.45);
            border-radius: 14px;
            padding: 12px 14px;
            margin-bottom: 16px;
            box-shadow: 0 8px 24px -8px rgba(0, 191, 255, 0.35);
        ">
            <div style="
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: linear-gradient(135deg, rgba(10, 114, 234, 0.5), rgba(0, 191, 255, 0.5));
                border: 1.5px solid #00BFFF;
                display: grid;
                place-items: center;
                flex-shrink: 0;
            ">
                {avatar_svg}
            </div>
            <div style="overflow: hidden; flex: 1;">
                <div style="font-weight: 700; color: #FFFFFF; font-size: 0.95rem; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">
                    {display_name} <span style="font-size: 0.8rem; font-weight: normal; color: #A9BCD8;">({role_display})</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px; margin-top: 3px; font-size: 0.78rem; color: #A9BCD8;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background: #00E676; box-shadow: 0 0 8px #00E676; display: inline-block;"></span>
                    Online
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
