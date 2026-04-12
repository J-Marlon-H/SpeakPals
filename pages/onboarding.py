"""pages/onboarding.py — Welcome interview that builds the user knowledge profile."""
from __future__ import annotations
import hashlib
import pathlib
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from pipeline import (run_pipeline_stream, MODELS, SETTINGS_DEFAULTS, character_tts_b64)
from db import (require_auth, load_knowledge_profile, save_knowledge_profile,
                delete_knowledge_profile, _secret)
from profile import update_knowledge_profile
from vad_helper import mic

load_dotenv("keys.env")


def _infer_settings(profile: dict) -> dict:
    """Extract user settings that can be reliably inferred from the knowledge profile."""
    settings = {}
    # Level: look for explicit CEFR codes in language_level content
    level_text = (profile.get("language_level") or {}).get("content", "").upper()
    for lvl in ("A1", "A2", "B1", "B2"):
        if lvl in level_text:
            settings["s_level"] = lvl
            break
    # Target language: look for known languages in motivation / context
    tl_map = {
        "danish":                 "Danish",
        "portuguese":             "Portuguese (Brazilian)",
        "portuguese (brazilian)": "Portuguese (Brazilian)",
    }
    combined = " ".join([
        (profile.get("learning_motivation") or {}).get("content", ""),
        (profile.get("personal_use_context") or {}).get("content", ""),
        (profile.get("language_level") or {}).get("content", ""),
    ]).lower()
    for kw, lang in tl_map.items():
        if kw in combined:
            settings["s_language"] = lang
            break
    # Background language
    bg_map = {
        "german":  "German",
        "spanish": "Spanish",
        "french":  "French",
        "dutch":   "Dutch",
        "swedish": "Swedish",
        "english": "English",
    }
    for kw, lang in bg_map.items():
        if f"native {kw}" in combined or f"speaks {kw}" in combined or \
           f"background: {kw}" in combined or f"background language: {kw}" in combined or \
           f"first language is {kw}" in combined or f"mother tongue is {kw}" in combined:
            settings["s_bg_lang"] = lang
            break
    return settings


CLAUDE_KEY = _secret("CLAUDE_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")

# ── Voice & language config ────────────────────────────────────────────────────
# Onboarding tutor voice — warm female, ElevenLabs multilingual model
_OB_VOICE_ID   = "4RklGmuxoAskAbGXplXN"
_OB_TTS_LANG   = "en"   # interview always in English
_OB_MAX_TURNS  = 18     # ~8-10 minutes of conversation

# ── Opening greeting ───────────────────────────────────────────────────────────
_OPENER = (
    "Hi {name}! I'm your SpeakPals tutor. "
    "What language are you hoping to learn?"
)

# ── System prompt ──────────────────────────────────────────────────────────────
_OB_SYSTEM = """\
You are a warm, curious, and deeply empathetic language learning tutor. \
You are meeting {name} for the very first time and having a friendly 8–12 minute \
getting-to-know-you conversation.

**You must respond ONLY in English. Never switch to another language.**

Your mission is to learn as much as possible about this person through natural, \
flowing conversation so you can become the best possible language and culture \
learning companion for them. Explore these areas — but do so organically, not like \
a checklist:

1. **Language level** — What do they already know? Grammar patterns, vocabulary, \
   phrases they are comfortable with? How would they rate themselves?
2. **Learning motivation** — Why are they learning the language? What personal reasons, \
   goals, or dreams drive them? Ask for stories and specific examples.
3. **Personal use context** — Where will they actually use the language in real life? \
   Specific situations: at work, with family, travelling, living abroad, hobbies?
4. **Patterns and challenges** — Mistakes or difficulties they are already aware of? \
   Things they have tried before? What worked, what did not?
5. **Personal and cultural connections** — Connections to the language or culture? \
   Partner, family, friends, travel plans, work context — anything that makes the \
   language personally meaningful?

Conversation guidelines:
- Be genuinely warm, curious, and encouraging — this is their welcome to the app
- Dig deep with follow-up questions when something interesting comes up
- Ask only ONE question at a time — never overwhelm with multiple questions
- Reflect back what you hear to show you are truly listening
- If they give a short answer, gently probe for more depth
- Share brief encouraging reactions before moving to the next question

Context about this learner:
- Name: {name}
- Language they are trying to learn: {target_lang}
- Their current level: {level}
- Their background language: {bg_lang}
- You have already greeted them and opened the conversation with: "{opener_text}"
- This is exchange number {turn_count} of approximately {max_turns}

After approximately {max_turns} exchanges, wrap up warmly. Briefly summarise the most \
interesting things you have learned about them and tell them you are excited to start \
practising together. End your very last message with this exact marker on its own line:
[ONBOARDING_COMPLETE]
"""


