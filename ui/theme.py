"""Design system: tokens and global styles for the GRA SCHOOL assistant.

Presentation only - no business logic lives here. The palette follows the
reference: a deep navy canvas, royal blue and violet gradients, and
glassmorphism panels (translucent surfaces with a hairline border).

Colour values are chosen for contrast, not by eye. Every text colour used
against a surface below is at least 4.5:1 for body copy and 3:1 for large
text; the muted tone is the one to re-check if the canvas lightens.
"""
from __future__ import annotations

import streamlit as st

DARK_TOKENS = {
    # canvas and surfaces. The navy is cool and low-chroma so the blue/violet
    # accents are the only saturated things on the page; a warmer or lighter
    # base made the glass panels read as muddy grey.
    "--bg": "#020B20",
    "--bg-2": "#061A3A",
    "--sidebar-bg": "linear-gradient(180deg, rgba(6,26,58,0.92), rgba(2,11,32,0.94))",
    "--input-bg": "rgba(8, 24, 54, 0.86)",
    "--table-head-bg": "rgba(12, 34, 74, 0.82)",
    "--table-row-bg": "rgba(8, 24, 54, 0.62)",
    "--overlay": "linear-gradient(180deg, transparent 0%, rgba(2,11,32,0.55) 100%)",
    "--surface": "rgba(12, 34, 74, 0.62)",
    "--surface-solid": "#061A3A",
    "--surface-hover": "rgba(16, 44, 92, 0.78)",
    # accents: electric blue carries the brand, neon blue and cyan are the
    # glow highlights, violet stays as the gradient's far end.
    # The requested primary, #087CFF, measures 3.93:1 under white - below AA for
    # a button label. #0A72EA is the same hue, darkened just enough to reach
    # 4.56:1 white-on-blue while still reading as electric blue on the canvas.
    # #087CFF is kept for borders, icons and glow, where no text sits on it.
    "--primary": "#0A72EA",
    "--primary-2": "#087CFF",
    "--violet": "#7A5CFF",
    "--neon": "#00BFFF",
    "--accent": "#35D5FF",
    # text. White is 19.6:1 on --bg; secondary 10.15:1 - both comfortably AA.
    "--fg": "#FFFFFF",
    "--fg-muted": "#A9BCD8",
    "--fg-dim": "#7E93B4",
    # lines and states
    "--border": "rgba(0, 153, 255, 0.35)",
    "--border-strong": "rgba(0, 153, 255, 0.60)",
    "--primary-soft": "rgba(8, 124, 255, 0.16)",
    "--primary-soft-strong": "rgba(8, 124, 255, 0.30)",
    "--primary-glow": "rgba(0, 191, 255, 0.45)",
    "--success": "#34D399",
    "--success-soft": "rgba(52, 211, 153, 0.14)",
    "--warning": "#FBBF24",
    "--warning-soft": "rgba(251, 191, 36, 0.14)",
    "--danger": "#F87171",
    "--danger-soft": "rgba(248, 113, 113, 0.14)",
    # shape and motion
    "--radius-sm": "10px",
    "--radius": "16px",
    "--radius-lg": "22px",
    "--ease-out": "cubic-bezier(0.23, 1, 0.32, 1)",
    "--ease-in-out": "cubic-bezier(0.77, 0, 0.175, 1)",
}

# Light is not the dark palette inverted: the accents are darkened so text and
# borders keep at least 4.5:1 against the pale canvas, and the surfaces become
# near-opaque white glass instead of translucent navy.
LIGHT_TOKENS = {
    "--bg": "#F3F6FD",
    "--bg-2": "#E7EDF9",
    "--sidebar-bg": "linear-gradient(180deg, rgba(255,255,255,0.96), rgba(238,243,253,0.96))",
    "--input-bg": "rgba(255,255,255,0.95)",
    "--table-head-bg": "rgba(232,239,253,0.95)",
    "--table-row-bg": "rgba(255,255,255,0.85)",
    "--overlay": "linear-gradient(180deg, transparent 0%, rgba(226,233,247,0.45) 100%)",
    "--surface": "rgba(255, 255, 255, 0.82)",
    "--surface-solid": "#FFFFFF",
    "--surface-hover": "rgba(232, 239, 253, 0.95)",
    "--primary": "#1D4ED8",
    "--primary-2": "#6D28D9",
    "--violet": "#7C3AED",
    "--accent": "#0E7490",
    "--fg": "#0F1B3D",
    "--fg-muted": "#41507A",
    "--fg-dim": "#5B6B94",
    "--border": "rgba(29, 78, 216, 0.20)",
    "--border-strong": "rgba(29, 78, 216, 0.38)",
    "--success": "#047857",
    "--warning": "#B45309",
    "--danger": "#B91C1C",
    "--radius-sm": "10px",
    "--radius": "16px",
    "--radius-lg": "22px",
    "--ease-out": "cubic-bezier(0.23, 1, 0.32, 1)",
    "--ease-in-out": "cubic-bezier(0.77, 0, 0.175, 1)",
}

TOKENS = DARK_TOKENS  # default, kept for callers that import it directly

# Kept low on purpose: these glows sit behind body copy, and at their previous
# strength (0.20/0.18) the centre of the page lifted enough to soften the text.
_RADIAL_DARK = (
    "radial-gradient(1100px 620px at 12% -8%, rgba(47,107,255,0.14), transparent 62%),"
    "radial-gradient(900px 560px at 92% 4%, rgba(122,92,255,0.12), transparent 60%),"
    "radial-gradient(760px 520px at 50% 108%, rgba(34,211,238,0.06), transparent 60%)"
)

_RADIAL_LIGHT = (
    "radial-gradient(1100px 620px at 12% -8%, rgba(29,78,216,0.10), transparent 62%),"
    "radial-gradient(900px 560px at 92% 4%, rgba(109,40,217,0.08), transparent 60%),"
    "radial-gradient(760px 520px at 50% 108%, rgba(14,116,144,0.06), transparent 60%)"
)


def _token_block(tokens: dict) -> str:
    return "\n".join(f"  {name}: {value};" for name, value in tokens.items())


def _build_style(tokens: dict, radial: str) -> str:
    """The full stylesheet for one token set."""
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
{_token_block(tokens)}
}}

html, body, [class*="css"] {{
  font-family: 'Inter', -apple-system, 'Segoe UI', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}}

/* ---------- canvas ---------- */
/* The login wallpaper covers the whole viewport. It is served from
   /app/static/ (enableStaticServing in .streamlit/config.toml) rather than
   inlined, because the image is 1.9 MB - as a data URI it would add 2.4 MB of
   base64 to every rerun. `background-attachment: fixed` is dropped under
   900px, where several mobile browsers stall scrolling with a fixed cover. */
.stApp {{
  background:
    linear-gradient(180deg, rgba(2, 10, 30, 0.45) 0%, rgba(2, 10, 30, 0.62) 100%),
    url('/app/static/campus-bg.png') center center / cover no-repeat fixed,
    var(--bg);
  color: var(--fg);
}}
.stApp::before {{
  content: "";
  position: fixed;
  inset: 0;
  background: var(--overlay);
  pointer-events: none;
  z-index: 0;
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ position: relative; z-index: 1; }}

h1, h2, h3, h4, h5 {{
  font-family: 'Inter', system-ui, sans-serif;
  color: var(--fg);
  letter-spacing: -0.015em;
  font-weight: 600;
}}
p, li, label, span {{ color: var(--fg); }}
a {{ color: var(--accent); }}

/* ---------- sidebar ----------
   Translucent navy glass so the campus wallpaper shows through. Streamlit
   paints its own opaque surface on the sidebar and its inner scroll container,
   so both are cleared here; without this the sidebar is a solid block over the
   image. */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"],
