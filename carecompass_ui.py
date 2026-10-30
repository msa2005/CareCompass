"""Presentation helpers for the CareCompass Streamlit interface."""
from html import escape

import streamlit as st


PALETTE = {
    "ground": "#F4F8F5",
    "ivory": "#F4F8F5",
    "surface": "#FFFFFF",
    "surface_soft": "#EAF2EC",
    "border": "#D7E4DA",
    "ink": "#24352B",
    "muted": "#52645A",
    "sage": "#4E7660",
    "sage_dk": "#365B48",
    "amber": "#755515",
    "coral": "#7A2D30",
    "blue": "#365F82",
    "green": "#325D48",
}

_ICONS = {
    "compass": '<circle cx="12" cy="12" r="9"/><path d="m15.8 8.2-2.2 5.4-5.4 2.2 2.2-5.4 5.4-2.2Z"/><circle cx="12" cy="12" r=".7"/>',
    "home": '<path d="m3.5 10 8.5-7 8.5 7v9.5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1V10Z"/><path d="M9 20.5v-6h6v6"/>',
    "assessment": '<path d="M7 3.5h7l4 4v13a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2v-14a2 2 0 0 1 2-2Z"/><path d="M14 3.5v5h5M8.5 12h7M8.5 15.5h7M8.5 19h4"/>',
    "checkin": '<path d="M12 20s-7.5-4.3-7.5-10a4.2 4.2 0 0 1 7.5-2.6A4.2 4.2 0 0 1 19.5 10c0 5.7-7.5 10-7.5 10Z"/><path d="M8.5 12h2l1.1-2.2 1.4 4.4 1.1-2.2h1.4"/>',
    "plan": '<path d="M5 4.5h14M5 9h14M5 13.5h8M5 18h6"/><circle cx="17" cy="16.5" r="3.5"/><path d="m15.5 16.5 1 1 2-2"/>',
    "history": '<path d="M4 7v5h5"/><path d="M5.1 11a7.5 7.5 0 1 1 .2 3.5M12 7v5l3.5 2"/>',
    "chat": '<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.5-3A7.5 7.5 0 1 1 20 11.5Z"/><path d="M8.5 11.5h.01M12.5 11.5h.01M16.5 11.5h.01"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1a1.8 1.8 0 1 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3 .9v.1a1.8 1.8 0 1 1-3.6 0v-.1a1.8 1.8 0 0 0-3-.9l-.1.1a1.8 1.8 0 1 1-2.5-2.5l.1-.1a1.8 1.8 0 0 0-.9-3h-.1a1.8 1.8 0 1 1 0-3.6h.1a1.8 1.8 0 0 0 .9-3l-.1-.1a1.8 1.8 0 1 1 2.5-2.5l.1.1a1.8 1.8 0 0 0 3-.9v-.1a1.8 1.8 0 1 1 3.6 0v.1a1.8 1.8 0 0 0 3 .9l.1-.1a1.8 1.8 0 1 1 2.5 2.5l-.1.1a1.8 1.8 0 0 0 .9 3h.1a1.8 1.8 0 1 1 0 3.6h-.1a1.8 1.8 0 0 0-.9 3Z"/>',
    "support": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4.5 1.5c-.8 1-2 1.3-2 2.8M12 16.7v.1"/>',
    "back": '<path d="m14.5 5-7 7 7 7"/>',
    "arrow": '<path d="M4 12h15M13 5l7 7-7 7"/>',
}