def _build_system(name, target_lang, level, bg_lang, turn_count, opener_text):
    return _OB_SYSTEM.format(
        name=name,
        target_lang=target_lang,
        level=level,
        bg_lang=bg_lang,
        opener_text=opener_text,
        turn_count=turn_count,
        max_turns=_OB_MAX_TURNS,
    )


# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Welcome — SpeakPals",
    page_icon="👋",
    layout="wide",
    initial_sidebar_state="expanded",
)
require_auth()

components.html("""<script>
Object.keys(localStorage).forEach(function(k){
  if(k.indexOf('Sidebar')>-1) localStorage.removeItem(k);
});
</script>""", height=0)

st.markdown("""<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html,body{font-family:'Inter',sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important;height:0!important;min-height:0!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#ffffff!important}

  /* Sidebar */
  [data-testid="stSidebar"]{
    background:#f5f5f5!important;border-right:1px solid #e5e5e5!important;
    width:320px!important;min-width:320px!important;color:#111827!important}
  [data-testid="stSidebar"] *{color:#111827!important}
  [data-testid="stSidebar"] section{padding:0!important}
  [data-testid="stSidebar"] .stButton button{
    background:rgba(13,148,136,.1)!important;color:#0d9488!important;
    border:1px solid rgba(13,148,136,.25)!important;border-radius:8px!important;
    font-size:13px!important}
  [data-testid="stSidebar"] .stButton button:hover{background:rgba(13,148,136,.2)!important}

  /* Main area — VAD component fills full area */
  .stMainBlockContainer,.block-container{padding:0!important;margin:0!important;max-width:100%!important}
  [data-testid="stVerticalBlock"]{gap:0!important;padding:0!important}
  section[data-testid="stMain"]{padding:0!important;overflow:hidden}
  [data-testid="stCustomComponentV1"]{padding:0!important;margin:0!important}
  [data-testid="stCustomComponentV1"]{height:100vh!important;overflow:hidden!important}
  [data-testid="stCustomComponentV1"] iframe{
    position:fixed!important;top:0!important;left:320px!important;
    height:100vh!important;width:calc(100vw - 320px)!important;
    border:none!important;display:block!important;margin:0!important}
  [data-stale="true"],[data-stale="true"] *{opacity:1!important;transition:none!important}

  /* Chat animations */
  @keyframes msgSlideIn{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:translateX(0)}}

  /* Sidebar scroll + pinned buttons */
  [data-testid="stSidebar"] > div:first-child{
    padding-bottom:140px!important;overflow-y:auto!important}
  [data-testid="stSidebar"] [data-testid="stVerticalBlock"]{
    gap:2px!important;overflow:visible!important}

  /* Pin Home button to bottom */
  [data-testid="stSidebar"] .st-key-btn_ob_home{
    position:fixed!important;bottom:0!important;left:0!important;
    width:320px!important;padding:6px 16px 12px!important;
    background:#f5f5f5!important;border-top:1px solid #e5e5e5!important;
    z-index:100!important}

  /* Pin Reset button just above Home */
  [data-testid="stSidebar"] .st-key-btn_reset_knowledge{
    position:fixed!important;bottom:62px!important;left:0!important;
    width:320px!important;padding:6px 16px 4px!important;
    background:#f5f5f5!important;z-index:99!important}
  [data-testid="stSidebar"] .st-key-btn_reset_knowledge button{
    background:rgba(220,38,38,.07)!important;
    border:1px solid rgba(220,38,38,.2)!important;
    color:#dc2626!important}
  [data-testid="stSidebar"] .st-key-btn_reset_knowledge button:hover{
    background:rgba(220,38,38,.14)!important}

  /* Language selectbox */
  [data-testid="stSidebar"] .stSelectbox > div > div{
    background:#ffffff!important;color:#111827!important;
    border:1px solid #e5e5e5!important;border-radius:10px!important;
    font-size:13px!important}
</style>""", unsafe_allow_html=True)