[data-testid="stSidebar"] > div {{
  background: rgba(4, 14, 34, 0.55) !important;
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
}}
[data-testid="stSidebar"] {{
  border-right: 1px solid var(--border);
}}
/* Sidebar widgets keep the theme's text colour. `!important` is deliberate:
   Streamlit's own `[data-testid="stSidebar"] *` selectors paint secondary
   buttons with the framework's light-grey body colour, which on the dark
   canvas leaves the label barely readable. */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] a,
[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {{
  color: var(--fg) !important;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  color: var(--fg-muted) !important;
}}

/* the decoration tile around the inline SVG mark */
.cca-brand-mark {{ color: #FFFFFF; }}
[data-testid="stSidebarNav"] {{ display: none; }}

/* ---------- glass panels ---------- */
.cca-glass {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(18px) saturate(140%);
  box-shadow: 0 18px 44px -28px rgba(0,0,0,0.9), inset 0 1px 0 rgba(255,255,255,0.05);
  padding: 18px 20px;
}}

/* ---------- login page ----------
   A hero banner carrying the artwork, then one glass card holding the form.
   Every class below is emitted only by render_login() / components.banner(),
   so nothing here can shift another view. */

/* A faint blue aurora over the wallpaper. Kept deliberately weak: the campus
   image already carries the neon wave, and a stronger wash hid the building. */
.cca-login-aurora {{
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(680px 420px at 14% 8%, rgba(8,124,255,0.10), transparent 62%),
    radial-gradient(560px 380px at 86% 12%, rgba(0,191,255,0.08), transparent 64%);
  animation: cca-aurora 18s var(--ease-in-out) infinite alternate;
}}
@keyframes cca-aurora {{
  from {{ opacity: 0.75; transform: scale(1) translateY(0); }}
  to   {{ opacity: 1;    transform: scale(1.06) translateY(-12px); }}
}}
@media (prefers-reduced-motion: reduce) {{
  .cca-login-aurora {{ animation: none; }}
}}

/* hero banner: copy on the left, artwork on the right.
   The art column is capped rather than fixed, and the whole grid drops to one
   column on narrow screens - a hard 340px track left the copy a few characters
   wide, which wrapped the paragraph into single words per line. */
.cca-banner {{
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 340px);
  align-items: center;
  gap: 26px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  /* translucent, so the campus wallpaper reads through the hero as well */
  background:
    radial-gradient(620px 280px at 88% -20%, rgba(8,124,255,0.22), transparent 68%),
    linear-gradient(135deg, rgba(4,18,46,0.62) 0%, rgba(6,26,58,0.55) 52%, rgba(2,11,32,0.58) 100%);
  backdrop-filter: blur(16px) saturate(130%);
  -webkit-backdrop-filter: blur(16px) saturate(130%);
  padding: 30px 34px;
  margin-bottom: 18px;
  box-shadow: 0 26px 60px -40px var(--primary-glow);
}}
/* the thin neon seam along the top edge of the banner */
.cca-banner::before {{
  content: "";
  position: absolute;
  top: 0; left: 8%; right: 8%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--neon), transparent);
  opacity: 0.9;
}}
.cca-banner-copy {{ position: relative; z-index: 1; min-width: 0; }}
.cca-banner-mark {{
  display: inline-grid; place-items: center;
  width: 54px; height: 54px;
  border-radius: 15px;
  background: linear-gradient(135deg, var(--primary), var(--neon));
  color: #FFFFFF;
  box-shadow: 0 14px 34px -14px var(--primary-glow);
  margin-bottom: 16px;
}}
.cca-banner-eyebrow {{
  font-size: 0.78rem; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--accent); font-weight: 700; margin: 0 0 6px 0;
}}
.cca-banner-title {{
  font-size: 2.5rem; font-weight: 800; line-height: 1.06;
  letter-spacing: -0.03em; margin: 0 0 8px 0;
  color: var(--fg);
}}
.cca-banner-title .cca-banner-accent {{
  background: linear-gradient(100deg, var(--neon), var(--accent));
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
}}
.cca-banner-sub {{
  font-size: 1.06rem; font-weight: 600; color: var(--accent);
  margin: 0 0 12px 0;
}}
.cca-banner-note {{
  border-left: 3px solid var(--primary);
  padding-left: 14px;
  margin: 0;
  font-size: 0.9rem;
  color: var(--fg-muted);
  max-width: 58ch;
  line-height: 1.6;
}}
/* the artwork: a real image, so it is a plain <img> with its own glow */
.cca-banner-art {{
  position: relative;
  z-index: 1;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
  box-shadow: 0 20px 50px -26px var(--primary-glow);
  line-height: 0;
}}
.cca-banner-art img {{
  display: block;
  width: 100%;
  height: auto;
  object-fit: cover;
}}
/* the robot mascot, shown small beside the sidebar brand */
.cca-mascot {{
  display: block;
  width: 100%;
  max-width: 210px;
  margin: 14px auto 4px auto;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  box-shadow: 0 18px 40px -26px var(--primary-glow);
}}
.cca-mascot-caption {{
  text-align: center;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 700;
  margin: 0 0 10px 0;
}}

/* the login card.
   The form IS the card: styling [data-testid="stForm"] directly avoids the
   sibling-selector trick that left the widgets outside the panel. The heading
   above it is its own small block with matching side borders. */
.cca-login-card {{
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(10,30,66,0.92), rgba(4,16,40,0.94));
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  box-shadow: 0 30px 70px -40px var(--primary-glow), inset 0 1px 0 rgba(255,255,255,0.06);
  padding: 26px 30px 8px 30px;
  margin-bottom: 14px;
}}
.cca-login-head {{
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 6px;
}}
.cca-login-head .cca-login-icon {{
  width: 42px; height: 42px;
  display: grid; place-items: center;
  border-radius: 13px;
  background: linear-gradient(135deg, var(--primary), var(--neon));
  color: #FFFFFF;
  box-shadow: 0 12px 28px -14px var(--primary-glow);
  flex: 0 0 auto;
}}
.cca-login-title {{
  font-size: 1.7rem; font-weight: 700; color: var(--fg);
  margin: 0; letter-spacing: -0.02em;
}}
.cca-login-lede {{
  font-size: 0.9rem; color: var(--fg-muted);
  margin: 0 0 4px 0; line-height: 1.55;
}}
.cca-role-label {{
  font-size: 0.82rem; font-weight: 600; color: var(--fg);
  margin: 14px 0 8px 0;
}}

/* the form panel itself */
[data-testid="stForm"] {{
  background: linear-gradient(180deg, rgba(10,30,66,0.66), rgba(4,16,40,0.72)) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  box-shadow: 0 30px 70px -40px var(--primary-glow), inset 0 1px 0 rgba(255,255,255,0.06);
  padding: 24px 30px 26px 30px !important;
}}
[data-testid="stForm"] [data-testid="stTextInput"] > div > div {{
  border-radius: var(--radius-sm) !important;
  min-height: 46px !important;
  border-color: var(--border) !important;
}}
[data-testid="stForm"] [data-testid="stTextInput"] > div > div:focus-within {{
  border-color: var(--neon) !important;
  box-shadow: 0 0 0 3px var(--primary-soft), 0 0 22px -6px var(--primary-glow) !important;
}}
[data-testid="stFormSubmitButton"] button {{
  min-height: 48px !important;
  border-radius: var(--radius-sm) !important;
  font-weight: 700 !important;
  font-size: 1rem !important;
  letter-spacing: 0.01em;
  background: linear-gradient(135deg, var(--primary), var(--primary-2)) !important;
  border: none !important;
  color: #FFFFFF !important;
  box-shadow: 0 16px 36px -18px var(--primary-glow) !important;
}}
[data-testid="stFormSubmitButton"] button:hover {{
  background: linear-gradient(135deg, var(--primary-2), var(--neon)) !important;
  box-shadow: 0 18px 42px -16px var(--primary-glow) !important;
}}

