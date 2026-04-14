"""pages/onboarding.py — Welcome interview that builds the user knowledge profile."""
from __future__ import annotations
import hashlib
import pathlib
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from pipeline import (SETTINGS_DEFAULTS, character_tts_b64)
from tutor import Tutor
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

_OB_MAX_TURNS  = 18     # ~8-10 minutes of conversation

# ── Opening greeting ───────────────────────────────────────────────────────────
# Acknowledges what we already know from sign-up so the first question goes
# straight to motivation rather than re-asking basics.
_OPENER = (
    "Hi {name}! I'm your SpeakPals tutor — great to meet you. "
    "I can see you're learning {target_lang} starting from {level} level "
    "with {bg_lang} as your background, so I already have a head start. "
    "To make our sessions as useful as possible I'd love to learn a bit more about you. "
    "What's drawing you to {target_lang}?"
)

# ── System prompt ──────────────────────────────────────────────────────────────
_OB_SYSTEM = """\
You are a warm, genuinely curious language learning tutor meeting {name} for the first time.
Your only job right now is to LISTEN and build a rich picture of who they are — not to teach.

**LANGUAGE: English only. Never use {target_lang} or any other language.**

**RESPONSE LENGTH: One short warm reaction (max one sentence) + ONE question. \
Two sentences maximum. The student talks; you listen.**

## What you already know — do NOT ask about these again
- Name: {name}
- Learning: {target_lang}
- Self-reported level: {level}
- Background language: {bg_lang}

## Topics to explore — work through as many as feel natural, one at a time
Cover different angles. Do not circle back to a topic you've already touched.

1. **Motivation & personal story** — The specific "why" behind learning {target_lang}. \
   Push past generic answers ("I like the culture") to the real story.
2. **Real-life use situations** — Exact moments where they'll need {target_lang}: \
   a neighbourhood, a workplace, a partner's family dinner, a trip planned. Concrete details.
3. **People in their life** — Partner, friends, colleagues, family who speak {target_lang}? \
   Any relationships where the language matters?
4. **Previous learning attempts** — Have they tried before? What worked, what didn't? \
   Apps, classes, immersion, self-study?
5. **Where they get stuck** — What feels hardest — pronunciation, grammar, vocabulary, \
   confidence to speak? Any patterns they've noticed in themselves?
6. **Daily life & schedule** — When and how do they picture practising? Work schedule, \
   commute, lifestyle clues that shape how sessions should feel.
7. **Cultural interests** — Food, music, films, humour, history, travel — anything they \
   are drawn to in {target_lang} culture that lessons could tap into.
8. **Milestone goal** — What would make them feel proud? A specific sentence, a \
   conversation, a trip, a work meeting — a concrete milestone to aim for.
9. **Learning style** — Do they prefer structure or free conversation? Corrections \
   in the moment or after? What has felt enjoyable vs. frustrating in the past?

## Pacing rules
- ONE question per turn. Never bundle two questions into one turn.
- Brief warm reaction first, then your question.
- If an answer is vague, probe once with a specific follow-up before moving on.
- When you have enough on a topic, acknowledge it briefly and shift: \
  "Got it — really useful." then move to a fresh angle.
- Vary your openers. Do not repeat the same reaction phrase twice.

## Wrap-up — from turn {nudge_turn} onwards
Once you have covered at least 6–7 topics OR reached turn {nudge_turn}, start wrapping up:
- Ask: "Is there anything else you'd like me to know before we start — \
  anything that would help me tailor things for you?"
- If they say no, or give a very short answer, close warmly in 1–2 sentences \
  and say: "Feel free to press Finish Onboarding whenever you're ready."
- End that final message with this exact marker on its own line:
[ONBOARDING_COMPLETE]

Do NOT wait until the absolute maximum turns. If the student signals readiness earlier, \
wrap up sooner. The marker must appear in your last message.

## Current state
Exchange number: {turn_count} of maximum {max_turns}
You opened with: "{opener_text}"
"""


def _build_system(name, target_lang, level, bg_lang, turn_count, opener_text):
    return _OB_SYSTEM.format(
        name=name,
        target_lang=target_lang,
        level=level,
        bg_lang=bg_lang,
        opener_text=opener_text,
        turn_count=turn_count,
        nudge_turn=8,
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
    border:none!important;display:block!important;margin:0!important;
    z-index:1!important}
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

tutor = Tutor.from_session(st.session_state)

