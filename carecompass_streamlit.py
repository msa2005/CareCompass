"""CareCompass - Streamlit interface. Run: streamlit run carecompass_streamlit.py
Credentials can be placed in the project-root .env file. Supabase uses the anon/publishable key only.
All decisions (scoring, safety, recommendations) live in carecompass_core.py."""
import os
from pathlib import Path


def load_local_env():
    """Load simple KEY=VALUE settings from the project .env without overriding the shell."""
    env_file = Path(__file__).with_name(".env")
    try:
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, value = entry.partition("=")
        key = key.strip()
        if not separator or not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(char.isalnum() or char == "_" for char in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_local_env()

import pandas as pd
import streamlit as st
import carecompass_core as cc
import carecompass_patterns as cpat
import carecompass_ui as ui

st.set_page_config(page_title="CareCompass", page_icon=":material/explore:", layout="wide", initial_sidebar_state="auto")
DEBUG = os.environ.get("CARECOMPASS_DEBUG", "1") != "0"

ui.inject_theme()

@st.cache_resource
def get_models():
    return cc.init_models()
get_models()

# ---------------------------------------------------------------- state
if "S" not in st.session_state:
    st.session_state.S = cc.fresh()
    st.session_state.screen = "welcome"
    st.session_state.flash = None
S = st.session_state.S

def goto(name, flash=None):
    if name != "home":
        st.session_state["notif_visible"] = False
    st.session_state.screen = name
    st.session_state.flash = flash
    st.rerun()

def guarded(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cc.Expired:
        goto("auth", ("warning", "Your session expired. Please log in again."))

def flash_show():
    f = st.session_state.get("flash")
    if f:
        getattr(st, f[0])(f[1])
        st.session_state.flash = None

# ---------------------------------------------------------------- v4: login voice-notification helpers
def load_wellbeing_summary():
    return cc.fetch_wellbeing_summary(S)

def _render_notification_card(voice_text, level, reasons, autoplay=True,
                             speech_text=None, play_label="Play voice summary"):
    """Warm card that speaks a short summary via the browser's built-in TTS. No audio leaves the device."""
    import json as _json
    safe_text = _json.dumps(speech_text or voice_text)
    from html import escape as _escape
    palette = {
        "urgent":  ("#F9E9E8", "#7A2D30", "Reach out for support today"),
        "high":    ("#F6F0DF", "#755515", "Heavier than usual"),
        "moderate":("#EAF2F6", "#365F82", "Some strain showing"),
        "low":     ("#E9F3EB", "#325D48", "Steady"),
    }
    bg, bd, label = palette.get(level, palette["low"])
    safe_id = bd.strip("#")
    safe_voice = _escape(str(voice_text))
    reasons_html = "".join(f"<li>{_escape(str(r))}</li>" for r in (reasons or [])[:3])
    autoplay_js  = "setTimeout(speak, 400);" if autoplay else ""
    html = f"""
    <div style="background:{bg};padding:18px 20px;border-radius:16px;
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#24352B;">
      <div style="font-size:14px;color:{bd};font-weight:650;">{_escape(label)}</div>
      <p style="margin:10px 0;font-size:15px;color:#24352B;line-height:1.55;">{safe_voice}</p>
      {('<ul style="margin:0 0 14px 18px;padding:0;color:#52645A;font-size:14px;line-height:1.55;">'
        + reasons_html + '</ul>') if reasons_html else ''}
      <button id="vc-play-{safe_id}" aria-label="{_escape(play_label)}" style="background:{bd};color:#fff;border:none;padding:10px 16px;
              border-radius:999px;cursor:pointer;font-size:14px;font-weight:600;">{_escape(play_label)}</button>
      <button id="vc-stop-{safe_id}" aria-label="Stop voice summary" style="background:transparent;color:{bd};border:1px solid {bd};
              padding:10px 16px;border-radius:999px;cursor:pointer;font-size:14px;margin-left:8px;">Stop</button>
    </div>
    <script>
    (function(){{
      const text = {safe_text};
      function speak() {{
        try {{
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(text);
          u.rate = 1.0; u.pitch = 1.0; u.volume = 1.0; u.lang = "en-IN";
          window.speechSynthesis.speak(u);
        }} catch (e) {{ console.error("TTS error:", e); }}
      }}
      const playBtn = document.getElementById("vc-play-{safe_id}");
      const stopBtn = document.getElementById("vc-stop-{safe_id}");
      if (playBtn) playBtn.addEventListener("click", speak);
      if (stopBtn) stopBtn.addEventListener("click", function(){{ try {{ window.speechSynthesis.cancel(); }} catch(e){{}} }});
      {autoplay_js}
    }})();
    </script>
    """
    st.components.v1.html(html, height=195, scrolling=False)
    st.caption("The voice summary plays aloud. Use headphones in shared spaces. "
               "If your browser blocks autoplay, click the button to hear it.")

def show_login_notification():
    if st.session_state.get("notif_shown"):
        return
    st.session_state["notif_shown"] = True
    try:
        data = load_wellbeing_summary()
    except cc.Expired:
        return
    if not data:
        return
    a  = data.get("assessments") or []
    ci = data.get("checkins")    or []
    if not a and not ci:
        return
    try:
        pat   = cpat.mine_patterns(a, ci)
        voice = cpat.voice_preview(a, ci, pat, S.get("name"))
    except Exception:
        return
    st.session_state["notif_data"] = {
        "voice": voice, "level": pat["criticality"], "assessments": a, "checkins": ci,
        "patterns": pat, "expanded": False, "detail": None,
    }
    st.session_state["notif_visible"] = True
    st.session_state["notif_autoplay_pending"] = True


def render_notification_push(autoplay=False):
    """Show the short voice note first; reveal the fuller result only on request."""
    nd = st.session_state.get("notif_data") or {}
    if not nd.get("voice"):
        return
    support_labels = {
        "low": "Steady",
        "moderate": "Some strain",
        "high": "A lot to carry",
        "urgent": "Reach out for support today",
    }
    detail_level = nd.get("detail_level", nd.get("level", "low"))
    full_speech = nd["voice"]
    if nd.get("expanded") and nd.get("detail"):
        full_speech += f" Support signal: {support_labels.get(detail_level, 'Steady')}. {nd['detail']}"
    _render_notification_card(
        nd["voice"], nd.get("level", "low"), [], autoplay=autoplay,
        speech_text=full_speech,
        play_label="Play full voice note" if nd.get("expanded") else "Play voice summary",
    )
    st.caption("The fuller AI summary uses categories from your three latest assessments and check-ins, plus a support signal. Your name and written check-in notes are not sent to Groq.")

    if not nd.get("expanded"):
        if st.button("Continue to my detailed wellbeing summary", key="notif_continue",
                     icon=":material/arrow_forward:", type="primary", use_container_width=True):
            with st.spinner("Preparing a gentle summary…"):
                recent_assessments = (nd.get("assessments") or [])[:3]
                recent_checkins = (nd.get("checkins") or [])[:3]
                detail_patterns = cpat.mine_patterns(recent_assessments, recent_checkins)
                nd["detail"] = cpat.gentle_wellbeing_summary(
                    recent_assessments, recent_checkins, detail_patterns)
                nd["detail_level"] = detail_patterns["criticality"]
            nd["expanded"] = True
            st.rerun()

    if nd.get("expanded"):
        with st.container(border=True):
            ui.section_header("assessment", "A little more about your result")
            st.caption("Support signal · " + support_labels.get(detail_level, "Steady"))
            st.text(nd.get("detail") or "Your summary is not available right now.")
            st.caption("This screening is a reflection of recent answers, not a diagnosis.")

# ---------------------------------------------------------------- navigation
def nav_bar():
    """The labelled sidebar is the single navigation surface for signed-in screens."""
    return

def sidebar_nav():
    with st.sidebar:
        ui.sidebar_brand(S.get('name') or S.get('email') or "CareCompass")
        cur = st.session_state.get("screen")
        st.markdown('<div class="cc-section-heading">Your space</div>', unsafe_allow_html=True)
        destinations = [
            ("Home", "home", "home", "home"),
            ("Weekly assessment", "assess", "assessment", "description"),
            ("My wellbeing plan", "plan", "plan", "event_note"),
            ("Check in", "followup", "checkin", "favorite_border"),
            ("Chat companion", "chat", "chat", "chat_bubble_outline"),
            ("History", "history", "history", "history"),
            ("Profile and settings", "settings", "settings", "settings"),
        ]
        for label, target, icon_name, material_icon in destinations:
            active = cur == target or (cur in ("context", "results") and target == "assess")
            if st.button(label, key=f"sb_{target}", icon=f":material/{material_icon}:", use_container_width=True,
                         type="primary" if active else "secondary"):
                start_assessment() if target == "assess" else goto(target)
        st.markdown('<div class="cc-section-heading">Your account</div>', unsafe_allow_html=True)
        if st.button("Hear my summary", icon=":material/volume_up:", key="sb_voice", use_container_width=True):
            if not st.session_state.get("notif_shown"):
                show_login_notification()
            if st.session_state.get("notif_data"):
                st.session_state["notif_visible"] = True
                st.session_state["notif_again"] = True
                goto("home")
            else:
                st.toast("Complete an assessment first so I have something to tell you.")
        if st.button("Sign out", icon=":material/logout:", key="sb_out", use_container_width=True): sign_out()

def sign_out():
    st.session_state.S = cc.fresh()
    for k in ("chat", "ci_reply", "chat_ok", "plan_ai", "chat_err",
              "notif_shown", "notif_data", "notif_again", "notif_visible",
              "notif_autoplay_pending"):
        st.session_state.pop(k, None)
    for k in list(st.session_state.keys()):
        if k.startswith("q") and k[1:].isdigit(): del st.session_state[k]
    goto("welcome", ("info", "You have been signed out."))

def choice_label(v):
    return next(l for l, x in cc.CHOICES if x == v)

def show_rec(x):
    st.markdown(f"**{x['title']}**  \n{x['text']}" if x.get("title") else f"- {x['text']}")

def rec_label(r):
    return f"{cc.date_str(r['created_at'])} · {cc.bands_str(r['severity_bands'])}"

# ---------------------------------------------------------------- screen 01: welcome
def screen_welcome():
    intro, guide = st.columns([1.2, 0.8], gap="large")
    with intro:
        ui.page_header("A gentle space to check in", "CareCompass helps you reflect on how the past week has felt.", "compass")
        st.info(cc.LIMITS)
        c = st.columns(2)
        if c[0].button("Get started", type="primary", icon=":material/arrow_forward:", use_container_width=True): goto("auth")
        if c[1].button("Log in", icon=":material/login:", use_container_width=True): goto("auth")
        with st.expander("Privacy and limitations"):
            st.markdown(cc.PRIVACY + "\n\n" + cc.LIMITS)
    with guide.container(border=True):
        ui.section_header("assessment", "A clear path through the week")
        for icon_name, title, copy in [
            ("checkin", "Check in", "Record how today feels, in your own words."),
            ("history", "Notice patterns", "Review saved check-ins and screening results over time."),
            ("plan", "Choose a next step", "Explore general ideas and support options that fit your answers."),
        ]:
            st.markdown(
                f'<div class="cc-nav-item" style="margin-top:.85rem">{ui.icon(icon_name, 19)}'
                f'<strong>{title}</strong></div><p style="margin:.15rem 0 0 1.9rem;color:#52645A">{copy}</p>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------- screen 02: auth
def screen_auth():
    ui.page_header("Sign up or log in", "Sign in to manage your saved history and preferences.", "settings")
    if not cc.db.configured:
        st.error("Backend not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY to the project .env file, then restart the app.")
    n = st.session_state.get("auth_n", 0)
    with st.container(border=True):
        with st.form(f"auth_{n}"):
            email = st.text_input("Email", key=f"auth_email_{n}")
            pw = st.text_input("Password", type="password", key=f"auth_pw_{n}")
            login = st.form_submit_button("Log in", type="primary", use_container_width=True)
            c = st.columns(2)
            signup = c[0].form_submit_button("Create account", use_container_width=True)
            reset  = c[1].form_submit_button("Forgot password", use_container_width=True)
    if st.button("Back", icon=":material/arrow_back:"): goto("welcome")
    if not (login or signup or reset): return
    e = cc.clean_email(email)
    if reset:
        try: cc.db.reset(e)
        except Exception: pass
        st.info("If that email has an account, a reset link is on its way."); return
    if signup:
        if not e or len(pw or "") < 8:
            st.warning("Enter an email and a password of at least 8 characters."); return
        try:
            direct = cc.db.sign_up(e, pw)
            st.session_state["auth_n"] = n + 1
            st.session_state.pop("auth_email", None)
            st.session_state.pop("auth_pw", None)
            goto("auth", ("success", "Account created. " + ("Please log in with your new details." if direct else "Check your email to confirm, then log in.")))
        except Exception as ex:
            st.error(f"Could not sign up: {str(ex)[:150]}")
        return
    try:
        tok, uid, em = cc.db.sign_in(e, pw or "")
    except Exception as ex:
        st.error(f"Could not log in: {str(ex)[:150]}"); return
    S.update(cc.fresh()); S.update(token=tok, uid=uid, email=em)
    guarded(cc.load_consents, S); guarded(cc.load_profile, S); guarded(cc.log, S, "login")
    goto("home" if S["consent"].get("assessment") else "consent")

# ---------------------------------------------------------------- screen 03: consent
def screen_consent():
    ui.page_header("Before we start", "Choose how your information is used. You can change these choices later in Settings.", "support")
    st.info(cc.LIMITS)
    st.write("You will answer 21 questions. Your result levels are calculated by fixed rules, not by AI. If AI wording is "
             "available it only rephrases approved suggestions. Saved records are private to you, and you can withdraw "
             "consent any time in Settings.")
    with st.container(border=True):
        st.markdown("**Required**")
        a = st.checkbox("I agree to complete the questionnaire and have my results processed and saved as described.")
    with st.container(border=True):
        st.markdown("**Optional**")
        f = st.checkbox("I would like to be able to save voluntary follow-up check-ins.")
    c = st.columns(2)
    if c[0].button("Continue", type="primary", use_container_width=True):
        if not a:
            st.warning("Required consent is needed to continue. You can also leave without starting.")
        else:
            try:
                guarded(cc.set_consent, S, "assessment", True)
                guarded(cc.set_consent, S, "followup", bool(f))
            except Exception:
                st.error("We could not record your consent, so nothing was started. Please try again."); return
            goto("home")
    if c[1].button("Leave without starting", use_container_width=True): sign_out()

# ---------------------------------------------------------------- screen 04: home
def screen_home():
    nav_bar()
    # Keep the note mounted on reruns so its Continue button can reveal the detail.
    if not st.session_state.get("notif_shown"):
        show_login_notification()
    if st.session_state.pop("notif_again", False):
        render_notification_push(autoplay=True)
    elif st.session_state.get("notif_visible") and st.session_state.get("notif_data"):
        render_notification_push(autoplay=st.session_state.pop("notif_autoplay_pending", False))
    ui.home_hero(S.get('name') or S['email'],
                 "Check in with today, reflect on the past week, or choose a small next step.")
    st.caption(cc.LIMITS)
    with st.container(border=True):
        ui.section_header("assessment", "See how the past week has felt",
                          "A 21-question check-in, usually about five minutes. Your result is based on fixed scoring rules.")
        if st.button("Start weekly assessment", type="primary", icon=":material/arrow_forward:", key="home_start"):
            start_assessment()
    st.markdown("## Other ways to begin")
    destinations = [
        ("Check in", "How are you feeling right now?", "checkin", "followup", "home_checkin", "today"),
        ("View history", "Return to your saved check-ins and results.", "history", "history", "home_history", "history"),
        ("Open your plan", "Review general ideas tailored to your answers.", "plan", "plan", "home_plan", "event_note"),
        ("Talk things through", "Open the AI companion and its safety information.", "chat", "chat", "home_chat", "chat_bubble_outline"),
    ]
    for row_start in range(0, len(destinations), 2):
        cols = st.columns(2)
        for col, (label, description, target, icon_name, key, material_icon) in zip(cols, destinations[row_start:row_start + 2]):
            with col.container(border=True):
                st.markdown(f'<div class="cc-nav-item">{ui.icon(icon_name, 19)}<strong>{label}</strong></div>', unsafe_allow_html=True)
                st.caption(description)
                if st.button(label, key=key, icon=f":material/{material_icon}:", use_container_width=True):
                    goto(target)

def start_assessment():
    if not S["consent"].get("assessment"): goto("consent")
    S.update(resp=[None] * 21, idx=0, ctx={}, self_harm=False, result=None, aid=None)
    for i in range(21): st.session_state.pop(f"q{i}", None)
    S["catalog"] = guarded(cc.catalog_from_db, S)
    goto("assess")

# ---------------------------------------------------------------- screen 05: questionnaire
def screen_assess():
    i = S["idx"]
    ui.progress_header(i, 21)
    ui.page_header("Weekly assessment", "Think about how each statement applied to you over the past week.", "assessment")
    st.subheader(cc.ITEMS[i])
    val = st.radio("Over the past week...", [0, 1, 2, 3], index=S["resp"][i], format_func=choice_label, key=f"q{i}")
    c = st.columns(3)
    back = c[0].button("Back", icon=":material/arrow_back:", use_container_width=True, disabled=(i == 0))
    nxt = c[1].button("Next" if i < 20 else "Finish", icon=":material/arrow_forward:", type="primary", use_container_width=True)
    exit_ = c[2].button("Exit", icon=":material/close:", use_container_width=True)
    if exit_:
        goto("home", ("info", "You exited. Nothing was saved."))
    if back:
        if val is not None: S["resp"][i] = int(val)
        S["idx"] = max(0, i - 1); st.rerun()
    if nxt:
        if val is None:
            st.warning("Please choose an answer to continue."); return
        S["resp"][i] = int(val)
        if i < 20:
            S["idx"] = i + 1; st.rerun()
        finish()

def finish():
    probs = cc.validate_responses(S["resp"])
    if probs:
        S["idx"] = next(i for i, v in enumerate(S["resp"]) if v is None)
        goto("assess", ("warning", "Some answers are missing: " + " ".join(probs[:3])))
    goto("context", ("info", "Thank you. Just a few quick questions so your suggestions fit you."))

def persist_result():
    r = S["result"]
    if S["aid"]:
        try:
            guarded(cc.api, S, lambda c: c.rpc("update_assessment_context", {"p_id": S["aid"], "p_context": S["ctx"], "p_summary": r["explanation"]}).execute())
            return ("success", "Your updated suggestions were saved.")
        except Exception:
            return ("error", "Your updated suggestions were NOT saved (technical problem).")
    if not S["consent"].get("assessment"):
        return ("warning", "Not saved: you have not given assessment consent.")
    try:
        aid = guarded(lambda: cc.api(S, lambda c: c.rpc("save_assessment", {
            "p_bands": r["bands"], "p_summary": r["explanation"], "p_scoring_version": cc.SCORING_VERSION,
            "p_model_version": cc.init_models().version, "p_raw_scores": r["raw"], "p_responses": S["resp"],
            "p_context": S["ctx"], "p_model_estimates": r["ml"]}).execute()).data)
        S["aid"] = aid
        guarded(cc.log, S, "assessment_saved")
        return ("success", "Saved to your private history.")
    except Exception:
        return ("error", "This result was NOT saved because of a technical problem. Please note it down if you need it.")

# ---------------------------------------------------------------- screen 06: results
def screen_results():
    nav_bar()
    r = S.get("result")
    if not r: goto("home")
    if r["safety"]["text"]:
        (st.error if r["safety"]["level"] == "urgent" else st.warning)(r["safety"]["text"])
    ui.page_header("Your results", "Based on your answers for the past week. This screening result is not a diagnosis.", "assessment")
    ui.status_badge(ui.level_from_result(r, r["safety"]["level"]))
    cols = st.columns(3)
    for col, (sub, b) in zip(cols, r["bands"].items()): col.metric(sub, b)
    if cc.SHOW_RESEARCH_MODEL_VIEW and r["ml"]:
        st.caption("Research view (experimental): " + ", ".join(f"{k} {v['band']} ({v['confidence']})" for k, v in r["ml"].items()))
    st.write(r["explanation"])
    ind = cc.lifestyle_indicator(S["ctx"])
    ui.section_header("history", "Patterns in your context answers")
    st.caption("These reflect your sleep, energy, academic pressure, activity, screen time and social contact. They do not change your DASS-21 result.")
    for col, (area, v) in zip(st.columns(3), ind.items()):
        col.metric(f"{area} strain", v["level"])
        col.caption(", ".join(v["drivers"]).capitalize() if v["drivers"] else "No strong lifestyle strain showing")
    # UI2: highlight the top suggestion in an amber card; rest under an expander
    ui.section_header("plan", "Suggestions for you")
    if r["recs"]:
        top = r["recs"][0]
        ui.recommendation_card(top.get("title") or "First idea to try", top["text"], "A small place to start")
        if len(r["recs"]) > 1:
            with st.expander(f"More ideas ({len(r['recs']) - 1})"):
                for x in r["recs"][1:]:
                    show_rec(x)
    with st.expander("Support options", expanded=r["safety"]["level"] != "none"):
        st.markdown(cc.SUPPORT_LINES)
    kind, msg = S.get("save_status", ("info", ""))
    if msg: getattr(st, kind)(msg)
    st.caption(cc.LIMITS)
    c = st.columns(3)
    if c[0].button("Get my wellbeing plan", type="primary", icon=":material/arrow_forward:", use_container_width=True): goto("plan")
    if c[1].button("Update my answers", icon=":material/edit:", use_container_width=True): goto("context")
    if c[2].button("View history", icon=":material/history:", use_container_width=True): goto("history")

# ---------------------------------------------------------------- screen 07: context
CTX_QUESTIONS = [
    ("sleep", "How has your sleep been lately?"),
    ("energy", "How has your energy been lately?"),
    ("pressure", "How much academic pressure do you feel?"),
    ("activity", "How often do you do physical activity or exercise?"),
    ("screen", "How much time do you spend on screens each day, outside of study?"),
    ("social", "How often do you spend time with friends or family?"),
    ("support", "What kind of support would you prefer?"),
]

def screen_context():
    if cc.validate_responses(S["resp"]):
        goto("home", ("warning", "Please complete the questionnaire first."))
    ui.page_header("A little more context", "These answers help tailor your suggestions. They do not change your DASS-21 result.", "checkin")
    prev = S.get("ctx") or {}
    ix = lambda k: cc.CTX_OPTIONS[k].index(prev[k]) if prev.get(k) in cc.CTX_OPTIONS[k] else None
    with st.form("ctx"):
        st.markdown("**Rest and energy**")
        ans = {}
        for k, q in CTX_QUESTIONS[:2]:
            ans[k] = st.radio(q + " *", cc.CTX_OPTIONS[k], index=ix(k))
        st.markdown("**Daily routines**")
        for k, q in CTX_QUESTIONS[2:5]:
            ans[k] = st.radio(q + " *", cc.CTX_OPTIONS[k], index=ix(k))
        st.markdown("**Connection and support**")
        for k, q in CTX_QUESTIONS[5:]:
            ans[k] = st.radio(q + " *", cc.CTX_OPTIONS[k], index=ix(k))
        sf = st.checkbox("I have had thoughts of harming myself recently")
        ok = st.form_submit_button("See my results" if not S.get("result") else "Update my results", type="primary")
    if S.get("result"):
        if st.button("Back to results"): goto("results")
    elif st.button("Exit without saving"): goto("home", ("info", "You exited. Nothing was saved."))
    if not ok: return
    missing = [q.rstrip("?").lower() for k, q in CTX_QUESTIONS if not ans[k]]
    if missing:
        st.warning(f"Please answer every question to continue. {len(missing)} still to answer."); return
    S["ctx"] = dict(ans)
    S["self_harm"] = bool(sf)
    with st.spinner("Preparing your results..."):
        cc.build_result(S)
        r = S["result"]
        S["save_status"] = persist_result()
        if r["safety"]["level"] != "none": guarded(cc.log, S, "safety_pathway_shown")
        if not r["groq"]: guarded(cc.log, S, "groq_fallback")
    st.session_state.pop("plan_ai", None)
    goto("results")

# ---------------------------------------------------------------- my wellbeing plan
def screen_plan():
    nav_bar(); flash_show()
    ui.page_header("My wellbeing plan", "General wellbeing ideas based on your most recent assessment.", "plan")
    try: inp = guarded(cc.fetch_latest_plan_inputs, S)
    except Exception: st.error("Could not load your latest assessment. Please try again in a moment."); return
    if not inp:
        ui.empty_state("plan", "Your plan will appear here",
                       "Your plan is built from your most recent assessment. Complete one first and it will appear here.")
        if st.button("Start an assessment", type="primary", icon=":material/arrow_forward:"): start_assessment()
        return
    bands, ctx, urgent = inp["bands"], inp.get("context") or {}, bool(inp.get("urgent"))
    created = cc.date_str(inp["created_at"])
    st.caption(f"Based on your most recent assessment ({created}). General wellbeing ideas, not medical advice or a diet plan.")
    cols = st.columns(3)
    for col, (sub, b) in zip(cols, bands.items()): col.metric(sub, b)
    serious = urgent or any(b in ("Severe", "Extremely Severe") for b in bands.values())
    if serious:
        (st.error if urgent else st.warning)("You do not have to manage this alone. Please consider speaking with someone today.\n\n" + cc.SUPPORT_LINES)
    plan = cc.build_plan(bands, ctx, urgent)
    st.info(plan["focus"])
    if plan.get("basis"): st.caption("Built from your answers: " + ", ".join(plan["basis"]) + ".")
    for sec in plan["sections"]:
        if sec["start_here"]:
            ui.accent_caption("Start here")
            with st.expander(sec["title"], expanded=True):
                for it in sec["items"]:
                    st.markdown(f"**{it['title']}**" + (f"  \n*{it['why']}*" if it.get("why") else "") + f"  \n{it['text']}")
        else:
            with st.expander(sec["title"], expanded=False):
                for it in sec["items"]:
                    st.markdown(f"**{it['title']}**" + (f"  \n*{it['why']}*" if it.get("why") else "") + f"  \n{it['text']}")
    ex = plan["example"]
    import re as _re
    example_title = _re.sub(r"\bworked\s+example\b", "Practical example", ex["title"], flags=_re.IGNORECASE).strip(" :-–")
    if not example_title:
        example_title = "Practical example"
    with st.expander(example_title, expanded=plan["example_relevant"]):
        for n, (t, d) in enumerate(ex["steps"], 1):
            st.markdown(f"**{n}. {t}**")
            st.markdown(d.replace("\n", "  \n"))
    if ctx:
        with st.expander("How your daily habits may be adding strain (simple rule-based view, not a diagnosis)"):
            for area, v in cc.lifestyle_indicator(ctx).items():
                why = ", ".join(v["drivers"]) if v["drivers"] else "nothing stands out in your answers"
                st.markdown(f"- **{area}:** {v['level']} ({why})")
            st.caption("This only reflects your habit answers, not your DASS-21 result. It is a rough guide, not a measurement.")
    ui.section_header("plan", "A plan written for you")
    if urgent:
        st.info("Because of your answers, please start with the support options above. The approved plan here is a gentle place to begin, "
                "and the AI-written version is paused.")
    else:
        focus = st.selectbox("What would you like the most help with?", cc.PLAN_FOCUS, key="plan_focus")
        key = f"{inp['assessment_id']}|{focus}"
        cache = st.session_state.setdefault("plan_ai", {})
        if st.button("Write my personalised plan", type="primary", icon=":material/auto_awesome:"):
            with st.spinner("Writing your plan..."):
                text = cc.generate_ai_plan(bands, ctx, focus, plan, urgent)
            if text:
                cache[key] = text; guarded(cc.log, S, "plan_generated")
            else:
                st.warning("I could not write the personalised version just now, so the approved plan above is what to follow."
                           + (f"\n\nTechnical detail: {cc.LAST_GROQ_ERROR}" if cc.LAST_GROQ_ERROR and DEBUG else ""))
        if cache.get(key):
            st.markdown(cache[key])
            st.caption("Written by AI from the approved ideas above. For health conditions, allergies or any worry about eating, please check with a doctor or dietitian.")
    st.download_button("Download my plan (text file)", cc.plan_to_text(plan, bands, created), file_name="my_wellbeing_plan.txt", icon=":material/download:")
    st.caption(plan["note"])

# ---------------------------------------------------------------- screen 08: history
def fetch_hist():
    rows = guarded(cc.api, S, lambda c: c.table("carecompass_assessments").select("id,created_at,screening_mode,severity_bands")
                   .order("created_at", desc=True).execute()).data
    fu = guarded(cc.api, S, lambda c: c.table("carecompass_followups").select("assessment_id,created_at,mood,stress,anxiety,energy,sleep,note")
                 .order("created_at", desc=True).execute()).data
    return rows, fu

def screen_history():
    nav_bar(); flash_show()
    ui.page_header("Your history", "Your saved screening results and linked check-ins, ordered by date.", "history")
    st.caption("Result levels only. Full-questionnaire results are labelled 'full21'.")
    try: rows, fu = fetch_hist()
    except Exception: st.error("Could not load your history."); return
    if not rows:
        ui.empty_state("history", "No saved assessments yet",
                       "Once you complete an assessment, it will appear here. You can compare future result levels here over time.")
        return
    recent = rows[:3]
    pattern_rows = []
    for sub in ("Depression", "Anxiety", "Stress"):
        observed = [r.get("severity_bands", {}).get(sub) for r in recent]
        observed = [value for value in observed if value in cc.BANDS]
        if len(observed) < 2:
            pattern = "One result so far"
        else:
            ranked = [cc.BANDS.index(value) for value in observed]
            if all(a == b for a, b in zip(ranked, ranked[1:])):
                pattern = "Same category across recent results"
            elif all(a <= b for a, b in zip(ranked, ranked[1:])):
                pattern = "Lower category in the most recent result"
            elif all(a >= b for a, b in zip(ranked, ranked[1:])):
                pattern = "Higher category in the most recent result"
            else:
                pattern = "Levels varied across recent results"
        pattern_rows.append({
            "Area": sub,
            "Observed levels (oldest to newest)": " → ".join(reversed(observed)) or "—",
            "Observation": pattern,
        })
    ui.section_header("history", "Patterns across your assessments",
                      "A simple comparison of result categories, not a diagnosis or a measure of progress.")
    st.dataframe(pattern_rows, use_container_width=True, hide_index=True)
    ui.status_badge(ui.level_from_result(rows[0]["severity_bands"]),
                    caption=f"most recent: {cc.date_str(rows[0]['created_at'])}")
    st.dataframe([{"Date": cc.date_str(r["created_at"]), "Mode": r["screening_mode"], "Levels (D / A / S)": cc.bands_str(r["severity_bands"])} for r in rows],
                 use_container_width=True, hide_index=True)
    by_id = {r["id"]: r for r in rows}
    pick = st.selectbox("Open a record", list(by_id), format_func=lambda i: rec_label(by_id[i]), index=None)
    if pick:
        r = by_id[pick]
        st.markdown(f"**{cc.date_str(r['created_at'])}** · mode: {r['screening_mode']}")
        for k, v in r["severity_bands"].items(): st.markdown(f"- {k}: {v}")
        mine = [f for f in fu if f["assessment_id"] == pick]
        if mine:
            st.markdown("**Check-ins linked to this assessment**")
            st.dataframe([{"Date": cc.date_str(f["created_at"]), "Mood": f["mood"], "Stress": f["stress"], "Anxiety": f["anxiety"],
                           "Energy": f["energy"], "Sleep": f["sleep"], "Note": f["note"] or ""} for f in mine], hide_index=True, use_container_width=True)
        ok = st.checkbox("I understand deleting this record is permanent", key="del_ok")
        if st.button("Delete this record", icon=":material/delete_outline:"):
            if not ok: st.warning("Tick the confirmation box first.")
            else:
                done = guarded(cc.api, S, lambda c: c.rpc("delete_my_assessment", {"p_id": pick}).execute()).data
                if done: guarded(cc.log, S, "assessment_deleted")
                goto("history", ("success" if done else "warning", "Record deleted." if done else "Nothing was deleted."))

# ---------------------------------------------------------------- check-in
def fetch_checkins():
    return guarded(cc.api, S, lambda c: c.table("carecompass_followups").select("created_at,mood,stress,anxiety,energy,sleep,feelings,note")
                   .order("created_at", desc=True).limit(60).execute()).data

def screen_followup():
    nav_bar(); flash_show()
    ui.page_header("Check in with yourself", "A private record of how you are doing over time. It is not a diagnosis.", "checkin")
    if not S["consent"].get("followup"):
        st.info("Saving check-ins is turned off. Turn it on to keep a private record you can look back on.")
        if st.button("Turn on check-in saving", type="primary", icon=":material/arrow_forward:"):
            guarded(cc.set_consent, S, "followup", True); goto("followup", ("success", "Check-in saving is on."))
        return
    rep_ = st.session_state.pop("ci_reply", None)
    if rep_:
        st.success(rep_["text"])
        if rep_["show_support"]: st.warning(cc.SUPPORT_LINES)
    n = st.session_state.get("ci_n", 0)
    with st.form(f"ci_{n}"):
        mood = st.select_slider("Overall, how are you feeling right now?", options=[1, 2, 3, 4, 5], value=3,
                                format_func=lambda v: f"{v} — {cc.MOOD_LABELS[v]}", key=f"ci_mood_{n}")
        feelings = st.multiselect("Which words fit best? (optional)", cc.FEELINGS, key=f"ci_feel_{n}")
        c = st.columns(2)
        stress = c[0].slider("Stress right now (1 calm - 5 very stressed)", 1, 5, 3, key=f"ci_stress_{n}")
        anxiety = c[1].slider("Anxiety right now (1 calm - 5 very anxious)", 1, 5, 3, key=f"ci_anx_{n}")
        energy = c[0].slider("Energy right now (1 very low - 5 high)", 1, 5, 3, key=f"ci_energy_{n}")
        sleep = c[1].slider("Sleep last night (1 poor - 5 great)", 1, 5, 3, key=f"ci_sleep_{n}")
        note = st.text_area("Anything you would like to add? (optional, max 500 characters)", max_chars=500, key=f"ci_note_{n}")
        ok = st.form_submit_button("Save my check-in", type="primary", icon=":material/check:")
    if ok:
        try:
            last = guarded(cc.api, S, lambda cl: cl.table("carecompass_assessments").select("id").order("created_at", desc=True).limit(1).execute()).data
            guarded(cc.api, S, lambda cl: cl.table("carecompass_followups").insert({
                "user_id": S["uid"], "assessment_id": last[0]["id"] if last else None, "mood": mood, "stress": stress,
                "anxiety": anxiety, "energy": energy, "sleep": sleep, "feelings": feelings or None,
                "note": (note or "")[:500] or None}).execute())
            guarded(cc.log, S, "followup_saved")
            reply = cc.checkin_reply(mood, feelings, note)
            if reply["show_support"]: guarded(cc.log, S, "safety_pathway_shown")
            st.session_state["ci_reply"] = reply
            st.session_state["ci_n"] = n + 1
            goto("followup", ("success", "Your check-in was saved. The form is ready for a fresh entry."))
        except Exception:
            st.error("Your check-in was NOT saved - something went wrong. Please try again.")
    try: rows = fetch_checkins()
    except Exception: st.error("Could not load your earlier check-ins."); return
    if not rows:
        ui.empty_state("checkin", "Your record will appear here",
                       "After your first check-in you can look back at your mood over time.")
        return
    ui.section_header("history", "Your record")
    now = rows[0]
    m = st.columns(4)
    m[0].metric("Mood", cc.MOOD_LABELS.get(now["mood"], "-")); m[1].metric("Stress", now["stress"] or "-")
    m[2].metric("Anxiety", now["anxiety"] or "-"); m[3].metric("Energy", now["energy"] or "-")
    st.caption(f"Latest check-in: {cc.date_str(now['created_at'])}" + (" · " + ", ".join(now["feelings"]) if now.get("feelings") else ""))
    t = cc.mood_trend(rows)
    if t: st.write(t)
    if len(rows) >= 2:
        df = pd.DataFrame([{"When": pd.to_datetime(r["created_at"]), "Mood": r["mood"], "Stress": r["stress"],
                            "Anxiety": r["anxiety"], "Energy": r["energy"]} for r in reversed(rows)]).set_index("When")
        chart_colors = ["#294B38", "#3C6850", "#598268", "#789782"]
        st.line_chart(df, color=chart_colors, height=240, width="stretch")
    with st.expander("All check-ins"):
        st.dataframe([{"Date": cc.date_str(r["created_at"]), "Mood": cc.MOOD_LABELS.get(r["mood"], ""), "Stress": r["stress"],
                       "Anxiety": r["anxiety"], "Energy": r["energy"], "Sleep": r["sleep"],
                       "Feelings": ", ".join(r["feelings"] or []), "Note": r["note"] or ""} for r in rows],
                     hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- chat companion
def screen_chat():
    nav_bar()
    ui.page_header("Chat companion", "A private conversation to help you talk things through.", "chat")
    st.info("A gentle space to talk things through. I am an AI, not a therapist or a person, and I cannot diagnose or give medical advice. "
            "Your messages are sent to an AI service (Groq) to write replies. They are **not saved** and disappear when you sign out.")
    if not st.checkbox("I understand", key="chat_ok"): return
    hist = st.session_state.setdefault("chat", [])
    if not hist:
        with st.chat_message("assistant"):
            st.markdown("Hi, I'm glad you're here. How are you feeling today? You can tell me as much or as little as you like.")
    for m in hist:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    prompt = st.chat_input("Type here...")
    if prompt:
        hist.append({"role": "user", "content": prompt[:1500]})
        with st.chat_message("user"): st.markdown(prompt[:1500])
        with st.chat_message("assistant"):
            with st.spinner("..."):
                text, kind = cc.chat_reply(hist)
            st.markdown(text)
        hist.append({"role": "assistant", "content": text})
        st.session_state["chat_err"] = cc.LAST_GROQ_ERROR if kind == "fallback" else ""
        if kind == "crisis": guarded(cc.log, S, "chat_crisis_shown")
    if DEBUG and st.session_state.get("chat_err"):
        st.caption(f"AI connection problem (shown because CARECOMPASS_DEBUG is on): {st.session_state['chat_err']}")
    if hist and st.button("Clear this conversation", icon=":material/delete_outline:"):
        st.session_state["chat"] = []; st.rerun()

# ---------------------------------------------------------------- settings
def screen_settings():
    nav_bar(); flash_show()
    try: guarded(cc.load_consents, S)
    except Exception: st.warning("Could not refresh your consent status; showing the last known values.")
    c = S["consent"]
    ui.page_header("Profile and privacy", "Manage your profile, data choices, and saved records.", "settings")
    ui.section_header("settings", "Your profile")
    with st.container(border=True):
        with st.form("profile"):
            name = st.text_input("Name (optional)", value=S.get("name") or "", max_chars=60)
            age = st.number_input("Age", min_value=10, max_value=100, value=S.get("age"), step=1)
            gender = st.selectbox("Gender", cc.GENDER_CHOICES, index=cc.GENDER_CHOICES.index(S["gender"]) if S.get("gender") in cc.GENDER_CHOICES else None)
            save_p = st.form_submit_button("Save profile", type="primary", icon=":material/check:")
    if save_p:
        try:
            guarded(cc.save_profile, S, name, age, gender); guarded(cc.log, S, "profile_saved")
            goto("settings", ("success", "Profile saved."))
        except Exception:
            st.error("Your profile was NOT saved - something went wrong.")
    ui.section_header("support", "Privacy and consent", "Your choices stay with your account and can be changed here.")
    with st.container(border=True):
        st.markdown(f"**Account:** {S['email']}  \n**Assessment consent:** {'given' if c.get('assessment') else 'not given'}  \n"
                    f"**Follow-up consent:** {'given' if c.get('followup') else 'not given'}  \n**Notice version:** {cc.NOTICE_VERSION}")
        fol = st.checkbox("Allow voluntary follow-up check-ins", value=bool(c.get("followup")))
        if st.button("Save follow-up consent", icon=":material/check:"):
            guarded(cc.set_consent, S, "followup", fol); goto("settings", ("success", "Follow-up consent updated."))
        if c.get("assessment") and st.button("Withdraw assessment consent", icon=":material/do_not_disturb_on:"):
            guarded(cc.set_consent, S, "assessment", False); guarded(cc.set_consent, S, "followup", False)
            goto("settings", ("success", "Consent withdrawn. New assessments will not start until you consent again."))

    ui.section_header("history", "Delete data or request account removal", "These actions cannot be undone.")
    with st.container(border=True):
        ok = st.checkbox("I understand these actions cannot be undone", key="set_ok")
        c2 = st.columns(2)
        if c2[0].button("Delete all my assessments", icon=":material/delete_outline:", use_container_width=True):
            if not ok: st.warning("Tick the confirmation box first.")
            else:
                n = guarded(cc.api, S, lambda cl: cl.rpc("delete_all_my_assessments").execute()).data
                guarded(cc.log, S, "assessment_deleted"); goto("settings", ("success", f"Deleted {n} assessment(s) and their follow-ups."))
        if c2[1].button("Request account deletion", icon=":material/person_remove:", use_container_width=True):
            if not ok: st.warning("Tick the confirmation box first.")
            else:
                guarded(cc.api, S, lambda cl: cl.rpc("request_account_deletion").execute()); guarded(cc.log, S, "deletion_requested")
                goto("settings", ("success", "Your deletion request is recorded. An administrator will remove your account and data, per the retention notice."))
    with st.expander("Privacy notice"): st.markdown(cc.PRIVACY)

# ---------------------------------------------------------------- router
SCREENS = dict(plan=screen_plan, welcome=screen_welcome, auth=screen_auth, consent=screen_consent, home=screen_home, assess=screen_assess,
               context=screen_context, results=screen_results, history=screen_history, followup=screen_followup, settings=screen_settings, chat=screen_chat)
scr = st.session_state.screen
if scr not in ("welcome", "auth") and not S.get("token"):
    scr = st.session_state.screen = "welcome"
if S.get("token") and scr not in ("welcome", "auth", "consent"): sidebar_nav()
if scr not in ("history", "followup", "settings"): flash_show()
st.markdown(f'<span class="cc-route-marker" data-page="{scr}"></span>', unsafe_allow_html=True)
SCREENS[scr]()