/* footer row under the card: two real outlined buttons */
.cca-login-foot {{ margin-top: 0; }}
.cca-login-foot ~ div .stButton > button,
.cca-login-card ~ div .stButton > button {{
  min-height: 42px;
  border-radius: var(--radius-sm);
}}

/* ---------- brand ---------- */
.cca-brand {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 2px 16px 2px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}}
.cca-brand-mark {{
  width: 40px; height: 40px;
  border-radius: 12px;
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  box-shadow: 0 8px 22px -10px var(--primary-glow);
  flex: 0 0 auto;
}}
.cca-brand-name {{
  font-size: 1rem; font-weight: 700; letter-spacing: 0.06em;
  line-height: 1.15; color: var(--fg);
}}
.cca-brand-sub {{ font-size: 0.72rem; color: var(--fg-muted); letter-spacing: 0.02em; }}
.cca-brand-name, .cca-brand-sub {{ color: var(--fg); }}
.cca-brand-sub {{ color: var(--fg-muted); }}

/* ---------- nav ---------- */
.cca-nav-label {{
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--fg-dim); margin: 6px 0 10px 2px; font-weight: 600;
}}

/* ---------- cards ---------- */
.cca-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(18px) saturate(140%);
  padding: 18px 20px;
  transition: border-color 220ms var(--ease-out), transform 220ms var(--ease-out);
}}
@media (hover: hover) and (pointer: fine) {{
  .cca-card:hover {{ border-color: var(--border-strong); }}
}}

/* KPI */
.cca-kpi {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  backdrop-filter: blur(18px);
  position: relative;
  overflow: hidden;
}}
.cca-kpi::after {{
  content: "";
  position: absolute; inset: 0 auto auto 0;
  width: 100%; height: 2px;
  background: linear-gradient(90deg, var(--primary), var(--violet), transparent);
  opacity: 0.85;
}}
.cca-kpi-label {{
  font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--fg-muted); font-weight: 600; margin: 0 0 6px 0;
}}
.cca-kpi-value {{
  font-size: 1.85rem; font-weight: 700; color: var(--fg);
  margin: 0; line-height: 1.1; letter-spacing: -0.02em;
}}
.cca-kpi-note {{ font-size: 0.75rem; color: var(--fg-dim); margin: 6px 0 0 0; }}

/* ---------- chat ---------- */
[data-testid="stChatMessage"] {{
  background: transparent;
  border: none;
  padding: 2px 0;
}}
.cca-bubble {{
  border-radius: var(--radius);
  padding: 14px 16px;
  border: 1px solid var(--border);
  line-height: 1.62;
}}
.cca-bubble-bot {{
  background: var(--surface);
  backdrop-filter: blur(18px);
  border-top-left-radius: 6px;
}}
.cca-bubble-user {{
  background: linear-gradient(135deg, rgba(47, 107, 255, 0.30), rgba(122, 92, 255, 0.26));
  border-color: var(--border-strong);
  border-top-right-radius: 6px;
}}
.cca-answer {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-top: 8px;
}}
.cca-source {{ color: var(--fg-dim); font-size: 0.76rem; }}
.cca-ts {{ color: var(--fg-dim); font-size: 0.7rem; }}

/* ---------- badges ---------- */
.cca-badge {{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 11px;
  border-radius: 999px;
  font-size: 0.73rem; font-weight: 600;
  border: 1px solid transparent;
}}
.cca-badge--good {{ background: var(--success-soft); color: #6EE7B7; border-color: var(--success); }}
.cca-badge--warn {{ background: var(--warning-soft); color: #FCD34D; border-color: var(--warning); }}
.cca-badge--info {{ background: var(--primary-soft); color: var(--fg); border-color: var(--primary-soft-strong); }}
.cca-badge--danger {{ background: var(--danger-soft); color: #FCA5A5; border-color: var(--danger); }}

/* ---------- buttons ---------- */
.stButton > button, .stDownloadButton > button {{
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--input-bg);
  color: var(--fg);
  font-weight: 500;
  transition: background 200ms var(--ease-out), border-color 200ms var(--ease-out),
              transform 120ms var(--ease-out);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  background: var(--surface-hover);
  border-color: var(--border-strong);
}}
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {{
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}}
.stButton > button:active {{ transform: scale(0.985); }}
.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  border-color: transparent;
  color: #FFFFFF !important;
  box-shadow: 0 12px 28px -14px var(--primary-glow);
}}
/* children of a primary button must not fall back to the theme foreground */
.stButton > button[kind="primary"] *,
.stButton > button[kind="primary"] p {{
  color: #FFFFFF !important;
}}

/* ---------- segmented control (the login role switch) ----------
   Streamlit does not render these as .stButton. Each option is a BaseButton
   whose testid is built from its kind: `stBaseButton-segmented_control`, and
   `stBaseButton-segmented_controlActive` for the selected one. Targeting
   [data-testid="stButtonGroup"] button missed them, which is why the role
   switch kept rendering as two bare labels. */
[data-testid="stButtonGroup"] {{
  gap: 10px !important;
  background: transparent !important;
  padding: 0 !important;
  margin-bottom: 4px;
}}
[data-testid="stBaseButton-segmented_control"],
[data-testid="stBaseButton-segmented_controlActive"] {{
  border-radius: 999px !important;
  border: 1px solid var(--border) !important;
  background: var(--input-bg) !important;
  color: var(--fg-muted) !important;
  padding: 10px 26px !important;
  font-weight: 600 !important;
  box-shadow: none !important;
  transition: border-color 180ms var(--ease-out), background 180ms var(--ease-out),
              color 180ms var(--ease-out), box-shadow 180ms var(--ease-out);
}}
[data-testid="stBaseButton-segmented_control"]:hover {{
  border-color: var(--neon) !important;
  color: var(--fg) !important;
  background: var(--surface-hover) !important;
}}
[data-testid="stBaseButton-segmented_controlActive"] {{
  background: linear-gradient(135deg, var(--primary), var(--neon)) !important;
  border-color: transparent !important;
  color: #FFFFFF !important;
  box-shadow: 0 10px 26px -12px var(--primary-glow) !important;
}}
/* the option label follows the pill colour, never the global foreground */
[data-testid="stBaseButton-segmented_control"] *,
[data-testid="stBaseButton-segmented_controlActive"] * {{
  color: inherit !important;
  font-weight: 600 !important;
}}

/* ---------- inputs ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {{
  background: var(--input-bg) !important;
  border-color: var(--border) !important;
  color: var(--fg) !important;
  border-radius: var(--radius-sm) !important;
}}
input, textarea {{ color: var(--fg) !important; }}
input::placeholder, textarea::placeholder {{ color: var(--fg-dim) !important; }}
/* password / text inputs drawn by the browser's own widget */
[data-testid="stTextInput"] input,
[data-testid="stTextInputRootElement"],
[data-testid="stTextInput"] > div > div {{
  background: var(--input-bg) !important;
  color: var(--fg) !important;
  border-color: var(--border) !important;
}}
[data-testid="stTextInput"] input {{ -webkit-text-fill-color: var(--fg) !important; }}
[data-testid="stTextInput"] button {{ color: var(--fg-muted) !important; }}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 3px var(--primary-soft-strong) !important;
}}

[data-testid="stChatInput"] {{
  background: var(--input-bg) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
}}
[data-testid="stChatInput"] * {{
  background-color: transparent !important;
  color: var(--fg) !important;
}}
[data-testid="stChatInput"] textarea {{ color: var(--fg) !important; }}
[data-testid="stChatInput"] textarea::placeholder {{ color: var(--fg-dim) !important; }}
[data-testid="stChatInput"] button:hover {{ background-color: var(--primary-soft) !important; }}

/* Voice microphone button styling in chat */
div[data-testid="stPopover"] button {{
  border-radius: 999px !important;
  font-weight: 600 !important;
  border: 1px solid var(--border-strong) !important;
  background: linear-gradient(135deg, rgba(8, 38, 83, 0.85), rgba(6, 26, 58, 0.95)) !important;
  color: var(--neon) !important;
  box-shadow: 0 4px 16px -4px var(--primary-glow) !important;
  transition: all 200ms ease !important;
}}
div[data-testid="stPopover"] button:hover {{
  border-color: var(--neon) !important;
  color: #FFFFFF !important;
  transform: translateY(-1px);
  box-shadow: 0 6px 22px -4px var(--primary-glow) !important;
}}


/* Older baseweb button-group markup, still matched for any component that
   emits it. The segmented-control pills themselves are styled in the buttons
   section above, where they can win the cascade over .stButton. */
[data-baseweb="button-group"] button {{
  background: var(--input-bg) !important;
  color: var(--fg-muted) !important;
  border-color: var(--border) !important;
}}

/* ---------- tabs ---------- */
[data-baseweb="tab-list"] {{
  gap: 6px;
  background: var(--table-row-bg);
  padding: 5px;
  border-radius: 999px;
  border: 1px solid var(--border);
  width: fit-content;
}}
[data-baseweb="tab"] {{
  border-radius: 999px !important;
  padding: 7px 18px !important;
  color: var(--fg-muted) !important;
  background: transparent !important;
}}
[data-baseweb="tab"][aria-selected="true"] {{
  background: linear-gradient(135deg, var(--primary-glow), var(--primary-2)) !important;
  color: #FFFFFF !important;
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none; }}

/* ---------- Streamlit chrome: main menu, toolbar, dropdowns ----------
   Streamlit draws its overflow menu, popovers and dropdown lists on a light
   surface of its own, ignoring the app canvas. Without these rules the menu
   appears as a white panel with white text and is unreadable. */
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
  background: transparent !important;
}}
[data-testid="stToolbar"] button,
[data-testid="stMainMenu"] button,
[data-testid="stMainMenuButton"] {{
  color: var(--fg) !important;
  background: transparent !important;
}}
[data-testid="stMainMenu"] button:hover,
[data-testid="stMainMenuButton"]:hover {{
  background: var(--primary-soft) !important;
}}

