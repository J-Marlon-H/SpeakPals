# SpeakPals — Restaurant Video Lesson
from __future__ import annotations
import pathlib, base64, re
import streamlit as st
import requests
from dotenv import load_dotenv
from db import require_auth, load_knowledge_profile, _secret
from pipeline import VOICES_BY_LANG, SETTINGS_DEFAULTS
from restaurant_helper import restaurant_player
from ws_proxy import start_in_thread, PROXY_PORT, scribe_token as _scribe_token
import streamlit.components.v1 as components

load_dotenv("keys.env")
require_auth()

CLAUDE_KEY = _secret("CLAUDE_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
IS_LOCAL   = pathlib.Path("keys.env").exists()

if IS_LOCAL:
    start_in_thread()

# ── Scene definitions ──────────────────────────────────────────────────────────

SCENES = [
    {
        "video":     "scene1.mp4",
        "user_turn": True,
        "da_line":   "Hej! Velkommen! Vil du sidde ved baren eller ved vinduet?",
        "en_prompt": "The waiter is asking: bar or window?",
        "da_target": "Ved vinduet",
        "hint":      "Try 'Ved vinduet tak' (by the window, please)",
    },
    {
        "video":     "scene2.mp4",
        "user_turn": True,
        "da_line":   "Velkommen! Her er menuen — vi har ramen og gyoza i dag. Hvad må det være?",
        "en_prompt": "Order the ramen from the menu.",
        "da_target": "Jeg vil gerne have ramen",
        "hint":      "Try 'Jeg vil gerne have ramen tak' (I'd like the ramen, please)",
    },
    {
        "video":     "scene3.mp4",
        "user_turn": False,
        "da_line":   "Ja, selvfølgelig, det ordner jeg med det samme.",
        "en_prompt": "",
        "hint":      "",
    },
    {
        "video":     "scene4.mp4",
        "user_turn": True,
        "da_line":   "Værsgo! Ramen til dig! God appetit!",
        "en_prompt": "The ramen arrived! Thank the waiter and ask for a fork.",
        "da_target": "Tak! Må jeg få en gaffel?",
        "hint":      "Try 'Tak! Må jeg få en gaffel?' (Thanks! May I have a fork?)",
    },
    {
        "video":     "scene5.mp4",
        "user_turn": False,
        "da_line":   "Selvfølgelig, jeg henter en gaffel til dig.",
        "en_prompt": "",
        "hint":      "",
    },
    {
        "video":     "scene6.mp4",
        "user_turn": False,
        "da_line":   "Jeg håber, at alt var lækkert, og vi ses forhåbentlig igen snart.",
        "en_prompt": "",
        "hint":      "",
    },
]

VIDEO_DIR = pathlib.Path("static/restaurant")

# ── Helpers ────────────────────────────────────────────────────────────────────

_HELP_RE = re.compile(
    r'\b(how|what|why|help|say|tell|don\'?t know|i need|can you|could you|what does|what is|how do|how to)\b',
    re.IGNORECASE,
)
_DANISH_CHARS = frozenset("æøåÆØÅ")
_PUNCT_RE = re.compile(r'[^\w\s]')

def _is_help_request(text: str) -> bool:
    """True when the utterance is an English help question rather than a Danish attempt."""
    if any(c in _DANISH_CHARS for c in text):
        return False
    return bool(_HELP_RE.search(text))

def _score_answer(attempt: str, target: str) -> bool:
    """True if at least half the target words appear in the attempt."""
    if not target:
        return True
    norm = lambda s: _PUNCT_RE.sub('', s.lower()).split()
    target_words = set(norm(target))
    if not target_words:
        return True
    attempt_words = set(norm(attempt))
    return len(target_words & attempt_words) / len(target_words) >= 0.5

def _tts_b64(text: str, voice_id: str) -> str | None:
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
                  "language_code": "en"},
            timeout=20,
        )
        r.raise_for_status()
        return base64.b64encode(r.content).decode()
    except Exception:
        return None

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Restaurant Lesson — SpeakPals", page_icon="🍜",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
  html,body{font-family:system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#ffffff!important}
  .block-container{padding:1rem 1.5rem!important;max-width:100%!important}
  div[data-testid="stVerticalBlock"]{gap:0.4rem!important}
  .stButton button{border-radius:10px!important;font-weight:600!important;font-size:13px!important}
  .stButton button[kind="primary"]{
    background:#0d9488!important;color:#fff!important;border:none!important}
  [data-testid="stVideo"]{border-radius:14px;overflow:hidden}
  video{border-radius:14px}
  /* Light sidebar */
  [data-testid="stSidebar"]{
    background:#f5f5f5!important;
    border-right:1px solid #e5e5e5!important;
    width:280px!important;min-width:280px!important}
  [data-testid="stSidebar"] *{color:#111827!important}
  [data-testid="stSidebar"] section{padding:0!important}
  [data-testid="stSidebar"] > div:first-child{
    padding-bottom:140px!important;overflow-y:auto!important}
  .st-key-rs_finish{
    position:fixed!important;bottom:58px!important;left:0!important;
    width:280px!important;padding:0 16px 6px!important;
    background:#f5f5f5!important;z-index:101!important}
  .st-key-rs_exit{
    position:fixed!important;bottom:0!important;left:0!important;
    width:280px!important;padding:0 16px 14px!important;
    background:#f5f5f5!important;border-top:1px solid #e5e5e5!important;
    z-index:100!important}
  @keyframes msgSlideIn{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:translateX(0)}}
</style>""", unsafe_allow_html=True)

# ── User profile ───────────────────────────────────────────────────────────────

sb_user_id = st.session_state.get("sb_user_id")
sb_token   = st.session_state.get("sb_access_token")
name       = st.session_state.get("s_name")    or "there"
level      = st.session_state.get("s_level")   or "A1"
bg_lang    = st.session_state.get("s_bg_lang") or "English"
lang_voices = VOICES_BY_LANG.get("Danish", {})
voice_label = st.session_state.get("s_voice_label", SETTINGS_DEFAULTS["s_voice_label"])
voice_id    = lang_voices.get(voice_label, next(iter(lang_voices.values()), ""))
knowledge_profile = st.session_state.get("knowledge_profile") or {}
if sb_user_id and sb_token and not knowledge_profile:
    knowledge_profile = load_knowledge_profile(sb_user_id, sb_token) or {}

# ── Session state ──────────────────────────────────────────────────────────────

_RS_KEYS = ["rs_phase","rs_scene_idx","rs_chat","rs_evaluation","rs_correct_log","rs_coaching_log","rs_last_chat_scene"]
for k, v in [
    ("rs_phase",           "start"),
    ("rs_scene_idx",       0),
    ("rs_chat",            []),
    ("rs_evaluation",      None),
    ("rs_correct_log",     []),
    ("rs_coaching_log",    []),
    ("rs_last_chat_scene", -1),
]:
    if k not in st.session_state:
        st.session_state[k] = v

rs_phase     = st.session_state.rs_phase
rs_scene_idx = st.session_state.rs_scene_idx

# Auto-append waiter's line to chat + correct_log when entering a new scene
if rs_phase in ("video", "mic", "feedback") and rs_scene_idx != st.session_state.rs_last_chat_scene:
    _da = SCENES[rs_scene_idx].get("da_line", "")
    if _da:
        st.session_state.rs_chat.append({"role": "waiter", "content": _da})
        st.session_state.rs_correct_log.append({"who": "character", "text": _da})
    st.session_state.rs_last_chat_scene = rs_scene_idx

# ── Shared component props (always rendered to keep mic permission alive) ──────

_scene_now = SCENES[rs_scene_idx] if rs_phase not in ("start", "complete") else {}
_mic_visible = (rs_phase == "mic")
_has_feedback_audio = (
    rs_phase == "feedback"
    and bool((st.session_state.rs_evaluation or {}).get("tts_b64"))
)

_comp_base: dict = {
    "visible":     _mic_visible,
    "watch_video": (rs_phase == "video"),
    "watch_audio": _has_feedback_audio,
    "scene_idx":   rs_scene_idx,
    "lang_code":   "da",
    "show":        rs_phase not in ("start", "complete"),
    "label":       "Tap to speak in Danish",
    "prompt":      _scene_now.get("en_prompt", ""),
    "key":         "restaurant_mic",   # same key → same iframe across reruns
    "height":      160,
    "default":     None,
}
if IS_LOCAL:
    _comp_base["proxy_port"] = PROXY_PORT
else:
    # Generate a fresh token only when entering mic phase; cache for that scene.
    # Calling scribe_token() on every rerun (including video phase) was wasteful
    # and risked rate-limiting or stale tokens by the time the mic was needed.
    if rs_phase == "mic":
        if not st.session_state.get("rs_stt_token"):
            st.session_state.rs_stt_token = _scribe_token(ELEVEN_KEY)
    else:
        st.session_state.rs_stt_token = None
    if st.session_state.get("rs_stt_token"):
        _comp_base["ws_token"] = st.session_state.rs_stt_token

# ── Sidebar: conversation + exit ───────────────────────────────────────────────

with st.sidebar:
    st.markdown("""<div style='padding:20px 16px 0'>
      <div style='font:800 16px/1.2 system-ui;color:#111827;letter-spacing:-.2px'>🍜 Lars · Tutor</div>
      <div style='font:500 11px system-ui;color:rgba(17,24,39,.45);margin-top:3px'>Restaurant Lesson</div>
      <div style='height:1px;background:#e5e5e5;margin:12px 0 8px'></div>
    </div>""", unsafe_allow_html=True)

    # ── Conversation log ──────────────────────────────────────────────────────
    _log = st.session_state.rs_chat
    if not _log:
        st.markdown(
            "<div style='padding:16px;font-size:12px;color:rgba(17,24,39,.45);font-style:italic'>"
            "Your conversation will appear here.</div>",
            unsafe_allow_html=True,
        )
    else:
        _last_i = len(_log) - 1
        _parts = []
        for _i, _msg in enumerate(_log):
            _txt  = _msg["content"].replace("<", "&lt;").replace(">", "&gt;")
            _anim = "animation:msgSlideIn .4s cubic-bezier(.34,1.56,.64,1) both;" if _i == _last_i else ""
            if _msg["role"] == "waiter":
                _parts.append(
                    f"<div style='padding:8px 12px 4px'>"
                    f"<div style='background:#ffffff;border:1px solid #e5e5e5;border-radius:12px 12px 12px 3px;"
                    f"padding:10px 12px;font-size:13px;line-height:1.5;"
                    f"color:#111827;word-break:break-word;{_anim}'>"
                    f"<span style='font:600 10px system-ui;color:#9ca3af;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>Waiter</span>"
                    f"<em>{_txt}</em></div></div>"
                )
            elif _msg["role"] == "user":
                _parts.append(
                    f"<div style='padding:4px 12px 8px'>"
                    f"<div style='background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.2);border-radius:12px 12px 3px 12px;"
                    f"padding:10px 12px;font-size:13px;line-height:1.5;"
                    f"color:#0f3d39;word-break:break-word;{_anim}'>"
                    f"<span style='font:600 10px system-ui;color:#0d9488;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>You</span>"
                    f"{_txt}</div></div>"
                )
        st.markdown("".join(_parts), unsafe_allow_html=True)
        components.html(f"""<script>
(function(){{
  function scroll(){{
    var s=window.parent.document.querySelector('[data-testid="stSidebar"]>div:first-child');
    if(s) s.scrollTop=s.scrollHeight;
  }}
  scroll(); setTimeout(scroll,120); setTimeout(scroll,400);
}})();
</script>""", height=0)

    st.markdown("<br>", unsafe_allow_html=True)
    if rs_phase not in ("start", "complete"):
        if st.button("Finish Lesson", key="rs_finish",
                     use_container_width=True, type="primary"):
            st.session_state["correct_log"]    = st.session_state.rs_correct_log
            st.session_state["coaching_log"]   = st.session_state.rs_coaching_log
            st.session_state["selected_scene"] = "restaurant_lesson"
            for k in _RS_KEYS:
                st.session_state.pop(k, None)
            st.switch_page("pages/feedback.py")
    if st.button("🏠 Exit lesson", key="rs_exit", use_container_width=True):
        for k in _RS_KEYS:
            st.session_state.pop(k, None)
        st.switch_page("pages/home.py")

# ── Main area ──────────────────────────────────────────────────────────────────

if True:

    # ── Start screen ───────────────────────────────────────────────────────────
    if rs_phase == "start":
        st.markdown("""
        <div style='text-align:center;padding:60px 20px 30px'>
          <div style='font-size:56px;margin-bottom:16px'>🍜</div>
          <div style='font:800 26px/1.2 system-ui;color:#111827;margin-bottom:10px'>
            At the Restaurant</div>
          <div style='font:400 14px/1.6 system-ui;color:rgba(17,24,39,.5);
            max-width:340px;margin:0 auto 32px'>
            A video lesson set in a ramen restaurant. Watch each scene and
            speak your Danish replies — Lars will guide you.</div>
        </div>""", unsafe_allow_html=True)
        _, btn_col, _ = st.columns([2, 2, 2])
        with btn_col:
            if st.button("▶  Start Lesson", use_container_width=True, type="primary"):
                st.session_state.rs_phase     = "video"
                st.session_state.rs_scene_idx = 0
                st.rerun()

    # ── Complete screen ────────────────────────────────────────────────────────
    elif rs_phase == "complete":
        st.markdown(f"""
        <div style='text-align:center;padding:50px 20px 24px'>
          <div style='font-size:56px;margin-bottom:16px'>🎉</div>
          <div style='font:800 26px/1.2 system-ui;color:#111827;margin-bottom:10px'>
            Lesson Complete!</div>
          <div style='font:400 14px/1.6 system-ui;color:rgba(17,24,39,.55);
            max-width:360px;margin:0 auto 24px'>
            Great work, {name}! You ordered ramen, asked for a fork, and got the
            bill — all in Danish. 🍜</div>
        </div>""", unsafe_allow_html=True)
        _, btn_col, _ = st.columns([2, 2, 2])
        with btn_col:
            if st.button("View Feedback →", use_container_width=True, type="primary"):
                st.session_state["correct_log"]    = st.session_state.rs_correct_log
                st.session_state["coaching_log"]   = st.session_state.rs_coaching_log
                st.session_state["selected_scene"] = "restaurant_lesson"
                for k in _RS_KEYS:
                    st.session_state.pop(k, None)
                st.switch_page("pages/feedback.py")

    # ── Video phase ────────────────────────────────────────────────────────────
    elif rs_phase == "video":
        scene = SCENES[rs_scene_idx]
        video_path = VIDEO_DIR / scene["video"]

        if video_path.exists():
            st.video(str(video_path), autoplay=True)
        else:
            st.warning(f"Video not found: {video_path}")

    # ── Mic phase ──────────────────────────────────────────────────────────────
    elif rs_phase == "mic":
        last_frame = VIDEO_DIR / f"scene{rs_scene_idx + 1}_last.jpg"
        if last_frame.exists():
            st.image(str(last_frame), use_container_width=True)

    # ── Feedback phase ─────────────────────────────────────────────────────────
    elif rs_phase == "feedback":
        ev      = st.session_state.rs_evaluation or {}
        tts_b64 = ev.get("tts_b64", "")

        # Play Lars' TTS audio; feedback text is in the sidebar conversation
        if tts_b64:
            st.markdown(
                f'<audio autoplay src="data:audio/mpeg;base64,{tts_b64}" style="display:none"></audio>',
                unsafe_allow_html=True,
            )
        # Show last frame for context while user listens to tip
        last_frame = VIDEO_DIR / f"scene{rs_scene_idx + 1}_last.jpg"
        if last_frame.exists():
            st.image(str(last_frame), use_container_width=True)

        # Show Continue button only as fallback when TTS is unavailable
        if not _has_feedback_audio:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            _, btn_col, _ = st.columns([1, 2, 1])
            with btn_col:
                next_idx = rs_scene_idx + 1
                is_last  = next_idx >= len(SCENES)
                label    = "Finish Lesson 🎉" if is_last else "Continue  →"
                if st.button(label, use_container_width=True, type="primary"):
                    if is_last:
                        st.session_state.rs_phase = "complete"
                    else:
                        st.session_state.rs_scene_idx = next_idx
                        st.session_state.rs_phase = "video"
                    st.rerun()

    # ── Mic component — mounted during lesson phases only (not start/complete) ───
    # Keeping the same key across video/mic/feedback preserves the JS context
    # and avoids re-prompting mic permission between scenes.
    _result = restaurant_player(**_comp_base) if rs_phase not in ("start", "complete") else None

    if _has_feedback_audio and isinstance(_result, dict) and _result.get("type") == "audio_ended":
        st.session_state.rs_evaluation = None
        st.session_state.rs_phase = "mic"
        st.rerun()

    if (rs_phase == "video" and isinstance(_result, dict)
            and _result.get("type") == "video_ended"
            and _result.get("scene_idx") == rs_scene_idx):
        _scene_ve = SCENES[rs_scene_idx]
        if _scene_ve["user_turn"]:
            st.session_state.rs_phase = "mic"
        else:
            _next = rs_scene_idx + 1
            if _next >= len(SCENES):
                st.session_state.rs_phase = "complete"
            else:
                st.session_state.rs_scene_idx = _next
                st.session_state.rs_phase = "video"
        st.rerun()

    if _mic_visible and isinstance(_result, dict) and _result.get("type") == "transcript":
        _txt = _result.get("text", "").strip()
        if _txt and _is_help_request(_txt):
            # English help question — give tip, stay on same scene
            _hint = _scene_now.get("hint", "")
            if _hint:
                _tip_audio = _tts_b64(_hint, voice_id)
                if _tip_audio:
                    st.session_state.rs_evaluation = {"tts_b64": _tip_audio}
                    st.session_state.rs_phase = "feedback"
                    st.rerun()
        else:
            # Danish attempt — score and log it, then advance
            if _txt:
                st.session_state.rs_chat.append({"role": "user", "content": _txt})
                _target = _scene_now.get("da_target", "")
                if _score_answer(_txt, _target):
                    st.session_state.rs_correct_log.append({"who": "student", "text": _txt})
                else:
                    st.session_state.rs_coaching_log.append({
                        "question":   _scene_now.get("da_line", ""),
                        "attempt":    _txt,
                        "correction": _scene_now.get("hint", f"Try: {_target}"),
                    })
            _next = rs_scene_idx + 1
            if _next >= len(SCENES):
                st.session_state.rs_phase = "complete"
            else:
                st.session_state.rs_scene_idx = _next
                st.session_state.rs_phase = "video"
            st.rerun()

    if _mic_visible and isinstance(_result, dict) and _result.get("type") == "ask_tip":
        _hint = _scene_now.get("hint", "")
        if _hint:
            _tip_audio = _tts_b64(_hint, voice_id)
            if _tip_audio:
                st.session_state.rs_evaluation = {"tts_b64": _tip_audio}
                st.session_state.rs_phase = "feedback"
                st.rerun()


