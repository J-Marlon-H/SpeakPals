import streamlit as st
from pipeline import SCENE_CATALOG, LESSON_STATE_KEYS, SETTINGS_DEFAULTS
from scene_images import img_b64 as _img_b64
from db import require_auth, load_profile, load_knowledge_profile
from prompts import get_tutor_name

require_auth()

# ── Load profile from Supabase into session_state ──────────────────────────────
if "sb_user_id" in st.session_state:
    _profile = load_profile(st.session_state.sb_user_id, st.session_state.sb_access_token)
else:
    _profile = {}
for _k, _v in {**SETTINGS_DEFAULTS, **_profile}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Load knowledge profile once per session ────────────────────────────────────
if "sb_user_id" in st.session_state and not st.session_state.get("onboarding_checked"):
    _kp = load_knowledge_profile(
        st.session_state.sb_user_id,
        st.session_state.sb_access_token,
    )
    st.session_state["knowledge_profile"]  = _kp
    st.session_state["onboarding_checked"] = True

st.set_page_config(page_title="SpeakPals", page_icon="🇩🇰",
                   layout="wide", initial_sidebar_state="collapsed")

# ── Separate lesson scenes from free conversation ──────────────────────────────
_LESSON_SCENES = [s for s in SCENE_CATALOG if not s.get("free_conv")]
_FREE_SCENE    = next((s for s in SCENE_CATALOG if s.get("free_conv")), None)

# ── Build CSS selectors (lesson scenes only) ───────────────────────────────────
_sel  = ", ".join(f".st-key-{s['key']} button" for s in _LESSON_SCENES)
_selH = ", ".join(f".st-key-{s['key']} button:hover" for s in _LESSON_SCENES)
_selP = ", ".join(
    f".st-key-{s['key']} button [data-testid='stMarkdownContainer'],"
    f" .st-key-{s['key']} button p"
    for s in _LESSON_SCENES
)
_selP2 = ", ".join(f".st-key-{s['key']} button p" for s in _LESSON_SCENES)

def _scene_card_css() -> str:
    """Per-scene height + background image/gradient rules in one pass."""
    parts = []
    for s in _LESSON_SCENES:
        n = min(len([x for x in _LESSON_SCENES if x["level"] == s["level"]]), 3)
        h = {1: "340px", 2: "240px", 3: "185px"}[n]
        parts.append(f".st-key-{s['key']} button{{height:{h}!important}}")
        img = _img_b64(s["file"]) if s.get("file") else None
        if img:
            rule = (f"background-image:url('{img}')!important;"
                    f"background-size:cover!important;"
                    f"background-position:top center!important")
        else:
            rule = f"background:{s['gradient']}!important"
        parts.append(f".st-key-{s['key']} button,.st-key-{s['key']} button:hover{{{rule}}}")
    return " ".join(parts)

_tutor_img = _img_b64("tutor.svg") if _FREE_SCENE else None
_tutor_bg_rule = (
    f"background-image:url('{_tutor_img}')!important;"
    "background-size:cover!important;background-position:top center!important"
    if _tutor_img else
    "background:linear-gradient(160deg,#0d9488 0%,#065f46 60%,#042f2e 100%)!important"
)