/* the menu panel itself */
[data-testid="stMainMenu"] ul,
[data-testid="stMainMenuPopover"] ul,
div[role="menu"],
div[data-baseweb="menu"],
div[data-baseweb="popover"] > div,
ul[data-testid="stMainMenuList"] {{
  background: var(--surface-solid) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  box-shadow: 0 20px 44px -22px rgba(0,0,0,0.95) !important;
}}
div[role="menu"] li,
div[data-baseweb="menu"] li,
div[role="menuitem"],
li[role="menuitem"],
div[data-testid="stMainMenu"] li,
div[data-testid="stMainMenu"] a,
div[data-testid="stMainMenu"] span,
div[role="menu"] span {{
  background: transparent !important;
  color: var(--fg) !important;
}}
div[role="menuitem"]:hover,
li[role="menuitem"]:hover,
div[data-testid="stMainMenu"] li:hover,
div[role="menu"] li:hover {{
  background: var(--primary-soft-strong) !important;
}}
/* keyboard shortcuts shown on the right of a menu row */
div[role="menuitem"] kbd,
div[data-testid="stMainMenu"] kbd,
div[role="menu"] kbd {{
  color: var(--fg-dim) !important;
  background: var(--border) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
}}

/* select / radio / multiselect dropdown lists */
ul[role="listbox"],
div[data-baseweb="select"] ul,
div[data-baseweb="select"] li,
div[data-baseweb="menu"] div[role="option"] {{
  background: var(--surface-solid) !important;
  color: var(--fg) !important;
}}
div[role="option"]:hover,
li[role="option"]:hover,
div[data-baseweb="select"] li:hover {{
  background: var(--primary-soft-strong) !important;
}}
div[role="option"][aria-selected="true"] {{
  background: var(--primary-soft-strong) !important;
  color: #FFFFFF !important;
}}

/* tooltips and popovers */
div[data-baseweb="tooltip"],
div[data-baseweb="popover"] {{
  background: var(--surface-solid) !important;
  color: var(--fg) !important;
  border-radius: var(--radius-sm) !important;
}}

/* ---------- FORCE TEXT VISIBILITY IN DARK MODE ----------
   Ensure ALL text elements use the correct colors regardless of Streamlit's
   internal styling. This catches forms, markdown, metrics, and other widgets. */
.stApp[data-theme="dark"],
.stApp:not([data-theme="light"]) {{
  color-scheme: dark;
}}

/* Form containers and all their children */
.stForm, .stForm * {{
  color: var(--fg) !important;
}}
.stForm label, .stForm p, .stForm span, .stForm div {{
  color: var(--fg) !important;
}}

/* Markdown and text elements */
.stMarkdown, .stMarkdown *, .stText, .stText * {{
  color: var(--fg) !important;
}}

/* Metrics and KPIs */
[data-testid="stMetric"], [data-testid="stMetric"] * {{
  color: var(--fg) !important;
}}

/* Expanders */
[data-testid="stExpander"] summary, [data-testid="stExpander"] * {{
  color: var(--fg) !important;
}}

/* Captions and help text */
.stCaption, .stCaption *, [data-testid="stCaptionContainer"] * {{
  color: var(--fg-muted) !important;
}}

/* Radio, checkbox, selectbox labels */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label, 
[data-testid="stSelectbox"] label, [data-testid="stMultiselect"] label {{
  color: var(--fg) !important;
}}

/* Generic form submit buttons (register, staff login, settings).
   `--fg` is pure white in this palette, so a submit button that is NOT primary
   must keep a visible surface behind its label or the text disappears. The
   primary variant is painted by the gradient below and needs no text override -
   `color: #FFFFFF` here was fighting the button's own background. */
.stFormSubmitButton button {{
  color: var(--fg) !important;
  background: var(--input-bg) !important;
  border: 1px solid var(--border) !important;
}}
.stFormSubmitButton button[kind="primary"],
.stFormSubmitButton button[type="primary"] {{
  background: linear-gradient(135deg, var(--primary), var(--primary-2)) !important;
  border: none !important;
  color: #FFFFFF !important;
}}
.stFormSubmitButton button[kind="primary"] * {{
  color: #FFFFFF !important;
}}

/* Tabs */
[data-baseweb="tab"] {{
  color: var(--fg-muted) !important;
}}
[data-baseweb="tab"][aria-selected="true"] {{
  color: #FFFFFF !important;
}}

/* Alert messages */
[data-testid="stAlert"] {{
  color: var(--fg) !important;
}}
[data-testid="stAlert"] * {{
  color: var(--fg) !important;
}}

/* DataFrame */
[data-testid="stDataFrame"] {{
  color: var(--fg) !important;
}}

/* Chat messages */
[data-testid="stChatMessage"] {{
  color: var(--fg) !important;
}}
[data-testid="stChatMessage"] * {{
  color: var(--fg) !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
  color: var(--fg) !important;
}}
[data-testid="stSidebar"] * {{
  color: var(--fg) !important;
}}

