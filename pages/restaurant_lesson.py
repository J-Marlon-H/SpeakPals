# SpeakPals — Restaurant Video Lesson
from __future__ import annotations
import pathlib, json, base64
import streamlit as st
import requests
from dotenv import load_dotenv
from db import require_auth, load_knowledge_profile, _secret
from pipeline import VOICES_BY_LANG, SETTINGS_DEFAULTS
from restaurant_helper import restaurant_player
from ws_proxy import start_in_thread, PROXY_PORT, scribe_token as _scribe_token

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
        "video":       "scene1.mp4",
        "user_turn":   True,
        "en_prompt":   "The waiter is asking: bar or window?",
        "da_target":   "Ved vinduet",
        "hint":        "Try 'Ved vinduet tak' (by the window, please)",
    },
    {
        "video":       "scene2.mp4",
        "user_turn":   True,
        "en_prompt":   "Order the ramen from the menu.",
        "da_target":   "Jeg vil gerne have ramen",
        "hint":        "Try 'Jeg vil gerne have ramen tak' (I'd like the ramen, please)",
    },
    {
        "video":       "scene3.mp4",
        "user_turn":   False,
        "en_prompt":   "",
        "hint":        "",
    },
    {
        "video":       "scene4.mp4",
        "user_turn":   True,
        "en_prompt":   "The ramen arrived! Thank the waiter and ask for a fork.",
        "da_target":   "Tak! Må jeg få en gaffel?",
        "hint":        "Try 'Tak! Må jeg få en gaffel?' (Thanks! May I have a fork?)",
    },
    {
        "video":       "scene5.mp4",
        "user_turn":   False,
        "en_prompt":   "",
        "hint":        "",
    },
    {
        "video":       "scene6.mp4",
        "user_turn":   False,
        "en_prompt":   "",
        "hint":        "",
    },
]

VIDEO_DIR = pathlib.Path("static/restaurant")

# ── Helpers ────────────────────────────────────────────────────────────────────

def _claude_evaluate(user_text: str, scene: dict, history: list,
                     knowledge_profile: dict, name: str, level: str, bg_lang: str) -> str:
    system = (
        f"You are Lars, a warm Danish tutor. The student ({name}, level {level}, "
        f"native language: {bg_lang}) is doing a restaurant role-play lesson. "
        f"They were asked to say something like: '{scene['da_target']}'\n\n"
        f"Reply in ONE short sentence only. "
        f"If correct or close: praise briefly. "
        f"If wrong or no response: say the correct Danish phrase naturally and encouragingly. "
        f"Plain text only — no markdown, no JSON."
    )
    if knowledge_profile:
        system += f"\n\nWhat you know about this student: {json.dumps(knowledge_profile)}"
    messages = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    messages.append({"role": "user", "content": user_text or "(no response)"})
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 80,
              "temperature": 0.6, "system": system, "messages": messages},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()

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
    padding-bottom:72px!important;overflow-y:auto!important}
  .st-key-rs_exit{
    position:fixed!important;bottom:0!important;left:0!important;
    width:280px!important;padding:10px 16px 14px!important;
    background:#f5f5f5!important;border-top:1px solid #e5e5e5!important;
    z-index:100!important}
  .chat-msg{padding:8px 12px;border-radius:10px;margin-bottom:5px;font-size:12px;line-height:1.5}
  .chat-user{background:rgba(13,148,136,.1);color:#0f3d39;text-align:right;
    border:1px solid rgba(13,148,136,.2)}
  .chat-tutor{background:rgba(245,158,11,.08);color:#78350f;
    border:1px solid rgba(245,158,11,.25)}
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

_RS_KEYS = ["rs_phase","rs_scene_idx","rs_chat","rs_evaluation","rs_last_eval_scene"]
for k, v in [
    ("rs_phase",          "start"),
    ("rs_scene_idx",      0),
    ("rs_chat",           []),
    ("rs_evaluation",     None),
    ("rs_last_eval_scene",-1),
]:
    if k not in st.session_state:
        st.session_state[k] = v