name        = tutor.name
level       = tutor.level
bg_lang     = tutor.bg_lang
target_lang = tutor.target_lang
model_id    = tutor.model_id

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


def _save_profile_now() -> None:
    """Build / update the knowledge profile from the current ob_log and persist it.
    Safe to call multiple times — skips if already saved or if no log exists.
    """
    if st.session_state.ob_profile_saved:
        return
    if not st.session_state.ob_log:
        return
    if "sb_user_id" not in st.session_state or not CLAUDE_KEY:
        return

    full_log = []
    if st.session_state.ob_opener_text:
        full_log.append({"who": "tutor", "text": st.session_state.ob_opener_text})
    full_log.extend(st.session_state.ob_log)

    current_profile = load_knowledge_profile(
        st.session_state.sb_user_id,
        st.session_state.sb_access_token,
    )

    import requests as _req
    _sess = _req.Session()
    _sess.verify = False

    updated = update_knowledge_profile(
        current_profile,
        name, level, target_lang, bg_lang,
        full_log, [],
        CLAUDE_KEY,
        model=model_id,
        http_session=_sess,
    )

    # Only mark as saved when Claude returned a real profile.
    # On any silent failure update_knowledge_profile returns current_profile ({}
    # for first session), so _profile_is_real will be False and we leave
    # ob_profile_saved=False — next button click or completion trigger will retry.
    _profile_is_real = any(
        isinstance(v, dict) and v.get("content", "").strip()
        for v in updated.values()
    )
    if not _profile_is_real:
        return

    save_knowledge_profile(
        st.session_state.sb_user_id,
        st.session_state.sb_access_token,
        updated,
    )
    st.session_state["knowledge_profile"] = updated
    st.session_state.ob_profile_saved = True

    _sync = _infer_settings(updated)
    if _sync:
        st.session_state.update(_sync)
        from db import upsert_profile
        upsert_profile(
            st.session_state.sb_user_id,
            st.session_state.sb_access_token,
            _sync,
        )


# ── Opener: generate TTS for Alex's opening greeting ──────────────────────────
# Triggered on the rerun after ob_started first becomes True.

if st.session_state.ob_started and not st.session_state.ob_opener_loaded:
    opener_text = _OPENER.format(name=name, target_lang=target_lang,
                                  level=level, bg_lang=bg_lang)
    st.session_state.ob_opener_text = opener_text

    if ELEVEN_KEY:
        b64 = character_tts_b64(opener_text, tutor.voice_id, ELEVEN_KEY, lang_code="")
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
        # Embed log length so Streamlit always treats this as new content and re-executes.
        components.html(f"""<script>
(function(){{
  var _len={len(log)};  // changes each rerun, forcing re-execution
  function scroll(){{
    var s=window.parent.document.querySelector('[data-testid="stSidebar"]>div:first-child');
    if(s) s.scrollTop=s.scrollHeight;
  }}
  scroll(); setTimeout(scroll,120); setTimeout(scroll,350);
}})();
</script>""", height=0)

    # Completion banner — no extra button; tutor already told the student to press Finish
    if st.session_state.ob_complete:
        st.markdown(
            "<div style='margin:10px 12px;padding:14px 16px;"
            "background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.3);"
            "border-radius:12px;font:500 12px Inter;color:#0d9488;line-height:1.5'>"
            "Great chat! Your profile has been saved. Press Finish Onboarding below whenever you're ready."
            "</div>",
            unsafe_allow_html=True,
        )

    # Error — dismissable so the student can simply try speaking again
    if st.session_state.ob_error:
        _ecol1, _ecol2 = st.columns([6, 1])
        with _ecol1:
            st.markdown(
                "<div style='margin:8px 0;padding:8px 10px;"
                "background:rgba(220,38,38,.08);border-radius:8px;"
                "color:#dc2626;font-size:11px'>"
                "⚠ Something went wrong — please try speaking again."
                "</div>",
                unsafe_allow_html=True,
            )
        with _ecol2:
            if st.button("✕", key="btn_clear_error", help="Dismiss"):
                st.session_state.ob_error = None
                st.rerun()

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
        components.html("<script>try{localStorage.removeItem('sp_mic_tip_ok')}catch(e){}</script>", height=0)
        st.rerun()

    # Finish onboarding — pinned to bottom
    if st.button("✅ Finish Onboarding", key="btn_ob_home", use_container_width=True):
        # Profile is saved during [ONBOARDING_COMPLETE] processing (primary path).
        # If not yet saved (user left early or completion save failed), do a best-effort
        # background save so we never block navigation on an API call.
        if not st.session_state.ob_profile_saved and st.session_state.ob_log and CLAUDE_KEY \
                and "sb_user_id" in st.session_state:
            import threading as _th
            _snap = dict(
                current_profile=load_knowledge_profile(
                    st.session_state.sb_user_id, st.session_state.sb_access_token),
                name=name, level=level, target_lang=target_lang, bg_lang=bg_lang,
                full_log=(
                    [{"who": "tutor", "text": st.session_state.ob_opener_text}]
                    if st.session_state.ob_opener_text else []
                ) + list(st.session_state.ob_log),
                user_id=st.session_state.sb_user_id,
                token=st.session_state.sb_access_token,
                claude_key=CLAUDE_KEY,
                model_id=model_id,
            )
            def _bg_save(snap=_snap):
                import requests as _req
                _sess = _req.Session(); _sess.verify = False
                updated = update_knowledge_profile(
                    snap["current_profile"], snap["name"], snap["level"],
                    snap["target_lang"], snap["bg_lang"],
                    snap["full_log"], [], snap["claude_key"],
                    model=snap["model_id"], http_session=_sess,
                )
                _real = any(
                    isinstance(v, dict) and v.get("content", "").strip()
                    for v in updated.values()
                )
                if _real:
                    save_knowledge_profile(snap["user_id"], snap["token"], updated)
            _th.Thread(target=_bg_save, daemon=True).start()

        if st.session_state.get("is_new_user"):
            st.switch_page("pages/telegram_settings.py")
        else:
            st.switch_page("pages/home.py")