# ── User settings ──────────────────────────────────────────────────────────────

name        = st.session_state.get("s_name",        SETTINGS_DEFAULTS["s_name"])
level       = st.session_state.get("s_level",       SETTINGS_DEFAULTS["s_level"])
bg_lang     = st.session_state.get("s_bg_lang",     SETTINGS_DEFAULTS["s_bg_lang"])
target_lang = st.session_state.get("s_language",    SETTINGS_DEFAULTS["s_language"])
model_label = st.session_state.get("s_model_label", SETTINGS_DEFAULTS["s_model_label"])
model_id    = MODELS[model_label]

# ── Session state ──────────────────────────────────────────────────────────────

for k, v in [
    ("ob_chat",           []),
    ("ob_log",            []),
    ("ob_turn_count",     0),
    ("ob_complete",       False),
    ("ob_pending",        None),
    ("ob_thinking",       False),
    ("ob_last_chunks",    None),
    ("ob_tutor_play_seq", 0),
    ("ob_stop_seq",       0),
    ("ob_last_id",        None),
    ("ob_started",        False),
    ("ob_opener_loaded",  False),
    ("ob_opener_text",    ""),
    ("ob_profile_saved",  False),
    ("ob_error",          None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Proxy / local dev ──────────────────────────────────────────────────────────

IS_LOCAL = pathlib.Path("keys.env").exists()

from ws_proxy import start_in_thread, PROXY_PORT, scribe_token as _scribe_token

@st.cache_resource
def _start_proxy():
    if IS_LOCAL:
        return start_in_thread()
    return None

_start_proxy()

# ── Opener: generate TTS for Alex's opening greeting ──────────────────────────
# Triggered on the rerun after ob_started first becomes True.

if st.session_state.ob_started and not st.session_state.ob_opener_loaded:
    opener_text = _OPENER.format(name=name)
    st.session_state.ob_opener_text = opener_text

    if ELEVEN_KEY:
        b64 = character_tts_b64(opener_text, _OB_VOICE_ID, ELEVEN_KEY, lang_code=_OB_TTS_LANG)
        if b64:
            st.session_state.ob_last_chunks    = [b64]
            st.session_state.ob_tutor_play_seq += 1

    # Add opener to display log only — ob_chat starts with the user's first actual message
    if not any(e["who"] == "tutor" and e["text"] == opener_text for e in st.session_state.ob_log):
        st.session_state.ob_log.append({"who": "tutor", "text": opener_text})

    st.session_state.ob_opener_loaded = True

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    # Header
    st.markdown(
        "<div style='padding:16px 16px 8px'>"
        "<div style='font:800 18px/1.2 Inter,sans-serif;color:#111827;letter-spacing:-.3px'>"
        "Welcome to SpeakPals 👋</div>"
        f"<div style='font:500 12px Inter;color:rgba(17,24,39,.5);margin-top:4px'>"
        f"Getting to know you, {name}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,rgba(13,148,136,.3),"
        "transparent);margin:4px 12px 12px'></div>",
        unsafe_allow_html=True,
    )

    # Chat log
    log = st.session_state.ob_log
    if not st.session_state.ob_started:
        st.markdown(
            "<div style='padding:12px 16px;font-size:12px;color:rgba(17,24,39,.45);font-style:italic'>"
            "Your tutor will start in a moment…"
            "</div>",
            unsafe_allow_html=True,
        )
    elif not log:
        st.markdown(
            "<div style='padding:16px;font-size:12px;color:rgba(17,24,39,.45);font-style:italic'>"
            "Loading your welcome message…</div>",
            unsafe_allow_html=True,
        )
    else:
        last_i = len(log) - 1
        parts  = []
        for i, entry in enumerate(log):
            txt  = entry["text"].replace("<", "&lt;").replace(">", "&gt;")
            anim = "animation:msgSlideIn .4s cubic-bezier(.34,1.56,.64,1) both;" if i == last_i else ""
            if entry["who"] == "tutor":
                parts.append(
                    f"<div style='padding:8px 12px 4px'>"
                    f"<div style='background:#ffffff;border:1px solid #e5e5e5;"
                    f"border-radius:12px 12px 12px 3px;padding:10px 12px;font-size:13px;"
                    f"line-height:1.5;color:#111827;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Inter;color:#9ca3af;display:block;"
                    f"margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>Tutor</span>"
                    f"{txt}</div></div>"
                )
            else:
                parts.append(
                    f"<div style='padding:4px 12px 8px'>"
                    f"<div style='background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.2);"
                    f"border-radius:12px 12px 3px 12px;padding:10px 12px;font-size:13px;"
                    f"line-height:1.5;color:#0f3d39;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Inter;color:#0d9488;display:block;"
                    f"margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>You</span>"
                    f"{txt}</div></div>"
                )
        st.markdown("".join(parts), unsafe_allow_html=True)

    # Completion banner
    if st.session_state.ob_complete:
        _is_new = st.session_state.get("is_new_user", False)
        st.markdown(
            "<div style='margin:10px 12px;padding:14px 16px;"
            "background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.3);"
            "border-radius:12px;font:500 12px Inter;color:#0d9488;line-height:1.5'>"
            + ("Great chat! Your profile is saved. Let's finish setting up your account."
               if _is_new else
               "Great chat! Your profile has been saved. Ready to start learning!")
            + "</div>",
            unsafe_allow_html=True,
        )
        _btn_label = "⚙ Go to Settings →" if _is_new else "🚀 Start Learning →"
        _btn_dest  = "pages/account.py"   if _is_new else "pages/home.py"
        if st.button(_btn_label, type="primary", use_container_width=True):
            st.switch_page(_btn_dest)

    # Error
    if st.session_state.ob_error:
        st.markdown(
            f"<div style='margin:8px 12px;padding:8px 10px;"
            f"background:rgba(220,38,38,.08);border-radius:8px;"
            f"color:#dc2626;font-size:11px;word-break:break-word'>"
            f"⚠ {st.session_state.ob_error}</div>",
            unsafe_allow_html=True,
        )

    # Reset all knowledge — pinned above Finish
    if st.button("🗑 Reset all knowledge", key="btn_reset_knowledge", use_container_width=True):
        if "sb_user_id" in st.session_state:
            delete_knowledge_profile(
                st.session_state.sb_user_id,
                st.session_state.sb_access_token,
            )
        for k in ["ob_chat", "ob_log", "ob_turn_count", "ob_complete", "ob_pending",
                   "ob_thinking", "ob_last_chunks", "ob_tutor_play_seq", "ob_last_id",
                   "ob_started", "ob_opener_loaded", "ob_opener_text", "ob_profile_saved",
                   "ob_error", "knowledge_profile", "onboarding_checked"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Finish onboarding — pinned to bottom
    if st.button("✅ Finish Onboarding", key="btn_ob_home", use_container_width=True):
        if st.session_state.get("is_new_user"):
            st.switch_page("pages/telegram_settings.py")
        else:
            st.switch_page("pages/home.py")

# ── VAD component ──────────────────────────────────────────────────────────────

mic_props = dict(
    lang            = "",           # auto-detect STT — user may switch languages freely
    scene_src       = "",           # no scene background; avatar fills the canvas
    scene_caption   = "Welcome",
    avatar_chunks   = st.session_state.ob_last_chunks or [],
    avatar_thinking = st.session_state.ob_thinking,
    char_audio      = [],
    tutor_play_seq  = st.session_state.ob_tutor_play_seq,
    char_play_seq   = 0,
    replay_char_seq = 0,
    stop_audio_seq  = st.session_state.ob_stop_seq,
    tutor_text      = "",
    progress_current= 0,
    progress_total  = 0,
    ob_mode         = True,         # light background + centered large avatar
    default         = None,
    height          = 900,
)

if IS_LOCAL:
    mic_props["proxy_port"] = PROXY_PORT
else:
    ws_token = _scribe_token(ELEVEN_KEY)
    if ws_token:
        mic_props["ws_token"] = ws_token

transcript_raw = mic(key="ob_mic", **mic_props)

# ── Handle VAD output ──────────────────────────────────────────────────────────

if transcript_raw == "__started__":
    if not st.session_state.ob_started:
        st.session_state.ob_started = True
        st.rerun()

elif (transcript_raw
      and isinstance(transcript_raw, str)
      and transcript_raw.strip()
      and transcript_raw not in ("__scene_select__",)):
    h = hashlib.md5(transcript_raw.encode()).hexdigest()
    if h != st.session_state.ob_last_id and not st.session_state.ob_complete:
        st.session_state.ob_last_id  = h
        st.session_state.ob_pending  = transcript_raw.strip()
        st.session_state.ob_thinking = True
        st.rerun()

# ── Pipeline ───────────────────────────────────────────────────────────────────

student_text = st.session_state.get("ob_pending")
if student_text and not st.session_state.ob_complete:
    st.session_state.ob_pending = None
    st.session_state.ob_error   = None

    system = _build_system(
        name, target_lang, level, bg_lang,
        st.session_state.ob_turn_count,
        st.session_state.ob_opener_text,
    )

    try:
        all_chunks = []
        raw_text   = ""

        for raw_text, chunk_b64, _ in run_pipeline_stream(
                system,
                student_text,
                st.session_state.ob_chat,
                _OB_VOICE_ID,
                CLAUDE_KEY,
                ELEVEN_KEY,
                model=model_id,
                use_structured=False,
                lang_code=_OB_TTS_LANG):
            if chunk_b64:
                all_chunks.append(chunk_b64)

        # Detect completion marker
        onboarding_done = "[ONBOARDING_COMPLETE]" in raw_text
        tutor_text      = raw_text.replace("[ONBOARDING_COMPLETE]", "").strip()

        # Update chat history (alternating roles for Claude context)
        st.session_state.ob_chat.extend([
            {"role": "user",      "content": student_text},
            {"role": "assistant", "content": tutor_text},
        ])

        # Update display log
        st.session_state.ob_log.append({"who": "student", "text": student_text})
        if tutor_text:
            st.session_state.ob_log.append({"who": "tutor", "text": tutor_text})

        st.session_state.ob_turn_count += 1
        st.session_state.ob_thinking    = False

        # Play tutor audio
        if all_chunks:
            st.session_state.ob_last_chunks    = all_chunks
            st.session_state.ob_tutor_play_seq += 1

        # ── Handle completion ──────────────────────────────────────────────────
        if onboarding_done and not st.session_state.ob_profile_saved:
            st.session_state.ob_complete     = True
            st.session_state.ob_profile_saved = True

            if "sb_user_id" in st.session_state and CLAUDE_KEY:
                # Build full log including the opener for the profile update
                full_log = []
                if st.session_state.ob_opener_text:
                    full_log.append({"who": "tutor", "text": st.session_state.ob_opener_text})
                full_log.extend(st.session_state.ob_log)

                current_profile = load_knowledge_profile(
                    st.session_state.sb_user_id,
                    st.session_state.sb_access_token,
                )
                updated = update_knowledge_profile(
                    current_profile,
                    name, level, target_lang, bg_lang,
                    full_log, [],   # no error log for onboarding
                    CLAUDE_KEY,
                    model=model_id,
                )
                save_knowledge_profile(
                    st.session_state.sb_user_id,
                    st.session_state.sb_access_token,
                    updated,
                )
                st.session_state["knowledge_profile"] = updated

                # Sync inferred settings back to session state + Supabase profile
                _sync = _infer_settings(updated)
                if _sync:
                    st.session_state.update(_sync)
                    from db import upsert_profile
                    upsert_profile(
                        st.session_state.sb_user_id,
                        st.session_state.sb_access_token,
                        _sync,
                    )

    except Exception as e:
        st.session_state.ob_thinking    = False
        st.session_state.ob_error       = str(e)
        st.session_state.ob_last_chunks = None

    st.rerun()