/* Button text */
.stButton button, .stButton button * {{
  color: var(--fg) !important;
}}
.stButton button[kind="primary"], .stButton button[kind="primary"] * {{
  color: #FFFFFF !important;
}}

/* Input fields - ensure text is visible */
input, textarea, select {{
  color: var(--fg) !important;
  -webkit-text-fill-color: var(--fg) !important;
}}
input::placeholder, textarea::placeholder {{
  color: var(--fg-dim) !important;
}}

/* File uploader */
[data-testid="stFileUploaderDropzone"] {{
  color: var(--fg-muted) !important;
}}
[data-testid="stFileUploaderDropzone"] * {{
  color: var(--fg-muted) !important;
}}

/* Audio */
[data-testid="stAudioInput"], [data-testid="stAudio"] {{
  color: var(--fg) !important;
}}

/* Code blocks */
code, pre {{
  color: var(--fg) !important;
  background: var(--surface-solid) !important;
}}

/* Links */
a {{
  color: var(--accent) !important;
}}

/* ---------- unanswered table (styled HTML, not st.dataframe) ---------- */
.cca-table-wrap {{
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: auto;
  background: var(--table-row-bg);
}}
table.cca-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
}}
table.cca-table th {{
  text-align: left;
  padding: 10px 14px;
  color: var(--fg-muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  border-bottom: 1px solid var(--border);
  background: var(--table-head-bg);
  white-space: nowrap;
}}
table.cca-table td {{
  padding: 10px 14px;
  color: var(--fg);
  border-bottom: 1px solid rgba(122, 146, 214, 0.12);
  vertical-align: top;
}}
table.cca-table tbody tr:last-child td {{ border-bottom: none; }}
table.cca-table tbody tr:hover td {{ background: var(--primary-soft); }}
.cca-td-ts {{ color: var(--fg-dim) !important; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.cca-td-conf {{ font-variant-numeric: tabular-nums; }}

/* ---------- catch-all for remaining light surfaces ----------
   Streamlit ships some chrome (menus, the bottom input dock, dialogs) on a
   light surface that ignores the canvas. These rules paint every remaining
   portal-type surface dark so no white box with white text is left. */
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="drawer"] > div,
[role="dialog"],
[data-testid="stDialog"] > div,
[data-testid="stModal"] > div {{
  background: var(--surface-solid) !important;
  color: var(--fg) !important;
  border-color: var(--border) !important;
}}
[role="dialog"] *, [data-testid="stDialog"] * {{ color: var(--fg); }}

/* the bottom input dock keeps a light strip behind the chat box */
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"],
[data-testid="stAppViewBlockContainer"] ~ div[data-testid="stBottom"] {{
  background: transparent !important;
}}
[data-testid="stBottom"] {{ background: var(--bg) !important; }}

/* menu rows: covers both the button and list markup Streamlit has shipped */
[data-testid="stMainMenu"] li,
[data-testid="stMainMenu"] ul li,
[data-baseweb="menu"] li,
li[role="menuitem"] {{
  color: var(--fg) !important;
}}
[data-testid="stMainMenu"] li:hover,
[data-baseweb="menu"] li:hover,
li[role="menuitem"]:hover {{
  background: var(--primary-soft-strong) !important;
}}
[data-testid="stMainMenu"] hr,
[data-baseweb="menu"] hr {{
  border-color: var(--border) !important;
}}

/* ---------- expander, alerts, table ---------- */
[data-testid="stExpander"] {{
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  background: var(--table-row-bg) !important;
}}
[data-testid="stExpander"] summary {{ color: var(--fg-muted) !important; }}
[data-testid="stAlert"] {{
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--table-row-bg);
}}
[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: var(--radius); }}

/* Charts (Streamlit draws with Vega-Lite / canvas) */
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {{
  background: var(--table-row-bg) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 10px !important;
}}
[data-testid="stVegaLiteChart"] canvas,
[data-testid="stArrowVegaLiteChart"] canvas {{
  background: transparent !important;
  filter: invert(0.88) hue-rotate(180deg) saturate(1.15);
}}
[data-testid="stFileUploaderDropzone"] {{
  background: var(--input-bg) !important;
  border: 1px dashed var(--border-strong) !important;
  border-radius: var(--radius) !important;
  color: var(--fg-muted) !important;
}}
[data-testid="stFileUploaderDropzone"] * {{ color: var(--fg-muted) !important; }}
[data-testid="stFileUploaderDropzone"] button {{
  background: var(--input-bg) !important;
  border: 1px solid var(--border) !important;
  color: var(--fg) !important;
}}
[data-testid="stFileUploader"] small {{ color: var(--fg-dim) !important; }}

/* Audio recorder / player */
[data-testid="stAudioInput"], [data-testid="stAudio"] {{
  background: var(--input-bg) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 8px !important;
}}
[data-testid="stAudioInput"] * {{ color: var(--fg) !important; }}
audio {{ filter: invert(0.92) hue-rotate(180deg); border-radius: 999px; }}

/* ---------- developer cards ---------- */
.cca-dev-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }}
.cca-dev-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 22px 18px;
  text-align: center;
  position: relative;
  transition: transform 240ms var(--ease-out), border-color 240ms var(--ease-out);
}}
.cca-dev-card::before {{
  content: "";
  position: absolute; inset: -1px;
  border-radius: var(--radius-lg);
  padding: 1px;
  background: linear-gradient(140deg, rgba(47, 107, 255, 0.75), rgba(139, 92, 246, 0.55), transparent 70%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  opacity: 0;
  transition: opacity 240ms var(--ease-out);
  pointer-events: none;
}}
@media (hover: hover) and (pointer: fine) {{
  .cca-dev-card:hover {{ transform: translateY(-3px); }}
  .cca-dev-card:hover::before {{ opacity: 1; }}
}}
.cca-dev-portrait {{
  width: 96px; height: 96px;
  margin: 0 auto 14px auto;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid rgba(139,92,246,0.55);
  box-shadow: 0 0 0 4px var(--primary-soft), 0 14px 30px -16px var(--primary-glow);
}}
.cca-dev-portrait img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.cca-dev-initial {{
  width: 100%; height: 100%; display: grid; place-items: center;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: #fff; font-weight: 700; font-size: 1.6rem;
}}
.cca-dev-name {{ font-size: 1rem; font-weight: 600; color: var(--fg); margin: 0 0 2px 0; }}
.cca-dev-role {{
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--fg); margin: 0 0 8px 0;
}}
.cca-dev-bio {{ font-size: 0.82rem; color: var(--fg-muted); line-height: 1.5; margin: 0; }}

/* ---------- hero ---------- */
.cca-hero {{
  background: linear-gradient(135deg, var(--primary-soft), rgba(122, 92, 255, 0.14) 55%, rgba(34, 211, 238, 0.10));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 26px 28px;
  margin-bottom: 18px;
  backdrop-filter: blur(16px);
}}
.cca-hero h1 {{ font-size: 1.6rem; margin: 0 0 6px 0; }}
.cca-hero p {{ margin: 0; color: var(--fg-muted); font-size: 0.92rem; max-width: 62ch; }}

