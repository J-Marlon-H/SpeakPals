# SpeakPals — Restaurant Video Lesson
from __future__ import annotations
import streamlit as st
import requests, json, base64, pathlib
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
# Only include fields the component or Python evaluation actually needs.

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

_RS_KEYS = ["rs_started","rs_complete","rs_chat","rs_evaluation","rs_last_eval_scene"]
for k, v in [
    ("rs_started",        False),
    ("rs_complete",       False),
    ("rs_chat",           []),
    ("rs_evaluation",     None),
    ("rs_last_eval_scene",-1),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Layout ─────────────────────────────────────────────────────────────────────

col_video, col_sidebar = st.columns([3, 1], gap="medium")

with col_video:

    # ── Start screen ───────────────────────────────────────────────────────────
    if not st.session_state.rs_started:
        st.markdown("""
        <div style='text-align:center;padding:60px 20px 30px'>
          <div style='font-size:56px;margin-bottom:16px'>🍜</div>
          <div style='font:800 26px/1.2 system-ui;color:#f1f5f9;margin-bottom:10px'>
            At the Restaurant</div>
          <div style='font:400 14px/1.6 system-ui;color:rgba(255,255,255,.5);
            max-width:340px;margin:0 auto 32px'>
            A video lesson set in a ramen restaurant. Watch the scenes and
            speak your Danish answers — Lars will guide you through.</div>
        </div>""", unsafe_allow_html=True)
        _, btn_col, _ = st.columns([2, 2, 2])
        with btn_col:
            if st.button("▶  Start Lesson", use_container_width=True, type="primary"):
                st.session_state.rs_started = True
                st.rerun()

    # ── Complete screen ────────────────────────────────────────────────────────
    elif st.session_state.rs_complete:
        st.markdown(f"""
        <div style='text-align:center;padding:50px 20px 24px'>
          <div style='font-size:56px;margin-bottom:16px'>🎉</div>
          <div style='font:800 26px/1.2 system-ui;color:#f1f5f9;margin-bottom:10px'>
            Lesson Complete!</div>
          <div style='font:400 14px/1.6 system-ui;color:rgba(255,255,255,.55);
            max-width:360px;margin:0 auto 32px'>
            Great work, {name}! You ordered ramen, asked for a fork, and got the
            bill — all in Danish. 🍜</div>
        </div>""", unsafe_allow_html=True)
        _, btn_col, _ = st.columns([2, 2, 2])
        with btn_col:
            if st.button("← Back to Home", use_container_width=True, type="primary"):
                for k in _RS_KEYS:
                    st.session_state.pop(k, None)
                st.switch_page("pages/home.py")

    # ── Active lesson — unified component ─────────────────────────────────────
    else:
        comp_props: dict = {
            "scenes":     SCENES,
            "started":    True,
            "evaluation": st.session_state.rs_evaluation,
            "key":        "restaurant_player",
            "height":     600,
            "default":    None,
        }
        if IS_LOCAL:
            comp_props["proxy_port"] = PROXY_PORT
        else:
            tok = _scribe_token(ELEVEN_KEY)
            if tok:
                comp_props["ws_token"] = tok

        result = restaurant_player(**comp_props)

        if isinstance(result, dict):
            if result.get("type") == "transcript":
                scene_idx = result["scene_idx"]
                # Deduplicate — same transcript fires on every rerun until component resets
                if scene_idx != st.session_state.rs_last_eval_scene:
                    scene    = SCENES[scene_idx]
                    txt      = result.get("text", "").strip()
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
                    st.rerun()

            elif result.get("type") == "complete":
                st.session_state.rs_complete = True
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
