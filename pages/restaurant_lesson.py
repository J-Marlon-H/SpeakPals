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
        "user_turn":   True,
        "en_prompt":   "",
        "da_target":   "Må jeg bede om regningen?",
        "hint":        "Try 'Må jeg bede om regningen?' (May I have the bill?)",
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
        f"Evaluate their attempt in 1-2 sentences. "
        f"If correct or close: praise and confirm. "
        f"If wrong: give a short encouraging hint with the correct Danish phrase. "
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
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 150,
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
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
  html,body{font-family:system-ui,-apple-system,BlinkMacSystemFont,Roboto,sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#0a0a0a!important}
  .block-container{padding:1rem 1.5rem!important;max-width:100%!important}
  div[data-testid="stVerticalBlock"]{gap:0.4rem!important}
  .chat-msg{padding:10px 14px;border-radius:12px;margin-bottom:6px;font-size:13px;line-height:1.5}
  .chat-user{background:rgba(13,148,136,.15);color:#e2e8f0;text-align:right}
  .chat-tutor{background:rgba(255,255,255,.07);color:#e2e8f0}
  .stButton button{border-radius:10px!important;font-weight:600!important;font-size:13px!important}
  .stButton button[kind="primary"]{
    background:#0d9488!important;color:#fff!important;border:none!important}
  /* Dark background for video widget */
  [data-testid="stVideo"]{border-radius:14px;overflow:hidden}
  video{border-radius:14px}
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

# ── Layout ─────────────────────────────────────────────────────────────────────

col_main, col_sidebar = st.columns([3, 1], gap="medium")

with col_main:

    # ── Start screen ───────────────────────────────────────────────────────────
    if rs_phase == "start":
        st.markdown("""
        <div style='text-align:center;padding:60px 20px 30px'>
          <div style='font-size:56px;margin-bottom:16px'>🍜</div>
          <div style='font:800 26px/1.2 system-ui;color:#f1f5f9;margin-bottom:10px'>
            At the Restaurant</div>
          <div style='font:400 14px/1.6 system-ui;color:rgba(255,255,255,.5);
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
        last_eval  = st.session_state.rs_evaluation or {}
        tts_b64    = last_eval.get("tts_b64", "")
        lars_text  = last_eval.get("text", "")
        audio_tag  = (f'<audio autoplay src="data:audio/mpeg;base64,{tts_b64}" '
                      f'style="display:none"></audio>') if tts_b64 else ""
        lars_block = (f"<div style='background:rgba(13,148,136,.15);"
                      f"border:1px solid rgba(13,148,136,.3);border-radius:10px;"
                      f"padding:12px 16px;margin:0 auto 24px;max-width:380px;"
                      f"font:13px/1.5 system-ui;color:#e2e8f0;text-align:left'>"
                      f"💡 {lars_text}</div>") if lars_text else ""
        st.markdown(f"""
        {audio_tag}
        <div style='text-align:center;padding:50px 20px 24px'>
          <div style='font-size:56px;margin-bottom:16px'>🎉</div>
          <div style='font:800 26px/1.2 system-ui;color:#f1f5f9;margin-bottom:10px'>
            Lesson Complete!</div>
          <div style='font:400 14px/1.6 system-ui;color:rgba(255,255,255,.55);
            max-width:360px;margin:0 auto 24px'>
            Great work, {name}! You ordered ramen, asked for a fork, and got the
            bill — all in Danish. 🍜</div>
          {lars_block}
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

        st.markdown(
            f"<div style='font:700 10px system-ui;color:rgba(13,148,136,.8);"
            f"letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px'>"
            f"Scene {rs_scene_idx + 1} / {len(SCENES)}</div>",
            unsafe_allow_html=True,
        )
        if video_path.exists():
            st.video(str(video_path), autoplay=True)
        else:
            st.warning(f"Video not found: {video_path}")

        if scene.get("en_prompt"):
            st.markdown(
                f"<div style='font:13px/1.5 system-ui;color:rgba(255,255,255,.6);"
                f"margin-top:8px;text-align:center'>{scene['en_prompt']}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            label = "🎤  Ready to respond in Danish" if scene["user_turn"] else "Continue  →"
            if st.button(label, use_container_width=True, type="primary"):
                if scene["user_turn"]:
                    st.session_state.rs_phase = "mic"
                else:
                    next_idx = rs_scene_idx + 1
                    if next_idx >= len(SCENES):
                        st.session_state.rs_phase = "complete"
                    else:
                        st.session_state.rs_scene_idx = next_idx
                        st.session_state.rs_phase = "video"
                st.rerun()

    # ── Mic phase ──────────────────────────────────────────────────────────────
    elif rs_phase == "mic":
        scene = SCENES[rs_scene_idx]

        st.markdown(
            f"<div style='font:700 10px system-ui;color:rgba(13,148,136,.8);"
            f"letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px'>"
            f"Scene {rs_scene_idx + 1} / {len(SCENES)} · Your turn</div>",
            unsafe_allow_html=True,
        )
        if scene.get("en_prompt"):
            st.markdown(
                f"<div style='font:14px/1.5 system-ui;color:#e2e8f0;"
                f"text-align:center;margin-bottom:10px'>"
                f"💬 {scene['en_prompt']}</div>",
                unsafe_allow_html=True,
            )

        comp_props: dict = {
            "scene_idx": rs_scene_idx,
            "lang_code": "da",
            "label":     "Tap to speak in Danish",
            "hint":      scene.get("hint", ""),
            "key":       "restaurant_mic",
            "height":    180,
            "default":   None,
        }
        if IS_LOCAL:
            comp_props["proxy_port"] = PROXY_PORT
        else:
            tok = _scribe_token(ELEVEN_KEY)
            if tok:
                comp_props["ws_token"] = tok

        result = restaurant_player(**comp_props)

        if isinstance(result, dict) and result.get("type") == "transcript":
            scene_idx = result["scene_idx"]
            if scene_idx != st.session_state.rs_last_eval_scene:
                txt = result.get("text", "").strip()
                with st.spinner("Lars is thinking…"):
                    feedback = _claude_evaluate(
                        txt, scene, st.session_state.rs_chat,
                        knowledge_profile, name, level, bg_lang,
                    )
                audio = _tts_b64(feedback, voice_id)
                st.session_state.rs_chat.extend([
                    {"role": "user",      "content": txt},
                    {"role": "assistant", "content": feedback},
                ])
                st.session_state.rs_evaluation     = {
                    "scene_idx": scene_idx,
                    "text":      feedback,
                    "tts_b64":   audio or None,
                }
                st.session_state.rs_last_eval_scene = scene_idx
                st.session_state.rs_phase = "feedback"
                st.rerun()

    # ── Feedback phase ─────────────────────────────────────────────────────────
    elif rs_phase == "feedback":
        ev        = st.session_state.rs_evaluation or {}
        tts_b64   = ev.get("tts_b64", "")
        lars_text = ev.get("text", "")

        st.markdown(
            f"<div style='font:700 10px system-ui;color:rgba(13,148,136,.8);"
            f"letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px'>"
            f"Scene {rs_scene_idx + 1} / {len(SCENES)} · Lars' feedback</div>",
            unsafe_allow_html=True,
        )
        if tts_b64:
            st.markdown(
                f'<audio autoplay src="data:audio/mpeg;base64,{tts_b64}" style="display:none"></audio>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div style='background:rgba(13,148,136,.15);border:1px solid rgba(13,148,136,.3);"
            f"border-radius:12px;padding:14px 18px;font:14px/1.6 system-ui;color:#e2e8f0;"
            f"margin-bottom:12px'>💡 {lars_text}</div>",
            unsafe_allow_html=True,
        )

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

with col_sidebar:
    st.markdown("""<div style='font:700 10px system-ui;color:rgba(255,255,255,.4);
      letter-spacing:2px;text-transform:uppercase;margin-bottom:12px'>
      💡 Lars · Tutor</div>""", unsafe_allow_html=True)

    if st.session_state.rs_chat:
        st.markdown("""<div style='font:700 10px system-ui;color:rgba(255,255,255,.3);
          letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px'>
          Conversation</div>""", unsafe_allow_html=True)
        for msg in st.session_state.rs_chat:
            if msg["role"] == "user":
                st.markdown(f"<div class='chat-msg chat-user'>🧑 {msg['content']}</div>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-msg chat-tutor'>💡 {msg['content']}</div>",
                            unsafe_allow_html=True)
    else:
        st.markdown("""<div style='font:400 12px system-ui;color:rgba(255,255,255,.25);
          margin-top:8px'>Your conversation will appear here.</div>""",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🏠 Exit lesson", use_container_width=True):
        for k in _RS_KEYS:
            st.session_state.pop(k, None)
        st.switch_page("pages/home.py")
