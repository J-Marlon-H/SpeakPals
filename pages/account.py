import streamlit as st
from pipeline import (VOICES, VOICES_BY_LANG, MODELS, LESSON_STATE_KEYS, SCENE_CATALOG,
                      SETTINGS_DEFAULTS, SCENE_PRIMARY_VOICE)
from db import require_auth, upsert_profile, load_profile, load_knowledge_profile, get_user_email

require_auth()

# Always load the user's saved profile from DB so the form shows their actual settings.
# Skipped if not authenticated (Supabase not configured).
if "sb_user_id" in st.session_state:
    _profile = load_profile(st.session_state.sb_user_id, st.session_state.sb_access_token)
else:
    _profile = {}
for _k, _v in {**SETTINGS_DEFAULTS, **_profile}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

st.set_page_config(page_title="Account — SpeakPals", page_icon="⚙", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html,body{font-family:'Inter',sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#ffffff!important}
  .block-container{padding:3rem 2rem!important;max-width:520px!important;margin:auto}

  /* Labels */
  label,.stSelectbox label,.stTextInput label{
    color:rgba(17,24,39,.65)!important;font-size:12px!important;
    font-weight:600!important;letter-spacing:.5px!important}

  /* Text inputs */
  .stTextInput input{
    background:#ffffff!important;color:#111827!important;
    -webkit-text-fill-color:#111827!important;
    border:1px solid #e5e5e5!important;border-radius:10px!important;
    font-size:15px!important}
  .stTextInput input:focus{
    border-color:#0d9488!important;
    box-shadow:0 0 0 3px rgba(13,148,136,.12)!important}
  .stTextInput input:-webkit-autofill,
  .stTextInput input:-webkit-autofill:focus{
    -webkit-box-shadow:0 0 0 100px #ffffff inset!important;
    -webkit-text-fill-color:#111827!important}

  /* Selectboxes */
  .stSelectbox > div > div{
    background:#ffffff!important;color:#111827!important;
    border:1px solid #e5e5e5!important;border-radius:10px!important}

  /* Buttons */
  .stButton button{
    border-radius:10px!important;font-weight:600!important;font-size:13px!important;
    background:rgba(13,148,136,.1)!important;
    border:1px solid rgba(13,148,136,.28)!important;
    color:#0d9488!important;
    transition:background .2s,border-color .2s}
  .stButton button:hover{
    background:rgba(13,148,136,.2)!important;
    border-color:rgba(13,148,136,.5)!important}

  div[data-testid="stVerticalBlock"]{gap:0.5rem!important}

  /* Section divider */
  .sec-div{height:1px;background:rgba(17,24,39,.1);margin:22px 0 18px}
  .sec-label{font:700 10px 'Inter',sans-serif;letter-spacing:2px;
    color:rgba(17,24,39,.4);text-transform:uppercase;margin:0 0 10px}
</style>""", unsafe_allow_html=True)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:4px 0 28px'>
  <div style='font:800 26px/1 Inter,sans-serif;color:#111827;letter-spacing:-.5px;
              margin-bottom:6px'>⚙ Settings</div>
  <div style='font:400 13px Inter;color:rgba(17,24,39,.55)'>
    Personalise your SpeakPals experience
  </div>
</div>""", unsafe_allow_html=True)

# ── Student profile ────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Student Profile</div>", unsafe_allow_html=True)

name     = st.text_input("Name", value=st.session_state.get("s_name", "Marlon"))
level    = st.selectbox("Level", ["A1", "A2", "B1", "B2"],
                        index=["A1", "A2", "B1", "B2"].index(
                            st.session_state.get("s_level", "A1")))
bg_langs = ["English", "German", "Spanish", "French", "Dutch", "Swedish"]
bg_lang  = st.selectbox("Your language background", bg_langs,
                        index=bg_langs.index(
                            st.session_state.get("s_bg_lang", "German")
                            if st.session_state.get("s_bg_lang", "German") in bg_langs
                            else "German"))

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Language & voice & model ───────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Preferences</div>", unsafe_allow_html=True)

languages = ["Danish", "Portuguese (Brazilian)"]
language  = st.selectbox(
    "Language to learn",
    languages,
    index=languages.index(
        st.session_state.get("s_language", "Danish")
        if st.session_state.get("s_language", "Danish") in languages else "Danish"
    )
)

lang_voices = VOICES_BY_LANG.get(language, VOICES)
voice_keys  = list(lang_voices.keys())
saved_voice = st.session_state.get("s_voice_label", "")
voice_label = st.selectbox(
    "Tutor voice",
    voice_keys,
    index=voice_keys.index(saved_voice) if saved_voice in voice_keys else 0
)

scene_primary = SCENE_PRIMARY_VOICE.get(language, SCENE_PRIMARY_VOICE["Danish"])
affected = [
    s["title"] for s in SCENE_CATALOG
    if scene_primary.get(s["key"]) == voice_label
]
if affected:
    st.markdown(
        f"<div style='background:rgba(13,148,136,.07);border:1px solid rgba(13,148,136,.2);"
        f"border-radius:10px;padding:10px 14px;margin-top:4px;font:400 12px Inter;"
        f"color:rgba(17,24,39,.65)'>"
        f"Auto-swap: <span style='color:#0d9488'>{', '.join(affected)}</span> "
        f"will use a different character voice to avoid your tutor voice."
        f"</div>",
        unsafe_allow_html=True
    )

model_keys  = list(MODELS.keys())
model_label = st.selectbox(
    "AI model",
    model_keys,
    index=model_keys.index(
        st.session_state.get("s_model_label", "Haiku 4.5 — fastest"))
)

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Save & navigate ────────────────────────────────────────────────────────────
def _save():
    data = {
        "s_name": name, "s_level": level, "s_bg_lang": bg_lang, "s_language": language,
        "s_voice_label": voice_label, "s_model_label": model_label,
    }
    st.session_state.update(data)
    if "sb_user_id" in st.session_state:
        upsert_profile(
            st.session_state.sb_user_id,
            st.session_state.sb_access_token,
            data,
        )

col_save, col_home, col_back, col_ob = st.columns(4)
with col_save:
    if st.button("Save", use_container_width=True):
        _save()
        st.success("Saved!")
with col_home:
    if st.button("🏠 Home", use_container_width=True):
        _save()
        st.switch_page("pages/home.py")
with col_back:
    if st.button("← Lesson", use_container_width=True):
        _save()
        st.switch_page("pages/lesson.py")
with col_ob:
    if st.button("👋 Interview", use_container_width=True):
        _save()
        st.switch_page("pages/onboarding.py")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Session ────────────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Session</div>", unsafe_allow_html=True)

if st.button("🔄 Clear lesson & restart", use_container_width=True):
    for k in LESSON_STATE_KEYS:
        st.session_state.pop(k, None)
    st.switch_page("pages/lesson.py")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)
st.markdown("<div class='sec-label'>Account</div>", unsafe_allow_html=True)

# Resolve email — prefer session state, fall back to live API call if missing.
_email = st.session_state.get("sb_email", "")
if not _email and "sb_access_token" in st.session_state:
    _email = get_user_email(st.session_state.sb_access_token)
    if _email:
        st.session_state["sb_email"] = _email

st.markdown(
    f"<div style='font:400 12px Inter;color:rgba(17,24,39,.5);margin-bottom:10px'>"
    f"Signed in as <strong>{_email or '—'}</strong></div>",
    unsafe_allow_html=True
)
if st.button("Sign out", use_container_width=True):
    from db import sign_out
    sign_out(st.session_state.get("sb_access_token", ""))
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.switch_page("pages/login.py")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)
st.markdown("<div class='sec-label'>Your Learning Profile</div>", unsafe_allow_html=True)

st.markdown("""
<div style='background:linear-gradient(135deg,rgba(13,148,136,.08),rgba(13,148,136,.03));
            border:1px solid rgba(13,148,136,.22);border-radius:14px;
            padding:16px 18px;margin-bottom:20px'>
  <div style='font:700 13px Inter;color:#0d9488;margin-bottom:6px'>
    🧠 Your tutor remembers you
  </div>
  <div style='font:400 13px/1.65 Inter;color:rgba(17,24,39,.65)'>
    Every session, SpeakPals builds a richer picture of who you are and how you learn.
    Below is <strong>everything we store about you</strong> — fully transparent, always
    up to date. The more you practise, the more personalised your experience becomes.
  </div>
</div>""", unsafe_allow_html=True)

# ── Add expander card styles ────────────────────────────────────────────────────
st.markdown("""<style>
  /* Profile expander cards */
  [data-testid="stExpander"]{
    border:1px solid rgba(17,24,39,.1)!important;
    border-radius:12px!important;
    overflow:hidden!important;
    margin-bottom:8px!important;
    background:#ffffff!important;
    box-shadow:0 1px 4px rgba(17,24,39,.05)!important;
    transition:box-shadow .18s ease!important}
  [data-testid="stExpander"]:hover{
    box-shadow:0 3px 12px rgba(13,148,136,.12)!important;
    border-color:rgba(13,148,136,.25)!important}
  [data-testid="stExpander"] summary{
    padding:14px 16px!important;
    font:600 13px Inter,sans-serif!important;
    color:#111827!important}
  [data-testid="stExpander"] summary:hover{
    background:rgba(13,148,136,.04)!important}
  [data-testid="stExpanderDetails"]{
    padding:0 16px 16px!important;
    border-top:1px solid rgba(17,24,39,.07)!important}
</style>""", unsafe_allow_html=True)

# ── Always-shown category definitions ──────────────────────────────────────────
if "sb_user_id" in st.session_state:
    _kp = load_knowledge_profile(st.session_state.sb_user_id, st.session_state.sb_access_token)
else:
    _kp = {}

_CATEGORIES = [
    (
        "language_level",
        "📊", "Language Level",
        "Your current proficiency in the target language — what vocabulary and grammar you've mastered, where you struggle, and how your level is progressing over time.",
    ),
    (
        "learning_motivation",
        "🎯", "Learning Motivation",
        "Why you're learning this language. Your personal goals, dreams, and the stories behind them — this shapes what topics your tutor brings up.",
    ),
    (
        "personal_use_context",
        "🌍", "Where You'll Use It",
        "The real-life situations where you need the language — at work, with a partner, travelling, living abroad, or daily errands. Your tutor picks scenarios relevant to your life.",
    ),
    (
        "common_errors",
        "🔍", "Errors & Patterns",
        "Mistakes and habits your tutor has noticed across sessions — wrong words, grammar slips, a tendency to fall back on English. Tracked silently so your tutor can gently correct them.",
    ),
    (
        "conversation_history",
        "💬", "Conversation History",
        "A running diary of what we've covered together — scenes practised, topics discussed, moments worth remembering. Your tutor uses this to pick up where you left off.",
    ),
    (
        "personal_facts",
        "👤", "Personal Facts",
        "Facts you've shared about yourself — where you live, your job, people in your life. Your tutor uses these to make conversations feel natural and personal to you.",
    ),
    (
        "tutor_observations",
        "💡", "Tutor Observations",
        "Anything else your tutor has noticed that doesn't fit the other categories — your learning style, confidence patterns, moments of breakthrough or frustration, curiosity spikes, pacing preferences, and more.",
    ),
]

for _key, _icon, _label, _desc in _CATEGORIES:
    _val     = _kp.get(_key, {})
    _content = (_val.get("content", "") if isinstance(_val, dict) else str(_val)).strip()
    _ts      = (_val.get("updated_at", "") if isinstance(_val, dict) else "")
    _filled  = bool(_content)

    if _filled and _ts:
        _status = f"Updated {_ts[:10]}"
        _dot    = "🟢"
    elif _filled:
        _status = "Updated"
        _dot    = "🟢"
    else:
        _status = "Not yet filled"
        _dot    = "⚪"

    _exp_label = f"{_icon} **{_label}** &nbsp; {_dot} *{_status}*"

    with st.expander(_exp_label, expanded=False):
        st.markdown(
            f"<div style='font:400 12px/1.6 Inter;color:rgba(17,24,39,.5);"
            f"margin:10px 0 14px;font-style:italic'>{_desc}</div>",
            unsafe_allow_html=True,
        )
        if _filled:
            st.markdown(
                f"<div style='font:400 13px/1.7 Inter;color:#111827;"
                f"white-space:pre-wrap'>{_content}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font:400 13px Inter;color:rgba(17,24,39,.35);"
                "font-style:italic;padding:4px 0'>"
                "Nothing recorded yet — this fills up as you practise and chat with your tutor."
                "</div>",
                unsafe_allow_html=True,
            )

# ── Any AI-added custom categories not in the predefined list ──────────────────
_known_keys = {c[0] for c in _CATEGORIES}
_custom     = {k: v for k, v in _kp.items() if k not in _known_keys}
if _custom:
    st.markdown(
        "<div style='font:700 10px Inter;letter-spacing:2px;text-transform:uppercase;"
        "color:rgba(17,24,39,.3);margin:18px 0 8px'>Also noted by your tutor</div>",
        unsafe_allow_html=True,
    )
    for _key, _val in _custom.items():
        _label   = _key.replace("_", " ").title()
        _content = (_val.get("content", "") if isinstance(_val, dict) else str(_val)).strip()
        _ts      = (_val.get("updated_at", "") if isinstance(_val, dict) else "")
        _exp_label = f"✨ **{_label}**" + (f"  ·  *{_ts[:10]}*" if _ts else "")
        with st.expander(_exp_label, expanded=False):
            st.markdown(
                f"<div style='font:400 13px/1.7 Inter;color:#111827;"
                f"white-space:pre-wrap'>{_content or '—'}</div>",
                unsafe_allow_html=True,
            )