/* ---------- Advanced Futuristic Settings Dashboard Styling ---------- */
.cca-settings-header {{
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-strong);
  background:
    radial-gradient(650px 260px at 85% 0%, rgba(0, 191, 255, 0.18), transparent 70%),
    linear-gradient(135deg, rgba(6, 26, 58, 0.85) 0%, rgba(2, 11, 32, 0.90) 100%);
  backdrop-filter: blur(20px) saturate(140%);
  -webkit-backdrop-filter: blur(20px) saturate(140%);
  padding: 24px 30px;
  margin-bottom: 18px;
  box-shadow: 0 20px 48px -20px var(--primary-glow), inset 0 1px 0 rgba(255, 255, 255, 0.10);
}}
.cca-settings-header::before {{
  content: "";
  position: absolute;
  top: 0; left: 5%; right: 5%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--neon), var(--accent), transparent);
  opacity: 0.95;
}}
.cca-settings-title-row {{
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 6px;
}}
.cca-settings-icon-badge {{
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary), var(--neon));
  display: grid;
  place-items: center;
  color: #FFFFFF;
  box-shadow: 0 10px 24px -8px var(--primary-glow);
  flex-shrink: 0;
}}
.cca-settings-title {{
  font-size: 1.9rem;
  font-weight: 800;
  letter-spacing: -0.025em;
  color: #FFFFFF;
  margin: 0;
  line-height: 1.15;
}}
.cca-settings-subtitle {{
  font-size: 0.93rem;
  color: var(--fg-muted);
  margin: 0 0 0 58px;
  max-width: 75ch;
  line-height: 1.45;
}}

/* Quick Center / Futuristic Card Grids */
.cca-futuristic-card {{
  position: relative;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: linear-gradient(145deg, rgba(8, 38, 83, 0.55) 0%, rgba(4, 18, 44, 0.70) 100%);
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  box-shadow: 0 16px 36px -18px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  padding: 18px 20px;
  margin-bottom: 14px;
  transition: all 240ms var(--ease-out);
}}
.cca-futuristic-card:hover {{
  border-color: var(--neon);
  box-shadow: 0 18px 42px -16px var(--primary-glow);
  transform: translateY(-2px);
}}
.cca-card-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(0, 153, 255, 0.20);
  padding-bottom: 10px;
}}
.cca-card-head-title {{
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.05rem;
  font-weight: 700;
  color: #FFFFFF;
  margin: 0;
}}
.cca-card-icon {{
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: linear-gradient(135deg, rgba(10, 114, 234, 0.35), rgba(0, 191, 255, 0.35));
  border: 1px solid var(--border);
  display: grid;
  place-items: center;
  color: var(--neon);
}}

/* Status indicator dot */
.cca-dot {{
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
}}
.cca-dot--green {{
  background: #00E676;
  box-shadow: 0 0 10px #00E676;
}}
.cca-dot--yellow {{
  background: #FFC107;
  box-shadow: 0 0 10px #FFC107;
}}
.cca-dot--red {{
  background: #FF5252;
  box-shadow: 0 0 10px #FF5252;
}}

/* System Status List Row */
.cca-status-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 0;
  font-size: 0.88rem;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
}}
.cca-status-row:last-child {{
  border-bottom: none;
}}
.cca-status-key {{
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--fg-muted);
}}
.cca-status-val {{
  display: flex;
  align-items: center;
  font-weight: 600;
  color: #FFFFFF;
}}

/* Settings Navigation Buttons */
div[data-testid="stHorizontalBlock"] .cca-cat-btn button {{
  min-height: 40px !important;
  font-size: 0.86rem !important;
  border-radius: 12px !important;
  letter-spacing: 0.02em;
}}


/* ---------- responsive ---------- */
@media (max-width: 768px) {{
  .cca-hero {{ padding: 20px 18px; }}
  .cca-hero h1 {{ font-size: 1.3rem; }}
  .cca-kpi-value {{ font-size: 1.5rem; }}
  [data-baseweb="tab"] {{ padding: 6px 12px !important; font-size: 0.85rem !important; }}

  /* the hero banner stacks on a phone: copy first, artwork under it. Without
     this the two-column grid squeezed the paragraph to a few characters a line. */
  .cca-banner {{
    grid-template-columns: 1fr !important;
    padding: 22px 20px;
    gap: 18px;
  }}
  .cca-banner-title {{ font-size: 1.9rem; }}
  .cca-banner-sub {{ font-size: 0.98rem; }}
  .cca-banner-art {{ max-width: 320px; margin: 0 auto; }}
  .cca-login-card {{ padding: 20px 20px 6px 20px; }}
  [data-testid="stForm"] {{ padding: 18px 20px 20px 20px !important; }}

  /* Nav buttons fill the sidebar width on a phone, which makes each label
     read as a full-width bar. Cap them and left-align the text. */
  .stButton > button {{ padding: 6px 14px !important; }}
  [data-testid="stSidebar"] .stButton > button {{
    justify-content: flex-start !important;
    text-align: left !important;
  }}
  [data-testid="stSidebar"] .stButton > button p {{
    text-align: left !important;
    width: 100%;
    font-size: 0.9rem;
  }}
  .cca-brand-name {{ font-size: 0.95rem; }}
}}

/* ---------- mobile: phone & tablet ---------- */
@media (max-width: 768px) {{
  /* Sidebar: narrower, touch-friendly nav buttons */
  [data-testid="stSidebar"],
  [data-testid="stSidebarContent"],
  [data-testid="stSidebar"] > div {{
    width: 260px !important;
    min-width: 260px !important;
  }}
  [data-testid="stSidebar"] .stButton > button {{
    min-height: 48px !important;
    padding: 10px 14px !important;
    font-size: 0.95rem !important;
    justify-content: flex-start !important;
    text-align: left !important;
  }}
  [data-testid="stSidebar"] .stButton > button p {{
    text-align: left !important;
    width: 100% !important;
    font-size: 0.95rem !important;
  }}

  /* Main content: full width, reduced padding */
  [data-testid="stMainBlockContainer"] {{
    padding: 4px 8px !important;
    max-width: 100% !important;
  }}

  /* Chat bubbles: stack, word-wrap, narrower */
  .cca-bubble {{
    max-width: 92% !important;
    padding: 10px 12px !important;
    font-size: 0.9rem !important;
    line-height: 1.55 !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
  }}
  .cca-bubble-user {{ margin-left: auto !important; }}
  .cca-bubble-bot {{ margin-right: auto !important; }}

  /* Chat input: full width, touch-friendly */
  [data-testid="stChatInput"] {{
    min-height: 52px !important;
    border-radius: 14px !important;
    padding: 4px 8px !important;
  }}
  [data-testid="stChatInput"] textarea {{
    min-height: 44px !important;
    font-size: 1rem !important;
  }}

  /* Buttons: minimum 44px touch target */
  .stButton > button, .stDownloadButton > button {{
    min-height: 44px !important;
    font-size: 0.95rem !important;
    padding: 10px 16px !important;
  }}
  .stButton > button p, .stDownloadButton > button p {{
    font-size: 0.95rem !important;
  }}

  /* Inputs: full width, larger touch targets */
  [data-testid="stTextInput"] > div > div {{
    min-height: 48px !important;
    font-size: 1rem !important;
  }}
  [data-baseweb="select"] > div,
  [data-baseweb="input"],
  [data-baseweb="textarea"] {{
    min-height: 48px !important;
    font-size: 1rem !important;
  }}

  /* Cards: full width, reduced padding */
  .cca-card, .cca-glass, .cca-futuristic-card {{
    padding: 14px 16px !important;
    margin: 0 4px 12px 4px !important;
  }}
  .cca-hero {{
    padding: 16px 18px !important;
    margin: 0 4px 12px 4px !important;
  }}
  .cca-hero h1 {{ font-size: 1.4rem !important; }}
  .cca-hero p {{ font-size: 0.9rem !important; }}
  .cca-login-card {{
    padding: 18px 20px 6px 20px !important;
    margin: 0 8px 12px 8px !important;
  }}

  /* KPI cards: smaller value text */
  .cca-kpi {{
    padding: 14px 16px !important;
    margin: 0 4px 12px 4px !important;
  }}
  .cca-kpi-value {{ font-size: 1.4rem !important; }}
  .cca-staff-kpi {{
    padding: 12px 14px !important;
    margin: 0 4px 10px 4px !important;
    min-height: 100px !important;
  }}
  .cca-staff-kpi-value {{ font-size: 1.4rem !important; }}

  /* Tables: horizontal scroll, smaller font */
  table.cca-table {{ font-size: 0.8rem !important; }}
  table.cca-table th, table.cca-table td {{
    padding: 8px 10px !important;
    white-space: nowrap !important;
  }}
  .cca-table-wrap {{
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
  }}
  .cca-staff-table-wrap {{
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
  }}
  .cca-staff-table {{
    min-width: 600px !important;
    font-size: 0.7rem !important;
  }}
  .cca-staff-table th, .cca-staff-table td {{
    padding: 7px 6px !important;
    white-space: nowrap !important;
  }}

  /* Expanders and forms */
  [data-testid="stExpander"] {{
    margin: 0 4px 12px 4px !important;
  }}
  .stForm {{
    margin: 0 4px 12px 4px !important;
  }}

  /* Developer grid: single column */
  .cca-dev-grid {{
    grid-template-columns: 1fr !important;
  }}
  .cca-dev-card {{
    padding: 18px 16px !important;
  }}

  /* Tabs: horizontal scroll */
  [data-baseweb="tab-list"] {{
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
    white-space: nowrap !important;
  }}
  [data-baseweb="tab"] {{
    padding: 6px 12px !important;
    font-size: 0.85rem !important;
    white-space: nowrap !important;
  }}

  /* Badges: smaller */
  .cca-badge {{
    font-size: 0.68rem !important;
    padding: 2px 9px !important;
  }}

  /* Section headings */
  .cca-staff-section-heading,
  .cca-nav-label {{
    font-size: 0.85rem !important;
    margin: 12px 8px 6px 8px !important;
  }}

  /* Staff quick actions: full-width buttons */
  .st-key-staff-quick-actions button {{
    min-height: 48px !important;
    font-size: 0.85rem !important;
    padding: 10px 14px !important;
  }}

  /* Document upload dropzone */
  [data-testid="stFileUploaderDropzone"] {{
    min-height: 100px !important;
    padding: 16px !important;
  }}

  /* Audio players: full width */
  audio {{ width: 100% !important; }}

  /* Hide heavy decorative aurora on mobile */
  .cca-login-aurora {{ opacity: 0.4 !important; }}
}}