st.markdown(f"""<style>
  html,body{{font-family:system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important}}
  #MainMenu,footer,[data-testid="stToolbar"]{{visibility:hidden}}
  [data-testid="stHeader"],header,.stAppHeader{{display:none!important}}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{{display:none!important}}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:#ffffff!important}}
  .block-container{{padding:2.5rem 3rem!important;max-width:1120px!important;margin:auto}}

  .section-head{{
    font:700 13px/1 system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif;letter-spacing:1.5px;
    text-transform:uppercase;color:rgba(17,24,39,.4);
    margin:48px 0 20px;padding-bottom:8px;
    border-bottom:1px solid rgba(17,24,39,.1)}}
  .section-head.current{{color:#0d9488;border-bottom-color:rgba(13,148,136,.3)}}

  /* Header nav buttons */
  .st-key-nav_feedback button,.st-key-nav_settings button{{
    white-space:pre-wrap!important;text-align:center!important;
    height:70px!important;flex-direction:column!important;
    background:#ffffff!important;border:1px solid #e5e5e5!important;
    color:#374151!important;box-shadow:0 1px 3px rgba(0,0,0,.06)!important}}
  .st-key-nav_feedback button:hover,.st-key-nav_settings button:hover{{
    border-color:rgba(13,148,136,.4)!important;color:#0d9488!important;
    background:#ffffff!important;box-shadow:0 2px 8px rgba(13,148,136,.1)!important}}

  label,.stButton button{{color:#111827!important}}
  .stButton button{{
    border-radius:12px!important;font-weight:600!important;font-size:15px!important;
    background:rgba(13,148,136,.12)!important;
    border:1px solid rgba(13,148,136,.3)!important;color:#0d9488!important;
    transition:background .2s,border-color .2s}}
  .stButton button:hover{{
    background:rgba(13,148,136,.22)!important;
    border-color:rgba(13,148,136,.5)!important}}

  /* ── Lesson scene card buttons ──────────────────────────────────────────── */
  {_sel} {{
    display:block!important;width:100%!important;
    padding:0!important;margin:0!important;
    border-radius:18px!important;overflow:hidden!important;border:none!important;
    background-size:cover!important;background-position:top center!important;
    box-shadow:0 4px 20px rgba(17,24,39,.18)!important;
    cursor:pointer!important;position:relative!important;
    transition:transform .22s cubic-bezier(.34,1.56,.64,1),
               box-shadow .22s ease,filter .22s ease!important}}
  {_selH} {{
    transform:scale(1.035) translateY(-4px)!important;
    box-shadow:0 16px 40px rgba(13,148,136,.3),0 4px 16px rgba(17,24,39,.15)!important;
    filter:brightness(1.05)!important}}
  {_selP} {{
    position:absolute!important;
    bottom:0!important;left:0!important;right:0!important;top:auto!important;
    padding:28px 16px 14px!important;
    background:linear-gradient(to top,rgba(10,10,20,.88) 0%,
               rgba(10,10,20,.35) 55%,transparent 100%)!important;
    border-radius:0 0 18px 18px!important;
    text-align:left!important;pointer-events:none!important;margin:0!important}}
  {_selP2} {{
    font:800 19px/1.2 system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important;
    color:#fff!important;text-align:left!important;margin:0!important}}

  .scene-desc{{
    font:400 14px system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif;color:rgba(17,24,39,.5);
    margin-top:7px;margin-bottom:28px;padding:0 2px;line-height:1.5}}

  /* ── Tutor card button — same style as lesson scene cards ──────────────── */
  .st-key-btn_tutor_chat button {{
    display:block!important;width:100%!important;height:320px!important;
    padding:0!important;margin:0!important;
    border-radius:18px!important;overflow:hidden!important;border:none!important;
    {_tutor_bg_rule}
    background-size:cover!important;background-position:top center!important;
    box-shadow:0 4px 20px rgba(17,24,39,.18)!important;
    cursor:pointer!important;position:relative!important;
    transition:transform .22s cubic-bezier(.34,1.56,.64,1),
               box-shadow .22s ease!important}}
  .st-key-btn_tutor_chat button:hover {{
    {_tutor_bg_rule}
    background-size:cover!important;background-position:top center!important;
    transform:scale(1.035) translateY(-4px)!important;
    box-shadow:0 16px 40px rgba(13,148,136,.3),0 4px 16px rgba(17,24,39,.15)!important}}
  .st-key-btn_tutor_chat button [data-testid="stMarkdownContainer"],
  .st-key-btn_tutor_chat button p {{
    position:absolute!important;
    bottom:0!important;left:0!important;right:0!important;top:auto!important;
    padding:28px 16px 14px!important;
    background:linear-gradient(to top,rgba(10,10,20,.88) 0%,
               rgba(10,10,20,.35) 55%,transparent 100%)!important;
    border-radius:0 0 18px 18px!important;
    text-align:left!important;pointer-events:none!important;margin:0!important}}
  .st-key-btn_tutor_chat button p {{
    font:800 19px/1.2 system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important;
    color:#fff!important;text-align:left!important;margin:0!important}}

  /* Per-scene heights + background images */
  {_scene_card_css()}
</style>""", unsafe_allow_html=True)


# ── Settings ───────────────────────────────────────────────────────────────────
name        = st.session_state.get("s_name",     "there")
level       = st.session_state.get("s_level",    "A1")
language    = st.session_state.get("s_language", "Danish")
tutor_name  = get_tutor_name(language)
LEVEL_LABELS = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate"}

_FLAG_SVG = {
    "Danish": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 37 28">'
        '<rect width="37" height="28" fill="#C60C30"/>'
        '<rect x="12" y="0" width="5" height="28" fill="#fff"/>'
        '<rect x="0" y="11.5" width="37" height="5" fill="#fff"/>'
        '</svg>'
    ),
    "Portuguese (Brazilian)": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 28">'
        '<rect width="40" height="28" fill="#009B3A"/>'
        '<polygon points="20,2 38,14 20,26 2,14" fill="#FEDF00"/>'
        '<circle cx="20" cy="14" r="7.5" fill="#002776"/>'
        '<path d="M12.8,11.2 A8.5,8.5 0 0 1 27.2,11.2" stroke="#fff" stroke-width="1.6" fill="none"/>'
        '<rect x="12.5" y="13.2" width="15" height="1.6" fill="#fff"/>'
        '</svg>'
    ),
}

