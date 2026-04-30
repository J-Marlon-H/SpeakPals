# SpeakPals — Restaurant Video Lesson
from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
import requests, json, base64
from dotenv import load_dotenv
from db import require_auth, load_knowledge_profile, _secret
from pipeline import VOICES_BY_LANG, SETTINGS_DEFAULTS, MODELS
from prompts import build_system_prompt
from tutor import Tutor
from video_player_helper import video_player

load_dotenv("keys.env")
require_auth()

CLAUDE_KEY = _secret("CLAUDE_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")

# ── Scene definitions ──────────────────────────────────────────────────────────

SCENES = [
    {
        "index":       0,
        "video":       "scene1.mp4",
        "user_turn":   True,
        "en_prompt":   "The waiter is asking: bar or window?",
        "da_target":   "Ved vinduet",
        "hint":        "Try saying 'Ved vinduet tak' (by the window, please)",
        "tutor_break": False,
        "auto_advance":False,
    },
    {
        "index":       1,
        "video":       "scene2.mp4",
        "user_turn":   True,
        "en_prompt":   "Order the ramen from the menu.",
        "da_target":   "Jeg vil gerne have ramen",
        "hint":        "Try 'Jeg vil gerne have ramen tak' (I'd like the ramen, please)",
        "tutor_break": True,
        "auto_advance":False,
    },
    {
        "index":       2,
        "video":       "scene3.mp4",
        "user_turn":   False,
        "en_prompt":   "",
        "auto_advance":True,
    },
    {
        "index":       3,
        "video":       "scene4.mp4",
        "user_turn":   True,
        "en_prompt":   "The ramen arrived! Thank the waiter and ask for a fork.",
        "da_target":   "Tak! Må jeg få en gaffel?",
        "hint":        "Try 'Tak! Må jeg få en gaffel?' (Thanks! May I have a fork?)",
        "tutor_break": False,
        "auto_advance":False,
    },
    {
        "index":       4,
        "video":       "scene5.mp4",
        "user_turn":   False,
        "en_prompt":   "",
        "auto_advance":True,
    },
    {
        "index":       5,
        "video":       "scene6.mp4",
        "user_turn":   True,
        "en_prompt":   "The meal was great. Ask for the bill.",
        "da_target":   "Må jeg bede om regningen?",
        "hint":        "Try 'Må jeg bede om regningen?' (May I have the bill?)",
        "tutor_break": False,
        "auto_advance":False,
        "is_final":    True,
    },
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def _scene_url(filename: str) -> str:
    return f"/app/static/restaurant/{filename}"

def _claude_evaluate(user_text: str, scene: dict, history: list,
                     knowledge_profile: dict, name: str, level: str, bg_lang: str) -> str:
    """Ask Claude to evaluate the user's Danish answer and give brief feedback."""
    system = (
        f"You are Lars, a warm Danish tutor. The student ({name}, level {level}, "
        f"native language: {bg_lang}) is doing a restaurant role-play lesson. "
        f"They were asked to say something like: '{scene['da_target']}'\n\n"
        f"Evaluate their attempt briefly (1-2 sentences max). "
        f"If correct or close: praise and confirm in English. "
        f"If wrong or blank: give a short encouraging hint with the correct Danish phrase. "
        f"Never be discouraging. Plain text only — no markdown, no JSON."
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
    """Generate ElevenLabs TTS and return base64 MP3."""
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

def _tutor_reply(user_question: str, knowledge_profile: dict,
                 name: str, level: str, bg_lang: str) -> str:
    """Ask Claude to answer a mid-lesson tutor question."""
    system = (
        f"You are Lars, a warm Danish tutor. The student ({name}, level {level}, "
        f"native language: {bg_lang}) is mid-lesson at a restaurant and has a question. "
        f"Answer helpfully in 1-2 sentences. Plain text only."
    )
    if knowledge_profile:
        system += f"\n\nWhat you know about this student: {json.dumps(knowledge_profile)}"
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 150,
              "temperature": 0.6,
              "system": system,
              "messages": [{"role": "user", "content": user_question}]},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()

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
  div[data-testid="stVerticalBlock"]{gap:0.5rem!important}

  .scene-badge{
    display:inline-block;padding:4px 12px;border-radius:20px;
    font:600 11px system-ui;letter-spacing:1px;text-transform:uppercase;
    background:rgba(13,148,136,.2);color:#2dd4bf;border:1px solid rgba(13,148,136,.3)}
  .chat-msg{padding:10px 14px;border-radius:12px;margin-bottom:8px;font-size:13px;line-height:1.5}
  .chat-user{background:rgba(13,148,136,.15);color:#e2e8f0;text-align:right}
  .chat-tutor{background:rgba(255,255,255,.07);color:#e2e8f0}
  .tutor-label{font:700 10px system-ui;letter-spacing:1.5px;text-transform:uppercase;
    color:rgba(255,255,255,.4);margin-bottom:4px}
  .hint-box{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
    border-radius:10px;padding:10px 14px;font-size:12px;color:#fcd34d;margin-top:8px}
  .stTextInput input{
    background:rgba(255,255,255,.08)!important;color:#f1f5f9!important;
    -webkit-text-fill-color:#f1f5f9!important;
    border:1px solid rgba(255,255,255,.15)!important;border-radius:10px!important}
  .stButton button{
    border-radius:10px!important;font-weight:600!important;font-size:13px!important}
</style>""", unsafe_allow_html=True)

# ── Load user profile ──────────────────────────────────────────────────────────

sb_user_id = st.session_state.get("sb_user_id")
sb_token   = st.session_state.get("sb_access_token")

name     = st.session_state.get("s_name")    or "there"
level    = st.session_state.get("s_level")   or "A1"
bg_lang  = st.session_state.get("s_bg_lang") or "English"

target_lang  = "Danish"
lang_voices  = VOICES_BY_LANG.get(target_lang, {})
voice_label  = st.session_state.get("s_voice_label", SETTINGS_DEFAULTS["s_voice_label"])
voice_id     = lang_voices.get(voice_label, next(iter(lang_voices.values()), ""))

knowledge_profile = st.session_state.get("knowledge_profile") or {}
if sb_user_id and sb_token and not knowledge_profile:
    knowledge_profile = load_knowledge_profile(sb_user_id, sb_token) or {}

# ── Session state ──────────────────────────────────────────────────────────────

for k, v in [
    ("rs_scene_idx",     0),
    ("rs_waiting",       False),   # True when video ended, awaiting user input
    ("rs_chat",          []),
    ("rs_tutor_mode",    False),   # True when tutor break active
    ("rs_complete",      False),
    ("rs_audio_queue",   None),
    ("rs_autoplay_next", False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

scene_idx = st.session_state.rs_scene_idx
scene     = SCENES[scene_idx] if scene_idx < len(SCENES) else None

# ── Layout ─────────────────────────────────────────────────────────────────────

col_video, col_sidebar = st.columns([3, 1], gap="medium")

# ── Video column ───────────────────────────────────────────────────────────────

with col_video:
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:10px;padding:0 0 12px'>
      <div style='font:800 20px/1 system-ui;color:#f1f5f9;letter-spacing:-.3px'>🍜 At the Restaurant</div>
      <div class='scene-badge'>Scene {scene_idx + 1} / {len(SCENES)}</div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.rs_complete:
        st.success("🎉 Lesson complete! Great work, " + name + "!")
        if st.button("← Back to Home", use_container_width=True):
            st.switch_page("pages/home.py")

    elif scene:
        scene_url  = _scene_url(scene["video"])
        user_turn  = st.session_state.rs_waiting and scene["user_turn"]
        auto_scene = scene.get("auto_advance", False)

        result = video_player(
            scene_url   = scene_url,
            scene_index = scene_idx,
            autoplay    = True,
            user_turn   = user_turn,
            prompt_text = scene.get("en_prompt", "") if user_turn else "",
            key         = f"vp_{scene_idx}",
        )

        # Handle video ended event
        if result and isinstance(result, dict) and result.get("event") == "ended":
            if not st.session_state.rs_waiting:
                if auto_scene:
                    # Auto-advance scenes (3 and 5) — no user input
                    next_idx = scene_idx + 1
                    if next_idx >= len(SCENES):
                        st.session_state.rs_complete = True
                    else:
                        st.session_state.rs_scene_idx     = next_idx
                        st.session_state.rs_autoplay_next = True
                else:
                    st.session_state.rs_waiting = True
                st.rerun()

        # Play queued tutor audio
        if st.session_state.rs_audio_queue:
            audio_b64 = st.session_state.rs_audio_queue
            st.session_state.rs_audio_queue = None
            components.html(f"""<script>
              (function(){{
                const a = new Audio("data:audio/mpeg;base64,{audio_b64}");
                a.play().catch(()=>{{}});
              }})();
            </script>""", height=0)

        # User input when it's their turn
        if st.session_state.rs_waiting and scene["user_turn"] and not st.session_state.rs_tutor_mode:
            st.markdown(f"<div class='hint-box'>💬 {scene['en_prompt']}</div>",
                        unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            user_input = st.text_input("Your answer in Danish:",
                                       key=f"answer_{scene_idx}",
                                       placeholder="Type in Danish…")

            btn_col1, btn_col2 = st.columns([2, 1])
            with btn_col1:
                submit = st.button("Submit ✓", use_container_width=True, type="primary",
                                   key=f"submit_{scene_idx}")
            with btn_col2:
                hint = st.button("Hint 💡", use_container_width=True,
                                 key=f"hint_{scene_idx}")

            if hint:
                st.info(scene.get("hint", ""))

            if scene.get("tutor_break"):
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Ask tutor 🎓", key=f"tutor_btn_{scene_idx}"):
                    st.session_state.rs_tutor_mode = True
                    st.rerun()

            if submit and user_input.strip():
                feedback = _claude_evaluate(
                    user_input.strip(), scene,
                    st.session_state.rs_chat,
                    knowledge_profile, name, level, bg_lang,
                )
                st.session_state.rs_chat.extend([
                    {"role": "user",      "content": user_input.strip()},
                    {"role": "assistant", "content": feedback},
                ])
                # Generate tutor voice feedback
                audio = _tts_b64(feedback, voice_id)
                if audio:
                    st.session_state.rs_audio_queue = audio

                # Advance to next scene
                next_idx = scene_idx + 1
                if next_idx >= len(SCENES):
                    st.session_state.rs_complete = True
                else:
                    st.session_state.rs_scene_idx = next_idx
                st.session_state.rs_waiting = False
                st.rerun()

# ── Sidebar column ─────────────────────────────────────────────────────────────

with col_sidebar:
    st.markdown("""<div style='font:700 10px system-ui;color:rgba(255,255,255,.4);
      letter-spacing:2px;text-transform:uppercase;margin-bottom:12px'>
      💡 Lars · Tutor</div>""", unsafe_allow_html=True)

    # Tutor break mode
    if st.session_state.rs_tutor_mode:
        st.markdown("""<div style='background:rgba(13,148,136,.15);border:1px solid
          rgba(13,148,136,.3);border-radius:10px;padding:10px 12px;font-size:12px;
          color:#2dd4bf;margin-bottom:12px'>
          Ask Lars anything about the lesson — vocabulary, grammar, how to say something.
        </div>""", unsafe_allow_html=True)

        q = st.text_input("Your question:", key="tutor_q",
                          placeholder="How do I ask for a fork?")
        if st.button("Ask", key="ask_tutor", type="primary"):
            if q.strip():
                answer = _tutor_reply(q.strip(), knowledge_profile, name, level, bg_lang)
                st.session_state.rs_chat.extend([
                    {"role": "user",      "content": f"[Tutor question] {q.strip()}"},
                    {"role": "assistant", "content": answer},
                ])
                audio = _tts_b64(answer, voice_id)
                if audio:
                    st.session_state.rs_audio_queue = audio
                st.rerun()

        if st.button("← Back to lesson", key="back_lesson"):
            st.session_state.rs_tutor_mode = False
            st.rerun()

        st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

    # Conversation transcript
    if st.session_state.rs_chat:
        st.markdown("""<div style='font:700 10px system-ui;color:rgba(255,255,255,.3);
          letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px'>
          Conversation</div>""", unsafe_allow_html=True)

        for msg in st.session_state.rs_chat:
            if msg["role"] == "user":
                content = msg["content"].removeprefix("[Tutor question] ")
                st.markdown(f"<div class='chat-msg chat-user'>🧑 {content}</div>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-msg chat-tutor'>💡 {msg['content']}</div>",
                            unsafe_allow_html=True)
    else:
        st.markdown("""<div style='font:400 12px system-ui;color:rgba(255,255,255,.25);
          margin-top:8px'>Your conversation will appear here as you progress.</div>""",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🏠 Exit lesson", use_container_width=True):
        for k in ["rs_scene_idx","rs_waiting","rs_chat","rs_tutor_mode",
                  "rs_complete","rs_audio_queue","rs_autoplay_next"]:
            st.session_state.pop(k, None)
        st.switch_page("pages/home.py")
