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
    # canvas and surfaces
    "--bg": "#070B1F",
    "--bg-2": "#0B1230",
    "--sidebar-bg": "linear-gradient(180deg, rgba(13,19,45,0.94), rgba(9,13,34,0.94))",
    "--input-bg": "rgba(13,19,45,0.85)",
    "--table-head-bg": "rgba(22,30,66,0.75)",
    "--table-row-bg": "rgba(13,19,45,0.6)",
    "--overlay": "linear-gradient(180deg, transparent 0%, rgba(7,11,31,0.55) 100%)",
    "--surface": "rgba(22, 30, 66, 0.62)",
    "--surface-solid": "#141C3D",
    "--surface-hover": "rgba(32, 42, 88, 0.72)",
    # accents
    "--primary": "#2F6BFF",
    "--primary-2": "#6D4AFF",
    "--violet": "#8B5CF6",
    "--accent": "#22D3EE",
    # text
    "--fg": "#EDF1FF",
    "--fg-muted": "#A3B0D4",
    "--fg-dim": "#7C89B0",
    # lines and states
    "--border": "rgba(122, 146, 214, 0.22)",
    "--border-strong": "rgba(122, 146, 214, 0.38)",
    "--success": "#34D399",
    "--warning": "#FBBF24",
    "--danger": "#F87171",
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

_RADIAL_DARK = (
    "radial-gradient(1100px 620px at 12% -8%, rgba(47,107,255,0.20), transparent 62%),"
    "radial-gradient(900px 560px at 92% 4%, rgba(109,74,255,0.18), transparent 60%),"
    "radial-gradient(760px 520px at 50% 108%, rgba(34,211,238,0.08), transparent 60%)"
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
.stApp {{
  background: {radial}, var(--bg);
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

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  backdrop-filter: blur(14px);
}}
[data-testid="stSidebar"] * {{ color: var(--fg); }}
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
  box-shadow: 0 8px 22px -10px rgba(47,107,255,0.9);
  flex: 0 0 auto;
}}
.cca-brand-name {{
  font-size: 1rem; font-weight: 700; letter-spacing: 0.06em;
  line-height: 1.15; color: var(--fg);
}}
.cca-brand-sub {{ font-size: 0.72rem; color: var(--fg-muted); letter-spacing: 0.02em; }}

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
  background: linear-gradient(135deg, rgba(47,107,255,0.30), rgba(109,74,255,0.26));
  border-color: rgba(122,146,214,0.42);
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
.cca-badge--good {{ background: rgba(52,211,153,0.14); color: #6EE7B7; border-color: rgba(52,211,153,0.32); }}
.cca-badge--warn {{ background: rgba(251,191,36,0.14); color: #FCD34D; border-color: rgba(251,191,36,0.32); }}
.cca-badge--info {{ background: rgba(47,107,255,0.16); color: #A5BEFF; border-color: rgba(47,107,255,0.34); }}
.cca-badge--danger {{ background: rgba(248,113,113,0.14); color: #FCA5A5; border-color: rgba(248,113,113,0.32); }}

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
  color: #FFFFFF;
  box-shadow: 0 12px 28px -14px rgba(47,107,255,0.95);
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
  box-shadow: 0 0 0 3px rgba(47,107,255,0.22) !important;
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
[data-testid="stChatInput"] button:hover {{ background-color: rgba(47,107,255,0.18) !important; }}

/* Segmented control (role switch) */
[data-testid="stSegmentedControl"] button,
[data-baseweb="button-group"] button {{
  background: var(--input-bg) !important;
  color: var(--fg-muted) !important;
  border-color: var(--border) !important;
}}
[data-testid="stSegmentedControl"] button[aria-checked="true"],
[data-baseweb="button-group"] button[aria-pressed="true"] {{
  background: linear-gradient(135deg, var(--primary), var(--primary-2)) !important;
  color: #FFFFFF !important;
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
  background: linear-gradient(135deg, rgba(47,107,255,0.9), rgba(109,74,255,0.85)) !important;
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
  background: rgba(47,107,255,0.18) !important;
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
  background: rgba(47,107,255,0.22) !important;
}}
/* keyboard shortcuts shown on the right of a menu row */
div[role="menuitem"] kbd,
div[data-testid="stMainMenu"] kbd,
div[role="menu"] kbd {{
  color: var(--fg-dim) !important;
  background: rgba(122,146,214,0.16) !important;
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
  background: rgba(47,107,255,0.22) !important;
}}
div[role="option"][aria-selected="true"] {{
  background: rgba(47,107,255,0.34) !important;
  color: #FFFFFF !important;
}}

/* tooltips and popovers */
div[data-baseweb="tooltip"],
div[data-baseweb="popover"] {{
  background: var(--surface-solid) !important;
  color: var(--fg) !important;
  border-radius: var(--radius-sm) !important;
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
  border-bottom: 1px solid rgba(122,146,214,0.10);
  vertical-align: top;
}}
table.cca-table tbody tr:last-child td {{ border-bottom: none; }}
table.cca-table tbody tr:hover td {{ background: rgba(47,107,255,0.08); }}
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
  background: rgba(47,107,255,0.22) !important;
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
  background: linear-gradient(140deg, rgba(47,107,255,0.75), rgba(139,92,246,0.55), transparent 70%);
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
  box-shadow: 0 0 0 4px rgba(47,107,255,0.14), 0 14px 30px -16px rgba(109,74,255,0.9);
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
  color: #A5BEFF; margin: 0 0 8px 0;
}}
.cca-dev-bio {{ font-size: 0.82rem; color: var(--fg-muted); line-height: 1.5; margin: 0; }}

/* ---------- hero ---------- */
.cca-hero {{
  background: linear-gradient(135deg, rgba(47,107,255,0.20), rgba(109,74,255,0.14) 55%, rgba(34,211,238,0.10));
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 26px 28px;
  margin-bottom: 18px;
  backdrop-filter: blur(16px);
}}
.cca-hero h1 {{ font-size: 1.6rem; margin: 0 0 6px 0; }}
.cca-hero p {{ margin: 0; color: var(--fg-muted); font-size: 0.92rem; max-width: 62ch; }}

/* ---------- responsive ---------- */
@media (max-width: 768px) {{
  .cca-hero {{ padding: 20px 18px; }}
  .cca-hero h1 {{ font-size: 1.3rem; }}
  .cca-kpi-value {{ font-size: 1.5rem; }}
  [data-baseweb="tab"] {{ padding: 6px 12px !important; font-size: 0.85rem !important; }}

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

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }}
  .cca-dev-card:hover {{ transform: none; }}
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
    }
    body = paths.get(name, paths["sparkles"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{colour}" stroke-width="1.9" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>'
    )