def _flag_img(lang: str, height: int = 32) -> str:
    import base64
    svg = _FLAG_SVG.get(lang, "")
    if not svg:
        return ""
    b64 = base64.b64encode(svg.encode()).decode()
    return (f"<img src='data:image/svg+xml;base64,{b64}' "
            f"height='{height}' style='vertical-align:middle;border-radius:4px;"
            f"box-shadow:0 2px 8px rgba(0,0,0,.2);margin-left:10px'>")

flag_img = _flag_img(language, height=30)

# ── Header ─────────────────────────────────────────────────────────────────────
col_hdr, col_fb, col_acct = st.columns([5, 1, 1])
with col_hdr:
    st.markdown(f"""
<div style='padding:8px 0 4px'>
  <div style='font:800 34px/1.1 system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif;color:#111827;letter-spacing:-.5px;display:flex;align-items:center;gap:0'>
    Hej, {name}! 👋{flag_img}
  </div>
  <div style='font:400 14px system-ui;color:rgba(17,24,39,.6);margin-top:6px'>
    Your level: <span style='color:#0d9488;font-weight:600'>{level} — {LEVEL_LABELS.get(level,"")}</span>
    &nbsp;·&nbsp; Practise {language} with {tutor_name}
  </div>
</div>""", unsafe_allow_html=True)
with col_fb:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("📋\nFeedback", key="nav_feedback", use_container_width=True):
        st.switch_page("pages/feedback.py")
    st.markdown("</div>", unsafe_allow_html=True)
with col_acct:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("⚙️\nSettings", key="nav_settings", use_container_width=True):
        st.switch_page("pages/account.py")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Two-column layout ──────────────────────────────────────────────────────────
col_scenes, col_tutor = st.columns([3, 1], gap="large")

# ── LEFT: Lesson scene cards ───────────────────────────────────────────────────
with col_scenes:
    LEVEL_ORDER = ["A1", "A2", "B1", "B2"]
    # User's level first, then the rest in order
    levels_with_scenes = [lvl for lvl in LEVEL_ORDER
                          if any(s["level"] == lvl for s in _LESSON_SCENES)]
    ordered_levels = (
        [level] + [lvl for lvl in levels_with_scenes if lvl != level]
        if level in levels_with_scenes else levels_with_scenes
    )

    for lvl in ordered_levels:
        scenes = [s for s in _LESSON_SCENES if s["level"] == lvl]
        is_recommended = lvl == level
        label = (
            f"{lvl} · {LEVEL_LABELS.get(lvl, lvl)} &nbsp;"
            f"<span style='background:#0d9488;color:#fff;font-size:10px;font-weight:700;"
            f"letter-spacing:.5px;padding:2px 7px;border-radius:20px;vertical-align:middle'>"
            f"Recommended</span>"
            if is_recommended else
            f"{lvl} · {LEVEL_LABELS.get(lvl, lvl)}"
        )
        head_style = "section-head current" if is_recommended else "section-head"
        st.markdown(f"<div class='{head_style}'>{label}</div>", unsafe_allow_html=True)
        cols = st.columns(min(len(scenes), 3), gap="large")
        for col, scene in zip(cols, scenes):
            with col:
                if st.button(scene["title"], key=scene["key"], use_container_width=True):
                    st.session_state["selected_scene"] = scene["key"]
                    for k in LESSON_STATE_KEYS:
                        st.session_state.pop(k, None)
                    st.switch_page("pages/lesson.py")
                st.markdown(
                    f"<div class='scene-desc'>{scene['desc']}</div>",
                    unsafe_allow_html=True,
                )

# ── RIGHT: Tutor conversation card ────────────────────────────────────────────
with col_tutor:
    st.markdown(
        "<div style='margin-top:28px'>"
        "<div style='font:700 11px/1 system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif;letter-spacing:2px;"
        "text-transform:uppercase;color:rgba(17,24,39,.4);margin-bottom:12px;"
        "padding-bottom:8px;border-bottom:1px solid rgba(17,24,39,.1)'>"
        "Your Tutor</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if _FREE_SCENE and st.button(
        "Talk with your Tutor",
        key="btn_tutor_chat",
        use_container_width=True,
    ):
        st.session_state["selected_scene"] = "free_conversation"
        for k in LESSON_STATE_KEYS:
            st.session_state.pop(k, None)
        st.switch_page("pages/lesson.py")

    st.markdown(
        "<div class='scene-desc' style='margin-top:8px'>"
        "Free conversation with your tutor — topics guided by your goals and memory</div>",
        unsafe_allow_html=True,
    )