@media (max-width: 480px) {{
  /* Phone: tighter still */
  [data-testid="stSidebar"] {{
    width: 240px !important;
    min-width: 240px !important;
  }}
  [data-testid="stMainBlockContainer"] {{
    padding: 2px 6px !important;
  }}
  .cca-bubble {{
    max-width: 95% !important;
    padding: 8px 10px !important;
    font-size: 0.85rem !important;
  }}
  .cca-hero h1 {{ font-size: 1.25rem !important; }}
  .cca-kpi-value {{ font-size: 1.25rem !important; }}
  .cca-staff-kpi-value {{ font-size: 1.25rem !important; }}
  .stButton > button, .stDownloadButton > button {{
    min-height: 48px !important;
    font-size: 0.9rem !important;
    padding: 10px 14px !important;
  }}
  [data-testid="stTextInput"] > div > div {{
    min-height: 46px !important;
    font-size: 0.95rem !important;
  }}
  .cca-banner-title {{ font-size: 1.7rem !important; }}
  .cca-banner-sub {{ font-size: 0.95rem !important; }}
}}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }}
  .cca-dev-card:hover {{ transform: none; }}
}}

/* ---------- staff workspace ---------- */
.cca-analytics-hero {{
  margin-bottom: 14px;
  padding: 18px 22px;
  border: 1px solid rgba(0,168,255,0.46);
  border-radius: 17px;
  background:
    radial-gradient(ellipse at 92% 18%, rgba(0,168,255,0.16), transparent 36%),
    linear-gradient(110deg, rgba(3,21,47,0.96), rgba(8,38,83,0.72));
  box-shadow: inset 0 1px rgba(255,255,255,0.06), 0 10px 28px rgba(0,55,140,0.16);
}}
.cca-analytics-hero span {{
  color: #35D5FF;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}}
.cca-analytics-hero h1 {{
  margin: 3px 0 2px;
  color: #FFFFFF;
  font-size: clamp(1.45rem, 2.4vw, 2rem);
}}
.cca-analytics-hero p {{
  margin: 0;
  color: #C0D4F0;
  font-size: 0.86rem;
}}
#analytics-kpi-row .cca-staff-kpi {{
  min-height: 116px;
}}
.cca-print-button {{
  width: 100%;
  min-height: 42px;
  border: 1px solid rgba(0,168,255,0.5);
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(8,49,101,0.94), rgba(3,20,47,0.94));
  color: #FFFFFF;
  font: inherit;
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}}
.cca-print-button:hover {{
  border-color: #00DFFF;
  box-shadow: 0 6px 20px rgba(0,168,255,0.18);
}}
@media print {{
  [data-testid="stSidebar"], [data-testid="stHeader"], .stButton,
  .stDownloadButton, [data-testid="stToolbar"] {{
    display: none !important;
  }}
  .stApp, [data-testid="stMain"] {{
    background: #FFFFFF !important;
    color: #111827 !important;
  }}
}}
.cca-staff-hero {{
  min-height: 130px;
  padding: 22px 26px;
  border: 1px solid rgba(0,168,255,0.55);
  border-radius: 20px;
  background:
    radial-gradient(ellipse at 86% 20%, rgba(0,168,255,0.24), transparent 44%),
    linear-gradient(110deg, rgba(3,21,47,0.96), rgba(8,38,83,0.78));
  box-shadow: inset 0 1px rgba(255,255,255,0.08), 0 12px 34px rgba(0,75,180,0.22);
}}
.cca-staff-hero-eyebrow {{
  color: #35D5FF;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.14em;
}}
.cca-staff-hero h1 {{
  margin: 5px 0 4px;
  color: #FFFFFF;
  font-size: clamp(1.7rem, 3vw, 2.45rem);
  letter-spacing: 0.02em;
}}
.cca-staff-hero p {{
  margin: 0;
  color: #C0D4F0;
  font-size: 0.92rem;
}}
.cca-staff-kpi {{
  height: 100%;
  min-height: 120px;
  box-sizing: border-box;
  padding: 13px 14px;
  border: 1px solid rgba(0,168,255,0.48);
  border-radius: 15px;
  background: linear-gradient(145deg, rgba(8,38,83,0.94), rgba(3,19,45,0.94));
  box-shadow: inset 0 1px rgba(255,255,255,0.06), 0 8px 26px rgba(0,40,120,0.18);
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}}
.cca-staff-kpi:hover {{
  transform: translateY(-2px);
  border-color: rgba(0,223,255,0.82);
  box-shadow: 0 10px 28px rgba(0,132,255,0.2);
}}
.cca-staff-kpi-icon {{
  height: 25px;
  margin-bottom: 5px;
}}
.cca-staff-kpi-value {{
  color: #FFFFFF;
  font-size: 1.65rem;
  font-weight: 750;
  line-height: 1.1;
}}
.cca-staff-kpi-label {{
  margin-top: 4px;
  color: #FFFFFF;
  font-size: 0.79rem;
  font-weight: 650;
}}
.cca-staff-kpi-note {{
  margin-top: 3px;
  color: #A9BCD8;
  font-size: 0.68rem;
  line-height: 1.25;
}}
.cca-staff-section-heading {{
  margin: 18px 0 9px;
  color: #FFFFFF;
  font-size: 1.05rem;
  font-weight: 750;
}}
.cca-staff-panel-title {{
  margin: 0 0 8px;
  color: #FFFFFF;
  font-size: 0.95rem;
  font-weight: 700;
}}
.cca-staff-stat-row {{
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 40px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(110,157,220,0.18);
}}
.cca-staff-stat-icon {{
  display: flex;
  flex: 0 0 18px;
}}
.cca-staff-stat-name {{
  flex: 1;
  color: #FFFFFF;
  font-size: 0.77rem;
}}
.cca-staff-stat-name small {{
  display: block;
  margin-top: 2px;
  color: #A9BCD8;
  font-size: 0.66rem;
}}
.cca-staff-stat-row strong {{
  color: #FFFFFF;
  font-size: 0.83rem;
  text-align: right;
}}
.cca-staff-system-value--healthy {{ color: #00E676 !important; }}
.cca-staff-system-value--unhealthy {{ color: #FF6478 !important; }}
.cca-staff-system-value--unknown {{ color: #FFC107 !important; }}
.cca-staff-table-wrap {{
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid rgba(0,168,255,0.38);
  border-radius: 13px;
  background: rgba(3,18,43,0.78);
}}
.cca-staff-table {{
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  color: #FFFFFF;
  font-size: 0.76rem;
}}
.cca-staff-table th {{
  padding: 10px 9px;
  background: rgba(8,45,94,0.9);
  color: #C0D4F0;
  text-align: left;
  white-space: nowrap;
}}
.cca-staff-table td {{
  padding: 9px;
  border-top: 1px solid rgba(110,157,220,0.16);
  color: #E8F1FF;
  vertical-align: top;
}}
.cca-staff-question {{ min-width: 220px; max-width: 390px; }}
.cca-staff-status {{
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(169,188,216,0.16);
  color: #DCEBFF;
  white-space: nowrap;
}}
.cca-staff-status--resolved {{ background: rgba(0,230,118,0.18); color: #69F0AE; }}
.cca-staff-status--pending {{ background: rgba(255,193,7,0.18); color: #FFD54F; }}
.cca-staff-status--unanswered {{ background: rgba(255,59,79,0.2); color: #FF7B88; }}
.cca-staff-insight {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0 0 8px;
  padding: 11px 12px;
  border: 1px solid rgba(0,168,255,0.3);
  border-radius: 13px;
  background: linear-gradient(130deg, rgba(8,38,83,0.76), rgba(3,17,40,0.78));
}}
.cca-staff-insight-mark {{ display: flex; padding-top: 2px; }}
.cca-staff-insight-copy {{ flex: 1; min-width: 0; }}
.cca-staff-insight-copy strong {{ color: #FFFFFF; font-size: 0.8rem; }}
.cca-staff-insight-copy p {{
  margin: 3px 0;
  color: #C0D4F0;
  font-size: 0.74rem;
}}
.cca-staff-insight-copy small {{ color: #A9BCD8; font-size: 0.68rem; }}
.cca-staff-insight-meta {{
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
  color: #FFC107;
  font-size: 0.65rem;
  white-space: nowrap;
}}
.cca-staff-insight-meta b {{ color: #A9BCD8; font-weight: 500; }}
.cca-staff-action-icon {{ display: flex; justify-content: center; padding: 10px 0 4px; }}
.st-key-staff-quick-actions [data-testid="stHorizontalBlock"] > div {{
  min-width: 0;
}}
.st-key-staff-quick-actions button {{
  min-height: 52px;
  border: 1px solid rgba(0,168,255,0.55);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(8,49,101,0.94), rgba(3,20,47,0.94));
  color: #FFFFFF;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}}
.st-key-staff-quick-actions button:hover {{
  transform: translateY(-2px);
  border-color: #00DFFF;
  box-shadow: 0 8px 24px rgba(0,168,255,0.22);
}}
@media (max-width: 1100px) {{
  .st-key-staff-kpi-row [data-testid="stHorizontalBlock"] {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }}
}}
@media (max-width: 640px) {{
  .cca-staff-hero {{ padding: 18px; }}
  .cca-staff-hero p {{ font-size: 0.82rem; }}
  .st-key-staff-kpi-row [data-testid="stHorizontalBlock"] {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
  .cca-staff-insight {{ flex-wrap: wrap; }}
  .cca-staff-insight-meta {{ width: 100%; flex-direction: row; justify-content: space-between; }}
}}
"""


STYLE = _build_style(DARK_TOKENS, _RADIAL_DARK)
STYLE_LIGHT = _build_style(LIGHT_TOKENS, _RADIAL_LIGHT)


def inject(theme: str = "dark") -> None:
    """Apply the design system to the current page.

    theme is "dark" (default) or "light"; anything else falls back to dark.
    """
    css = STYLE_LIGHT if theme == "light" else STYLE
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def icon(name: str, size: int = 18, colour: str = "currentColor") -> str:
    """Inline Lucide icon markup (stroke SVG, no icon font, no emoji).

    Only the handful of glyphs this app needs are inlined, so there is no
    external icon dependency to fail at runtime.
    """
    paths = {
        "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
        "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
        "bot": '<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/>',
        "mic": '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>',
        "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
        "megaphone": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
        "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        "chart": '<line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>',
        "sparkles": '<path d="m12 3-1.9 5.8L4 10.7l6.1 1.9L12 18.4l1.9-5.8L20 10.7l-6.1-1.9z"/>',
        "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
        "bell": '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
        "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
        "send": '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
        "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
        "waveform": '<path d="M2 12h2l2-6 3 14 3-10 3 6 2-4h3"/>',
        "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
        "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
        "check": '<polyline points="20 6 9 17 4 12"/>',
        "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
        "login": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>',
        "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/>',
        "cap": '<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5"/>',
        "id-card": '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8" cy="11" r="2"/><path d="M5 17c0-1.7 1.3-3 3-3s3 1.3 3 3"/><line x1="14" y1="10" x2="19" y2="10"/><line x1="14" y1="14" x2="19" y2="14"/>',
        "lock": '<rect x="3" y="11" width="18" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        "arrow-left": '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
        "sliders": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
        "brain": '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-5.04z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-5.04z"/>',
        "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
        "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
        "school": '<path d="m4 6 8-4 8 4"/><path d="m18 10 4 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8l4-2"/><path d="M14 22v-4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v4"/><path d="M18 5v17"/><path d="M6 5v17"/><circle cx="12" cy="9" r="2"/>',
        "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>',
        "book": '<path d="M12 7v14"/><path d="M3 18V5a2 2 0 0 1 2-2h3a4 4 0 0 1 4 4 4 4 0 0 1 4-4h3a2 2 0 0 1 2 2v13"/><path d="M3 18a3 3 0 0 1 3-3h3a3 3 0 0 1 3 3 3 3 0 0 1 3-3h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-4a3 3 0 0 0-3 2 3 3 0 0 0-3-2H5a2 2 0 0 1-2-2z"/>',
        "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
        "rotate-ccw": '<path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
        "server": '<rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>',
        "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
        "chevron-right": '<polyline points="9 18 15 12 9 6"/>',
        "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
        "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
        "accessibility": '<circle cx="16" cy="4" r="1"/><path d="m18 19 1-7-6 1"/><path d="m5 8 3-3 5.5 3-2.36 3.5"/><path d="M4.24 14.5a5 5 0 0 0 6.88 6"/><path d="M13.76 17.5a5 5 0 0 0-6.88-6"/>',
    }
    body = paths.get(name, paths["sparkles"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{colour}" stroke-width="1.9" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>'
    )
