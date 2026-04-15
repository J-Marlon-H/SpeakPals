import streamlit as st
from pipeline import (VOICES, VOICES_BY_LANG, MODELS, LESSON_STATE_KEYS, SCENE_CATALOG,
                      SETTINGS_DEFAULTS, SCENE_PRIMARY_VOICE)

_LANG_PROFILE_KEY = {"Danish": "danish", "Portuguese (Brazilian)": "portuguese_brazilian"}
from db import (require_auth, upsert_profile, load_profile, load_knowledge_profile,
                delete_knowledge_profile, get_user_email, update_password)

require_auth()

# Always load the user's saved profile from DB so the form shows their actual settings.
if "sb_user_id" in st.session_state:
    _profile = load_profile(st.session_state.sb_user_id, st.session_state.sb_access_token)
else:
    _profile = {}
for _k, _v in {**SETTINGS_DEFAULTS, **_profile}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Consume new-user flag once — used to show the integration setup callout
_is_new_user = st.session_state.pop("is_new_user", False)

st.set_page_config(page_title="Settings — SpeakPals", page_icon="⚙", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""<style>
  html,body{font-family:system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#ffffff!important}
  .block-container{padding:3rem 2rem!important;max-width:520px!important;margin:auto}

  label,.stSelectbox label,.stTextInput label{
    color:rgba(17,24,39,.65)!important;font-size:12px!important;
    font-weight:600!important;letter-spacing:.5px!important}

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

  .stSelectbox > div > div{
    background:#ffffff!important;color:#111827!important;
    border:1px solid #e5e5e5!important;border-radius:10px!important}

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

  .sec-div{height:1px;background:rgba(17,24,39,.1);margin:22px 0 18px}
  .sec-label{font:700 10px system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif;letter-spacing:2px;
    color:rgba(17,24,39,.4);text-transform:uppercase;margin:0 0 10px}

  /* Profile expander cards */
  [data-testid="stExpander"]{
    border:1px solid rgba(17,24,39,.1)!important;border-radius:12px!important;
    overflow:hidden!important;margin-bottom:8px!important;background:#ffffff!important;
    box-shadow:0 1px 4px rgba(17,24,39,.05)!important;transition:box-shadow .18s ease!important}
  [data-testid="stExpander"]:hover{
    box-shadow:0 3px 12px rgba(13,148,136,.12)!important;
    border-color:rgba(13,148,136,.25)!important}
  [data-testid="stExpander"] summary{
    padding:14px 16px!important;font:600 13px system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important;color:#111827!important}
  [data-testid="stExpander"] summary:hover{background:rgba(13,148,136,.04)!important}
  [data-testid="stExpanderDetails"]{
    padding:0 16px 16px!important;border-top:1px solid rgba(17,24,39,.07)!important}
</style>""", unsafe_allow_html=True)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:4px 0 28px'>
  <div style='font:800 26px/1 system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif;color:#111827;letter-spacing:-.5px;
              margin-bottom:6px'>⚙ Settings</div>
  <div style='font:400 13px system-ui;color:rgba(17,24,39,.55)'>
    Personalise your SpeakPals experience
  </div>
</div>""", unsafe_allow_html=True)

# ── Student profile ────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Student Profile</div>", unsafe_allow_html=True)

name = st.text_input("Name", value=st.session_state.get("s_name", ""))

_cefr = ["A1", "A2", "B1", "B2", "C1", "C2"]
_saved_level = st.session_state.get("s_level", "A1")
level = st.selectbox(
    "CEFR Level",
    _cefr,
    index=_cefr.index(_saved_level) if _saved_level in _cefr else 0,
    help=(
        "Your current level in the language you are learning.\n\n"
        "A1 — complete beginner\n"
        "A2 — basic phrases\n"
        "B1 — can handle simple conversations\n"
        "B2 — comfortable in most situations\n"
        "C1 — advanced, near-fluent\n"
        "C2 — mastery, near-native"
    ),
)

_bg_opts = ["English", "German", "Spanish", "French", "Dutch", "Swedish", "Other"]
_saved_bg = st.session_state.get("s_bg_lang", "English")
_bg_idx   = _bg_opts.index(_saved_bg) if _saved_bg in _bg_opts else _bg_opts.index("Other")
_bg_sel   = st.selectbox(
    "Main language background",
    _bg_opts,
    index=_bg_idx,
    help=(
        "The language you speak best — your native tongue or the language you are most "
        "fluent in. Your tutor uses this to explain concepts in a way that makes sense "
        "for someone with your background, and to spot typical mistakes speakers of your "
        "language tend to make."
    ),
)
if _bg_sel == "Other":
    _other_val = _saved_bg if _saved_bg not in _bg_opts[:-1] else ""
    bg_lang = st.text_input(
        "Specify your language",
        value=_other_val,
        placeholder="e.g. Turkish, Arabic, Hindi…",
    )
else:
    bg_lang = _bg_sel

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Language & voice & model ───────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Preferences</div>", unsafe_allow_html=True)

languages = ["Danish", "Portuguese (Brazilian)"]
_LANG_LABELS = {"Portuguese (Brazilian)": "Portuguese (Brazilian) - beta"}
language  = st.selectbox(
    "Language to learn",
    languages,
    index=languages.index(
        st.session_state.get("s_language", "Danish")
        if st.session_state.get("s_language", "Danish") in languages else "Danish"
    ),
    format_func=lambda x: _LANG_LABELS.get(x, x),
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
affected = [s["title"] for s in SCENE_CATALOG if scene_primary.get(s["key"]) == voice_label]
if affected:
    st.markdown(
        f"<div style='background:rgba(13,148,136,.07);border:1px solid rgba(13,148,136,.2);"
        f"border-radius:10px;padding:10px 14px;margin-top:4px;margin-bottom:16px;font:400 12px system-ui;"
        f"color:rgba(17,24,39,.65)'>"
        f"Auto-swap: <span style='color:#0d9488'>{', '.join(affected)}</span> "
        f"will use a different character voice to avoid your tutor voice.</div>",
        unsafe_allow_html=True
    )

model_label = "Haiku 4.5 — fastest"  # fixed — not user-configurable

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Integrations ───────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Integrations</div>", unsafe_allow_html=True)

if _is_new_user:
    st.markdown("""
<div style='background:linear-gradient(135deg,rgba(13,148,136,.1),rgba(13,148,136,.04));
            border:1px solid rgba(13,148,136,.3);border-radius:14px;
            padding:16px 18px;margin-bottom:16px'>
  <div style='font:700 13px system-ui;color:#0d9488;margin-bottom:6px'>
    👋 One more step — connect your tools
  </div>
  <div style='font:400 13px/1.65 system-ui;color:rgba(17,24,39,.65)'>
    Link your <strong>Telegram</strong> to get lessons on the go, and connect
    <strong>Google Calendar</strong> so your tutor can build conversations around your upcoming
    events. Both are optional — but they make SpeakPals much more personal.
  </div>
</div>""", unsafe_allow_html=True)
else:
    st.markdown(
        "<div style='font:400 12px/1.6 system-ui;color:rgba(17,24,39,.5);margin-bottom:12px'>"
        "Connect Telegram for lessons on the go, and Google Calendar so your tutor can "
        "build conversations around your real life.</div>",
        unsafe_allow_html=True
    )

if st.button("✈ Telegram & Calendar settings", use_container_width=True):
    st.switch_page("pages/telegram_settings.py")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Your Learning Profile ──────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Your Learning Profile</div>", unsafe_allow_html=True)

st.markdown("""
<div style='background:linear-gradient(135deg,rgba(13,148,136,.08),rgba(13,148,136,.03));
            border:1px solid rgba(13,148,136,.22);border-radius:14px;
            padding:16px 18px;margin-bottom:14px'>
  <div style='font:700 13px system-ui;color:#0d9488;margin-bottom:6px'>
    🧠 Your tutor remembers you
  </div>
  <div style='font:400 13px/1.65 system-ui;color:rgba(17,24,39,.65)'>
    Every session, SpeakPals builds a richer picture of who you are and how you learn —
    separately for each language. Below is <strong>everything we store about you</strong>.
  </div>
</div>

<div style='background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.3);
            border-radius:12px;padding:12px 16px;margin-bottom:20px;
            display:flex;gap:10px;align-items:flex-start'>
  <span style='font-size:16px;flex-shrink:0'>🔒</span>
  <div style='font:400 12px/1.6 system-ui;color:rgba(17,24,39,.65)'>
    <strong style='color:#92400e'>Your data stays yours.</strong>
    This profile is stored securely and used exclusively to personalise your experience
    inside SpeakPals. It is never shared with third parties, never sold, and never used
    to train AI models. You can reset it at any time.
  </div>
</div>""", unsafe_allow_html=True)

if "sb_user_id" in st.session_state:
    _kp = load_knowledge_profile(st.session_state.sb_user_id, st.session_state.sb_access_token)
else:
    _kp = {}

# Which language the user currently has selected (drives the profile tab shown)
_selected_lang = st.session_state.get("s_language", "Danish")
_lang_key      = _LANG_PROFILE_KEY.get(_selected_lang, "danish")
_lang_section  = _kp.get(_lang_key, {})
_shared        = _kp.get("shared", {})

# Helper — render one profile expander row
def _render_expander(key, icon, label, desc, section_dict):
    _val     = section_dict.get(key, {})
    _content = (_val.get("content", "") if isinstance(_val, dict) else str(_val)).strip()
    _ts      = (_val.get("updated_at", "") if isinstance(_val, dict) else "")
    _filled  = bool(_content)
    _dot, _status = ("🟢", f"Updated {_ts[:10]}") if (_filled and _ts) else \
                    ("🟢", "Updated")              if _filled else \
                    ("⚪", "Not yet filled")
    with st.expander(f"{icon} **{label}** &nbsp; {_dot} *{_status}*", expanded=False):
        st.markdown(
            f"<div style='font:400 12px/1.6 system-ui;color:rgba(17,24,39,.5);"
            f"margin:4px 0 10px;font-style:italic'>{desc}</div>",
            unsafe_allow_html=True,
        )
        if _filled:
            st.markdown(_content)
        else:
            st.markdown(
                "<div style='font:400 13px system-ui;color:rgba(17,24,39,.35);"
                "font-style:italic;padding:4px 0'>"
                "Nothing recorded yet — this fills up as you practise.</div>",
                unsafe_allow_html=True,
            )

# ── Language-specific section ─────────────────────────────────────────────────
st.markdown(
    f"<div style='font:700 10px system-ui;letter-spacing:2px;text-transform:uppercase;"
    f"color:rgba(17,24,39,.4);margin:0 0 10px'>{_selected_lang} — Language Profile</div>",
    unsafe_allow_html=True,
)

_LANG_CATEGORIES = [
    ("language_level",       "📊", "CEFR Level",
     "Proficiency on the A1–C2 scale — vocabulary mastered, grammar strengths, and where you struggle."),
    ("learning_motivation",  "🎯", "Learning Motivation",
     f"Why you're learning {_selected_lang}. Your personal goals shape what topics your tutor brings up."),
    ("personal_use_context", "🌍", "Where You'll Use It",
     f"Real-life situations where you need {_selected_lang} — work, a partner, travel, daily life."),
    ("common_errors",        "🔍", "Errors & Patterns",
     "Mistakes your tutor has noticed — wrong words, grammar slips, falling back to English."),
    ("conversation_history", "💬", "Conversation History",
     "A running diary of what we've covered — scenes practised, topics discussed, breakthroughs."),
    ("tutor_observations",   "💡", "Tutor Observations",
     "Learning style, confidence patterns, pacing, cultural curiosity — anything worth remembering."),
]

for _key, _icon, _label, _desc in _LANG_CATEGORIES:
    _render_expander(_key, _icon, _label, _desc, _lang_section)

# Any AI-added custom keys in the language section
_known_lang_keys = {c[0] for c in _LANG_CATEGORIES}
_custom_lang = {k: v for k, v in _lang_section.items() if k not in _known_lang_keys}
if _custom_lang:
    st.markdown(
        "<div style='font:700 10px system-ui;letter-spacing:2px;text-transform:uppercase;"
        "color:rgba(17,24,39,.3);margin:14px 0 8px'>Also noted by your tutor</div>",
        unsafe_allow_html=True,
    )
    for _key, _val in _custom_lang.items():
        _label   = _key.replace("_", " ").title()
        _content = (_val.get("content", "") if isinstance(_val, dict) else str(_val)).strip()
        _ts      = (_val.get("updated_at", "") if isinstance(_val, dict) else "")
        with st.expander(f"✨ **{_label}**" + (f"  ·  *{_ts[:10]}*" if _ts else ""), expanded=False):
            st.markdown(_content or "—")

# ── Shared / personal section ─────────────────────────────────────────────────
st.markdown(
    "<div style='font:700 10px system-ui;letter-spacing:2px;text-transform:uppercase;"
    "color:rgba(17,24,39,.4);margin:22px 0 10px'>About You — Across All Languages</div>",
    unsafe_allow_html=True,
)
_render_expander(
    "personal_facts", "👤", "Personal Facts",
    "Facts you've shared about yourself — where you live, your job, people in your life. "
    "These carry into every language you learn.",
    _shared,
)

# ── Delete knowledge ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

if not st.session_state.get("_confirm_delete_profile"):
    if st.button("🗑 Delete all my learning data", use_container_width=True):
        st.session_state["_confirm_delete_profile"] = True
        st.rerun()
else:
    st.markdown("""
<div style='background:rgba(220,38,38,.07);border:1px solid rgba(220,38,38,.25);
            border-radius:12px;padding:14px 16px;margin-bottom:12px'>
  <div style='font:700 13px system-ui;color:#dc2626;margin-bottom:4px'>⚠ Are you sure?</div>
  <div style='font:400 12px/1.6 system-ui;color:rgba(17,24,39,.6)'>
    This will permanently delete everything SpeakPals knows about you —
    your learning history, personal context, and all tutor observations.
    Your account and lesson settings are not affected.
    This cannot be undone.
  </div>
</div>""", unsafe_allow_html=True)
    _col_yes, _col_no = st.columns(2)
    with _col_yes:
        if st.button("Yes, delete everything", use_container_width=True):
            if "sb_user_id" in st.session_state:
                delete_knowledge_profile(
                    st.session_state.sb_user_id,
                    st.session_state.sb_access_token,
                )
            st.session_state.pop("knowledge_profile", None)
            st.session_state.pop("_confirm_delete_profile", None)
            st.success("Your learning data has been deleted.")
            st.rerun()
    with _col_no:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("_confirm_delete_profile", None)
            st.rerun()

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Session ────────────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Session</div>", unsafe_allow_html=True)

if st.button("🔄 Clear lesson & restart", use_container_width=True):
    for k in LESSON_STATE_KEYS:
        st.session_state.pop(k, None)
    st.switch_page("pages/lesson.py")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Account ────────────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Account</div>", unsafe_allow_html=True)

_email = st.session_state.get("sb_email", "")
if not _email and "sb_access_token" in st.session_state:
    _email = get_user_email(st.session_state.sb_access_token)
    if _email:
        st.session_state["sb_email"] = _email

st.markdown(
    f"<div style='font:400 12px system-ui;color:rgba(17,24,39,.5);margin-bottom:10px'>"
    f"Signed in as <strong>{_email or '—'}</strong></div>",
    unsafe_allow_html=True
)
if not st.session_state.get("_show_change_pw"):
    if st.button("Change password", use_container_width=True):
        st.session_state["_show_change_pw"] = True
        st.rerun()
else:
    with st.form("change_pw_form"):
        new_pw     = st.text_input("New password", type="password", placeholder="At least 6 characters")
        confirm_pw = st.text_input("Confirm new password", type="password", placeholder="••••••••")
        _col_save, _col_cancel = st.columns(2)
        with _col_save:
            pw_submitted = st.form_submit_button("Update password", use_container_width=True)
        with _col_cancel:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

    if cancelled:
        st.session_state.pop("_show_change_pw", None)
        st.rerun()
    if pw_submitted:
        if len(new_pw) < 6:
            st.error("Password must be at least 6 characters.")
        elif new_pw != confirm_pw:
            st.error("Passwords don't match.")
        else:
            _err = update_password(
                st.session_state.sb_access_token,
                new_pw,
                st.session_state.get("sb_refresh_token", ""),
            )
            if _err:
                st.error(f"Could not update password: {_err}")
            else:
                st.session_state.pop("_show_change_pw", None)
                st.success("Password updated.")
                st.rerun()

if st.button("Sign out", use_container_width=True):
    from db import sign_out
    sign_out(st.session_state.get("sb_access_token", ""))
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.switch_page("pages/login.py")

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

col_save, col_home = st.columns(2)
with col_save:
    if st.button("Save", use_container_width=True):
        _save()
        st.success("Saved!")
with col_home:
    if st.button("🏠 Home", use_container_width=True):
        _save()
        st.switch_page("pages/home.py")

col_lesson, col_ob = st.columns(2)
with col_lesson:
    if st.button("← Back to Lesson", use_container_width=True):
        _save()
        st.switch_page("pages/lesson.py")
with col_ob:
    if st.button("👋 Redo Onboarding", use_container_width=True):
        _save()
        st.switch_page("pages/onboarding.py")