def icon(name, size=18, extra_class=""):
    """Return a small, accessible outline icon from the CareCompass icon set."""
    paths = _ICONS.get(name, _ICONS["compass"])
    cls = f' class="{escape(extra_class, quote=True)}"' if extra_class else ""
    return (
        f'<svg{cls} aria-hidden="true" focusable="false" width="{int(size)}" '
        f'height="{int(size)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    )


def inject_theme():
    """Inject the shared light theme, responsive layout, states, and route motion."""
    route_names = (
        "welcome", "auth", "consent", "home", "assess", "context", "results",
        "plan", "history", "followup", "chat", "settings",
    )
    route_rules = "\n".join(
        f'body:has(.cc-route-marker[data-page="{name}"]) '
        f'[data-testid="stMainBlockContainer"] {{ animation-name: cc-enter-{name}; }}\n'
        f'@keyframes cc-enter-{name} {{ from {{ opacity: 0; transform: translateY(7px); }} '
        f'to {{ opacity: 1; transform: translateY(0); }} }}'
        for name in route_names
    )
    st.markdown(
        f"""
        <style>
        :root {{
          color-scheme: light;
          --cc-ground: {PALETTE['ground']};
          --cc-surface: {PALETTE['surface']};
          --cc-surface-soft: {PALETTE['surface_soft']};
          --cc-border: {PALETTE['border']};
          --cc-ink: {PALETTE['ink']};
          --cc-muted: {PALETTE['muted']};
          --cc-accent: {PALETTE['sage']};
          --cc-accent-dark: {PALETTE['sage_dk']};
          --cc-positive: {PALETTE['green']};
          --cc-warning: {PALETTE['amber']};
          --cc-negative: {PALETTE['coral']};
          --cc-info: {PALETTE['blue']};
          --cc-radius: 18px;
          --cc-radius-control: 12px;
        }}

        html, body, [data-testid="stAppViewContainer"], .stApp {{
          background: var(--cc-ground);
          color: var(--cc-ink);
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-feature-settings: "kern", "liga";
        }}
        [data-testid="stAppViewContainer"] {{ background: var(--cc-ground); }}
        [data-testid="stMain"] {{ background: var(--cc-ground); }}
        [data-testid="stMainBlockContainer"], .block-container {{
          width: 100%; max-width: 1180px; margin-inline: auto;
          padding: 2.25rem 2.25rem 4.5rem !important;
        }}
        header[data-testid="stHeader"] {{ background: transparent; }}
        footer {{ visibility: hidden; }}

        h1, h2, h3, h4, p, li, label {{ color: var(--cc-ink); }}
        h1 {{ font-size: 1.75rem !important; line-height: 1.22 !important; font-weight: 620 !important;
              letter-spacing: -0.025em !important; margin: 0 0 .35rem !important; }}
        h2 {{ font-size: 1.25rem !important; line-height: 1.35 !important; font-weight: 600 !important;
              letter-spacing: -0.015em !important; margin: 1.2rem 0 .45rem !important; }}
        h3 {{ font-size: 1.02rem !important; line-height: 1.4 !important; font-weight: 600 !important; }}
        p, li {{ line-height: 1.62; }}
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
          color: var(--cc-muted) !important; font-size: .86rem !important; line-height: 1.55;
        }}
        [data-testid="stMarkdownContainer"] a {{ color: var(--cc-accent-dark); text-underline-offset: 3px; }}
        ::selection {{ background: #D5E8DA; color: var(--cc-ink); }}

        [data-testid="stSidebar"] {{ background: var(--cc-ground); border-right: 1px solid var(--cc-border); }}
        [data-testid="stSidebar"] > div:first-child {{ padding: 1.05rem .75rem 1.5rem; }}
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: .42rem; }}
        [data-testid="stSidebar"] .stButton > button {{
          min-height: 42px; justify-content: flex-start; text-align: left;
          padding-inline: .8rem; border: 1px solid transparent; background: transparent;
          color: var(--cc-muted); font-size: .9rem; font-weight: 500;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
          background: #EDF4EF; color: var(--cc-ink); border-color: transparent;
        }}
        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
          background: #E5EFE8; color: #294B38; border-color: transparent; font-weight: 600;
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
          color: var(--cc-muted); font-size: .79rem; line-height: 1.45;
        }}
        [data-testid="stSidebar"] hr {{ margin: .85rem .5rem; border-color: var(--cc-border); }}

        .cc-brand {{ display:flex; align-items:center; gap:.72rem; padding:.35rem .5rem 1rem; margin-bottom:.55rem;
                    border-bottom:1px solid var(--cc-border); }}
        .cc-brand-mark {{ display:grid; place-items:center; width:38px; height:38px; flex:0 0 38px;
                         border-radius:13px; color:#365B48; background:#E4EEE7; }}
        .cc-brand-name {{ color:var(--cc-ink); font-size:1rem; font-weight:650; letter-spacing:-.02em; }}
        .cc-brand-user {{ color:var(--cc-muted); font-size:.77rem; margin-top:2px; max-width:162px;
                         overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
        .cc-section-heading {{ display:flex; align-items:center; gap:.55rem; margin:1.35rem 0 .25rem;
                              color:var(--cc-muted); font-size:.83rem; font-weight:600; }}
        .cc-section-heading svg {{ color:var(--cc-accent-dark); flex:none; }}
        .cc-page-heading {{ display:flex; align-items:flex-start; gap:.75rem; margin:0 0 1.25rem; }}
        .cc-page-heading svg {{ color:var(--cc-accent-dark); margin-top:.3rem; flex:none; }}
        .cc-page-heading p {{ color:var(--cc-muted); margin:.28rem 0 0; max-width:68ch; font-size:.94rem; }}
        .cc-route-marker {{ position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
          background: var(--cc-surface); border:1px solid var(--cc-border) !important;
          border-radius:var(--cc-radius) !important; box-shadow:none !important;
        }}
        [data-testid="stVerticalBlockBorderWrapper"] > div {{ border-radius:inherit; }}
        [data-testid="stMetric"] {{ background:var(--cc-surface); border:1px solid var(--cc-border);
                                    border-radius:14px; padding:1rem 1.05rem; }}
        [data-testid="stMetricLabel"] p {{ color:var(--cc-muted) !important; font-size:.84rem !important; }}
        [data-testid="stMetricValue"] {{ color:var(--cc-ink); font-weight:550; font-variant-numeric:tabular-nums; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius:14px; overflow:hidden; }}
        [data-testid="stDataFrame"] {{ border:1px solid var(--cc-border); }}
        [data-testid="stExpander"] {{ background:var(--cc-surface); border:1px solid var(--cc-border);
                                      border-radius:14px; overflow:hidden; }}
        [data-testid="stExpander"] summary {{ min-height:48px; padding-inline:1rem; color:var(--cc-ink); }}
        [data-testid="stChatMessage"] {{ background:var(--cc-surface); border:1px solid var(--cc-border);
                                        border-radius:16px; padding:1rem 1.1rem; }}

        .stButton > button, [data-testid="stFormSubmitButton"] > button,
        [data-testid="stDownloadButton"] > button {{
          min-height:44px; border-radius:var(--cc-radius-control); border:1px solid var(--cc-border);
          background:var(--cc-surface); color:var(--cc-ink); font-weight:560;
          transition:transform 180ms ease, background-color 180ms ease, border-color 180ms ease, color 180ms ease;
        }}
        .stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover,
        [data-testid="stDownloadButton"] > button:hover {{
          border-color:#AFC6B5; background:#F7FAF8; color:var(--cc-accent-dark); transform:translateY(-1px);
        }}
        .stButton > button:active, [data-testid="stFormSubmitButton"] > button:active {{ transform:translateY(0); }}
        .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {{
          background:var(--cc-accent); border-color:var(--cc-accent); color:#fff;
        }}
        button[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] {{
          background:var(--cc-accent) !important; border-color:var(--cc-accent) !important; color:#fff !important;
        }}
        button[data-testid="stBaseButton-primary"] *, [data-testid="stBaseButton-primary"] * {{ color:inherit !important; }}
        .stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
          background:var(--cc-accent-dark); border-color:var(--cc-accent-dark); color:#fff;
        }}
        button[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
          background:var(--cc-accent-dark) !important; border-color:var(--cc-accent-dark) !important; color:#fff !important;
        }}
        button:focus-visible, input:focus-visible, textarea:focus-visible, [role="radio"]:focus-visible,
        [role="checkbox"]:focus-visible {{ outline:3px solid #89AA94 !important; outline-offset:2px !important; }}

        input, textarea, [data-baseweb="select"] > div {{
          border-radius:var(--cc-radius-control) !important; border-color:#C8D8CD !important;
        }}
        textarea {{ border-radius:14px !important; }}
        [data-baseweb="slider"] [role="slider"] {{ background:var(--cc-accent); border-color:var(--cc-accent); }}
        [data-baseweb="slider"] [data-testid="stTickBar"] {{ background:var(--cc-border); }}
        div[role="radiogroup"] {{ gap:.6rem; }}
        div[role="radiogroup"] label {{ border-radius:13px; }}
        [data-testid="stAlert"] {{ border-radius:14px; padding:.9rem 1rem; }}
        [data-testid="stAlert"] p {{ line-height:1.55; }}
        hr {{ border-color:var(--cc-border); opacity:.75; }}
        .cc-status {{ display:inline-flex; align-items:center; min-height:26px; padding:3px 10px;
                     border-radius:999px; font-size:.77rem; line-height:1.35; font-weight:600; }}
        .cc-status-urgent {{ color:#7A2D30; background:#F9E9E8; }}
        .cc-status-high {{ color:#755515; background:#F6F0DF; }}
        .cc-status-moderate {{ color:#365F82; background:#EAF2F6; }}
        .cc-status-low {{ color:#325D48; background:#E9F3EB; }}
        .cc-status-caption {{ margin-left:.55rem; color:var(--cc-muted); font-size:.85rem; }}
        .cc-empty {{ display:grid; grid-template-columns:auto 1fr; align-items:start; gap:.9rem;
                    padding:1.35rem 1.4rem; background:#EDF4EF; border-radius:16px; }}
        .cc-empty-icon {{ color:var(--cc-accent-dark); margin-top:.15rem; }}
        .cc-empty h3 {{ margin:0 0 .3rem; font-size:1rem; }}
        .cc-empty p {{ margin:0; color:var(--cc-muted); line-height:1.55; }}
        .cc-progress {{ margin:.25rem 0 1.3rem; }}
        .cc-progress-top {{ display:flex; align-items:center; justify-content:space-between; gap:1rem;
                           color:var(--cc-muted); font-size:.85rem; margin-bottom:.55rem; }}
        .cc-progress-track {{ display:grid; grid-template-columns:repeat(21,minmax(0,1fr)); gap:4px; }}
        .cc-progress-step {{ height:5px; border-radius:99px; background:#DCE7DF; }}
        .cc-progress-step.done {{ background:#8EAA97; }}
        .cc-progress-step.current {{ background:var(--cc-accent); }}
        .cc-recommendation {{ padding:1.05rem 1.15rem; margin:.55rem 0 1rem; border-radius:16px;
                             background:#EDF4EF; }}
        .cc-recommendation-label {{ color:var(--cc-accent-dark); font-size:.8rem; font-weight:600; margin-bottom:.4rem; }}
        .cc-recommendation-title {{ color:var(--cc-ink); font-size:1rem; font-weight:620; margin-bottom:.3rem; }}
        .cc-recommendation-copy {{ color:var(--cc-muted); line-height:1.58; }}
        .cc-nav-item {{ display:flex; align-items:center; gap:.65rem; min-height:48px; color:var(--cc-ink); }}
        .cc-nav-item svg {{ color:var(--cc-accent-dark); flex:none; }}

        @media (prefers-reduced-motion: no-preference) {{
          [data-testid="stMainBlockContainer"] {{ animation-duration:220ms; animation-timing-function:cubic-bezier(.2,.72,.2,1); animation-fill-mode:both; }}
          {route_rules}
          .stButton > button:hover {{ transition-duration:180ms; }}
        }}
        @media (max-width: 900px) {{
          [data-testid="stMainBlockContainer"], .block-container {{ padding:1.65rem 1.4rem 3.5rem !important; }}
        }}
        @media (max-width: 640px) {{
          [data-testid="stMainBlockContainer"], .block-container {{ padding:1.25rem 1rem 2.75rem !important; }}
          h1 {{ font-size:1.48rem !important; }}
          h2 {{ font-size:1.12rem !important; }}
          div[data-testid="stHorizontalBlock"] {{ gap:.7rem !important; }}
          div[data-testid="stHorizontalBlock"] {{ flex-direction:column !important; }}
          div[data-testid="column"] {{ width:100% !important; flex:1 1 100% !important; min-width:100% !important; }}
          [data-testid="stMetric"] {{ padding:.85rem; }}
          .cc-progress-track {{ gap:2px; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{ animation-duration:.01ms !important; transition-duration:.01ms !important; scroll-behavior:auto !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def level_from_result(result_or_bands, safety_level=None):
    """Map a screening result to the existing non-diagnostic presentation level."""
    try:
        if safety_level == "urgent":
            return "urgent"
        if safety_level == "elevated":
            return "high"
        bands = (
            result_or_bands.get("bands")
            if isinstance(result_or_bands, dict) and "bands" in result_or_bands
            else result_or_bands
        ) or {}
        values = list(bands.values()) if isinstance(bands, dict) else []
        if any(value == "Extremely Severe" for value in values):
            return "urgent"
        if any(value == "Severe" for value in values):
            return "high"
        if any(value == "Moderate" for value in values):
            return "moderate"
        return "low"
    except Exception:
        return "low"


def page_header(title, subtitle=None, icon_name=None):
    """One clear app-level title and optional explanatory line."""
    mark = f'<span>{icon(icon_name, 21)}</span>' if icon_name else ""
    sub = f'<p>{escape(str(subtitle))}</p>' if subtitle else ""
    st.markdown(
        f'<div class="cc-page-heading">{mark}<div><h1>{escape(str(title))}</h1>{sub}</div></div>',
        unsafe_allow_html=True,
    )


def section_header(icon_name, title, subtitle=None):
    """A quiet, consistent section title with a small outline mark."""
    sub = f'<p>{escape(str(subtitle))}</p>' if subtitle else ""
    st.markdown(
        f'<div class="cc-section-heading">{icon(icon_name, 17)}<span>{escape(str(title))}</span></div>{sub}',
        unsafe_allow_html=True,
    )


def empty_state(icon_name, title, body):
    """A useful first-run or empty-history state that preserves the page frame."""
    st.markdown(
        f'<div class="cc-empty"><div class="cc-empty-icon">{icon(icon_name, 22)}</div>'
        f'<div><h3>{escape(str(title))}</h3><p>{escape(str(body))}</p></div></div>',
        unsafe_allow_html=True,
    )


def progress_header(i, total):
    """Show the assessment position as a calm sequence of real question steps."""
    total = max(int(total), 1)
    current = max(0, min(int(i), total - 1))
    steps = "".join(
        f'<span class="cc-progress-step {"done" if n < current else "current" if n == current else ""}"></span>'
        for n in range(total)
    )
    st.markdown(
        f'<div class="cc-progress"><div class="cc-progress-top"><span>Weekly assessment</span>'
        f'<span>Question {current + 1} of {total}</span></div><div class="cc-progress-track">{steps}</div></div>',
        unsafe_allow_html=True,
    )


def accent_caption(text, colour=None):
    """Emphasize a short instruction without a decorative alert bar."""
    st.markdown(f'**{escape(str(text))}**')


def home_hero(name, tagline):
    """Personal-home greeting kept at app scale rather than landing-page scale."""
    safe_name = escape(str(name or "there"))
    st.markdown(
        f'<div class="cc-page-heading"><div><h1>Good to see you, {safe_name}</h1>'
        f'<p>{escape(str(tagline or "A quiet place to check in and notice how things have been."))}</p></div></div>',
        unsafe_allow_html=True,
    )


def nav_card(col, icon_name, title, subtitle, button_label, key, primary=False, on_click=None):
    """A restrained destination panel with a line icon inline with its title."""
    with col.container(border=True):
        st.markdown(
            f'<div class="cc-nav-item">{icon(icon_name, 19)}<strong>{escape(str(title))}</strong></div>',
            unsafe_allow_html=True,
        )
        st.caption(subtitle)
        if st.button(
            button_label,
            key=key,
            type="primary" if primary else "secondary",
            use_container_width=True,
        ) and on_click:
            on_click()


def recommendation_card(title, text, caption="A good place to begin"):
    """Highlight one real suggestion without changing its wording or priority."""
    st.markdown(
        f'<div class="cc-recommendation"><div class="cc-recommendation-label">{escape(str(caption))}</div>'
        f'<div class="cc-recommendation-title">{escape(str(title))}</div>'
        f'<div class="cc-recommendation-copy">{escape(str(text))}</div></div>',
        unsafe_allow_html=True,
    )


def status_badge(level, caption=None):
    """Show the existing screening/safety band with a pale, readable status pair."""
    labels = {
        "urgent": "Urgent support suggested",
        "high": "Heavier than usual",
        "moderate": "Some strain showing",
        "low": "Steady",
    }
    cls = level if level in labels else "low"
    tail = f'<span class="cc-status-caption">{escape(str(caption))}</span>' if caption else ""
    st.markdown(
        f'<div style="margin:.3rem 0 1rem"><span class="cc-status cc-status-{cls}">'
        f'{labels[cls]}</span>{tail}</div>',
        unsafe_allow_html=True,
    )


def sidebar_brand(name):
    """Product mark and signed-in identity at the top of the labelled sidebar."""
    st.sidebar.markdown(
        f'<div class="cc-brand"><div class="cc-brand-mark">{icon("compass", 23)}</div>'
        f'<div><div class="cc-brand-name">CareCompass</div>'
        f'<div class="cc-brand-user">{escape(str(name or "Your wellbeing space"))}</div></div></div>',
        unsafe_allow_html=True,
    )