# ── VAD component ──────────────────────────────────────────────────────────────

mic_props = dict(
    lang            = "en",          # onboarding is always English
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

# ── Mic tip overlay — shown before first speech, dismissed via localStorage ────
if not st.session_state.ob_started:
    st.markdown("""
<div id="mic-tip-wrap" style="
    position:fixed;inset:0;z-index:10000;pointer-events:none;
    display:flex;align-items:flex-end;justify-content:center;
    padding-bottom:136px;padding-left:320px;
">
  <div id="mic-tip" style="
    pointer-events:auto;
    background:#111827;color:#fff;
    border-radius:14px;padding:14px 18px 12px;
    font:500 13px/1.5 'Inter',sans-serif;
    max-width:216px;text-align:center;
    box-shadow:0 8px 32px rgba(0,0,0,.35);
    position:relative;
  ">
    <div style="font:700 14px 'Inter';margin-bottom:6px">🎙️ Using the mic</div>
    <div style="font:400 12px/1.6 'Inter';opacity:.9">
      Press the mic button to unmute,<br>then start speaking.<br>
      It turns <span style="color:#38bdf8;font-weight:600">blue</span> while it's listening.
    </div>
    <button onclick="
      document.getElementById('mic-tip-wrap').style.display='none';
      try{localStorage.setItem('sp_mic_tip_ok','1')}catch(e){}
    " style="
      margin-top:12px;
      background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.28);
      color:#fff;border-radius:8px;padding:5px 0;
      font:600 12px 'Inter';cursor:pointer;width:100%;
    ">Got it ✓</button>
    <div style="
      position:absolute;bottom:-9px;left:50%;transform:translateX(-50%);
      width:0;height:0;
      border-left:9px solid transparent;border-right:9px solid transparent;
      border-top:9px solid #111827;
    "></div>
  </div>
</div>
<script>
(function(){
  try{if(localStorage.getItem('sp_mic_tip_ok')){
    var w=document.getElementById('mic-tip-wrap');if(w)w.style.display='none';
  }}catch(e){}
})();
</script>""", unsafe_allow_html=True)

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

        for raw_text, chunk_b64, _ in tutor.stream(
                system,
                student_text,
                st.session_state.ob_chat,
                CLAUDE_KEY,
                ELEVEN_KEY,
                use_structured=False):
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
        if onboarding_done:
            st.session_state.ob_complete = True
            _save_profile_now()   # idempotent — marks ob_profile_saved itself

    except Exception as e:
        st.session_state.ob_thinking    = False
        st.session_state.ob_error       = str(e)
        st.session_state.ob_last_chunks = None

    st.rerun()