rs_phase     = st.session_state.rs_phase
rs_scene_idx = st.session_state.rs_scene_idx

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
    "label":       "Tap to speak in Danish",
    "hint":        _scene_now.get("hint", ""),
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
      <div style='height:1px;background:#e5e5e5;margin:12px 0 4px'></div>
    </div>""", unsafe_allow_html=True)

    if rs_phase == "mic" and _scene_now.get("en_prompt"):
        st.markdown(
            f"<div style='margin:8px 12px 0;padding:10px 12px;"
            f"font:400 12px/1.5 system-ui;color:#374151;"
            f"background:#fff;border-left:2px solid rgba(13,148,136,.6);"
            f"border-radius:0 8px 8px 0'>{_scene_now['en_prompt']}</div>",
            unsafe_allow_html=True,
        )
    if rs_phase == "mic" and _scene_now.get("hint"):
        _hint = _scene_now["hint"]
        st.markdown(
            f"<div style='margin:6px 12px 0;padding:8px 10px;"
            f"font:12px system-ui;color:#92400e;"
            f"background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);"
            f"border-radius:8px'>💡 {_hint}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    if st.session_state.rs_chat:
        for msg in st.session_state.rs_chat:
            if msg["role"] == "user":
                st.markdown(f"<div class='chat-msg chat-user'>🧑 {msg['content']}</div>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-msg chat-tutor'>💡 {msg['content']}</div>",
                            unsafe_allow_html=True)
    else:
        st.markdown("""<div style='font:400 12px system-ui;color:rgba(17,24,39,.35);
          margin:8px 12px'>Your conversation will appear here.</div>""",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
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
            if st.button("← Back to Home", use_container_width=True, type="primary"):
                for k in _RS_KEYS:
                    st.session_state.pop(k, None)
                st.switch_page("pages/home.py")

    # ── Video phase ────────────────────────────────────────────────────────────
    elif rs_phase == "video":
        scene = SCENES[rs_scene_idx]
        video_path = VIDEO_DIR / scene["video"]

        if video_path.exists():
            st.video(str(video_path), autoplay=True)
        else:
            st.warning(f"Video not found: {video_path}")

        if scene.get("en_prompt"):
            st.markdown(
                f"<div style='font:13px/1.5 system-ui;color:rgba(17,24,39,.55);"
                f"margin-top:8px;text-align:center'>{scene['en_prompt']}</div>",
                unsafe_allow_html=True,
            )

    # ── Mic phase ──────────────────────────────────────────────────────────────
    elif rs_phase == "mic":
        scene = SCENES[rs_scene_idx]
        video_path = VIDEO_DIR / scene["video"]

        if video_path.exists():
            st.video(str(video_path), autoplay=False)

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
        # Show scene video for context while user listens to feedback
        video_path = VIDEO_DIR / SCENES[rs_scene_idx]["video"]
        if video_path.exists():
            st.video(str(video_path), autoplay=False)

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
        _next_a = rs_scene_idx + 1
        if _next_a >= len(SCENES):
            st.session_state.rs_phase = "complete"
        else:
            st.session_state.rs_scene_idx = _next_a
            st.session_state.rs_phase = "video"
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

    def _handle_eval(scene_idx, user_text):
        if scene_idx == st.session_state.rs_last_eval_scene:
            return
        with st.spinner("Lars is thinking…"):
            _feedback = _claude_evaluate(
                user_text, _scene_now, st.session_state.rs_chat,
                knowledge_profile, name, level, bg_lang,
            )
        _audio = _tts_b64(_feedback, voice_id)
        _display = user_text if user_text else "(no response)"
        st.session_state.rs_chat.extend([
            {"role": "user",      "content": _display},
            {"role": "assistant", "content": _feedback},
        ])
        st.session_state.rs_evaluation     = {
            "scene_idx": scene_idx,
            "text":      _feedback,
            "tts_b64":   _audio or None,
        }
        st.session_state.rs_last_eval_scene = scene_idx
        st.session_state.rs_phase = "feedback"
        st.rerun()

    if _mic_visible and isinstance(_result, dict) and _result.get("type") == "transcript":
        _handle_eval(_result["scene_idx"], _result.get("text", "").strip())


