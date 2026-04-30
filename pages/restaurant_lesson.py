# SpeakPals — Restaurant Video Lesson
from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
import requests, json, base64, pathlib
from dotenv import load_dotenv
from db import require_auth, load_knowledge_profile, _secret
from pipeline import VOICES_BY_LANG, SETTINGS_DEFAULTS

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
        "hint":        "Try 'Ved vinduet tak' (by the window, please)",
        "tutor_break": False,
    },
    {
        "index":       1,
        "video":       "scene2.mp4",
        "user_turn":   True,
        "en_prompt":   "Order the ramen from the menu.",
        "da_target":   "Jeg vil gerne have ramen",
        "hint":        "Try 'Jeg vil gerne have ramen tak' (I'd like the ramen, please)",
        "tutor_break": True,
    },
    {
        "index":       2,
        "video":       "scene3.mp4",
        "user_turn":   False,
        "en_prompt":   "",
    },
    {
        "index":       3,
        "video":       "scene4.mp4",
        "user_turn":   True,
        "en_prompt":   "The ramen arrived! Thank the waiter and ask for a fork.",
        "da_target":   "Tak! Må jeg få en gaffel?",
        "hint":        "Try 'Tak! Må jeg få en gaffel?' (Thanks! May I have a fork?)",
        "tutor_break": False,
    },
    {
        "index":       4,
        "video":       "scene5.mp4",
        "user_turn":   False,
        "en_prompt":   "",
    },
    {
        "index":       5,
        "video":       "scene6.mp4",
        "user_turn":   True,
        "en_prompt":   "The meal was great. Ask for the bill.",
        "da_target":   "Må jeg bede om regningen?",
        "hint":        "Try 'Må jeg bede om regningen?' (May I have the bill?)",
        "tutor_break": False,
        "is_final":    True,
    },
]

VIDEO_DIR = pathlib.Path(__file__).parent.parent / "static" / "restaurant"

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

def _tutor_reply(question: str, knowledge_profile: dict,
                 name: str, level: str, bg_lang: str) -> str:
    system = (
        f"You are Lars, a warm Danish tutor. The student ({name}, level {level}, "
        f"native language: {bg_lang}) is mid-lesson at a restaurant. "
        f"Answer their question helpfully in 1-2 sentences. Plain text only."
    )
    if knowledge_profile:
        system += f"\n\nWhat you know about this student: {json.dumps(knowledge_profile)}"
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 150,
              "temperature": 0.6, "system": system,
              "messages": [{"role": "user", "content": question}]},
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

def _play_audio(b64: str) -> None:
    components.html(f"""<script>
      (function(){{
        const a = new Audio("data:audio/mpeg;base64,{b64}");
        a.play().catch(()=>{{}});
      }})();
    </script>""", height=0)

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

  .scene-badge{display:inline-block;padding:3px 10px;border-radius:20px;
    font:600 11px system-ui;letter-spacing:1px;text-transform:uppercase;
    background:rgba(13,148,136,.2);color:#2dd4bf;border:1px solid rgba(13,148,136,.3)}
  .prompt-box{background:rgba(13,148,136,.12);border:1px solid rgba(13,148,136,.3);
    border-radius:12px;padding:12px 16px;color:#e2e8f0;font-size:14px;margin:8px 0}
  .hint-box{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
    border-radius:10px;padding:10px 14px;font-size:13px;color:#fcd34d;margin-top:6px}
  .chat-msg{padding:10px 14px;border-radius:12px;margin-bottom:6px;font-size:13px;line-height:1.5}
  .chat-user{background:rgba(13,148,136,.15);color:#e2e8f0;text-align:right}
  .chat-tutor{background:rgba(255,255,255,.07);color:#e2e8f0}
  .stTextInput input{
    background:rgba(255,255,255,.08)!important;color:#f1f5f9!important;
    -webkit-text-fill-color:#f1f5f9!important;
    border:1px solid rgba(255,255,255,.15)!important;border-radius:10px!important}
  .stButton button{border-radius:10px!important;font-weight:600!important;font-size:13px!important}
  .stButton button[kind="primary"]{
    background:#0d9488!important;color:#fff!important;border:none!important}
  video{border-radius:16px;width:100%}
</style>""", unsafe_allow_html=True)

# ── User profile ───────────────────────────────────────────────────────────────

sb_user_id = st.session_state.get("sb_user_id")
sb_token   = st.session_state.get("sb_access_token")
name       = st.session_state.get("s_name")    or "there"
level      = st.session_state.get("s_level")   or "A1"
bg_lang    = st.session_state.get("s_bg_lang") or "English"
target_lang = "Danish"
lang_voices = VOICES_BY_LANG.get(target_lang, {})
voice_label = st.session_state.get("s_voice_label", SETTINGS_DEFAULTS["s_voice_label"])
voice_id    = lang_voices.get(voice_label, next(iter(lang_voices.values()), ""))
knowledge_profile = st.session_state.get("knowledge_profile") or {}
if sb_user_id and sb_token and not knowledge_profile:
    knowledge_profile = load_knowledge_profile(sb_user_id, sb_token) or {}

# ── Session state ──────────────────────────────────────────────────────────────

for k, v in [
    ("rs_scene_idx",  0),
    ("rs_watching",   True),   # True = video phase, False = answer phase
    ("rs_chat",       []),
    ("rs_tutor_mode", False),
    ("rs_complete",   False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

scene_idx = st.session_state.rs_scene_idx
scene     = SCENES[scene_idx] if scene_idx < len(SCENES) else None

# ── Layout ─────────────────────────────────────────────────────────────────────

col_video, col_sidebar = st.columns([3, 1], gap="medium")

with col_video:
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:10px;padding:0 0 10px'>
      <div style='font:800 20px/1 system-ui;color:#f1f5f9;letter-spacing:-.3px'>🍜 At the Restaurant</div>
      <div class='scene-badge'>Scene {scene_idx + 1} / {len(SCENES)}</div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.rs_complete:
        st.success(f"🎉 Lesson complete! Great work, {name}!")
        if st.button("← Back to Home", use_container_width=True):
            for k in ["rs_scene_idx","rs_watching","rs_chat","rs_tutor_mode","rs_complete"]:
                st.session_state.pop(k, None)
            st.switch_page("pages/home.py")

    elif scene:
        video_path = VIDEO_DIR / scene["video"]

        # ── Video phase ────────────────────────────────────────────────────────
        if st.session_state.rs_watching:
            if video_path.exists():
                st.video(str(video_path), autoplay=True)
            else:
                st.warning(f"Video file not found: {scene['video']}")

            st.markdown("<br>", unsafe_allow_html=True)

            if not scene["user_turn"]:
                # Auto-advance scenes (3 and 5) — no user input needed
                if st.button("▶ Continue", use_container_width=True, type="primary",
                             key=f"continue_{scene_idx}"):
                    next_idx = scene_idx + 1
                    if next_idx >= len(SCENES):
                        st.session_state.rs_complete = True
                    else:
                        st.session_state.rs_scene_idx = next_idx
                        st.session_state.rs_watching  = True
                    st.rerun()
            else:
                if st.button("🎤 I'm ready to answer", use_container_width=True, type="primary",
                             key=f"ready_{scene_idx}"):
                    st.session_state.rs_watching = False
                    st.rerun()

        # ── Answer phase ───────────────────────────────────────────────────────
        else:
            if video_path.exists():
                st.video(str(video_path))

            if not st.session_state.rs_tutor_mode:
                st.markdown(f"<div class='prompt-box'>💬 {scene['en_prompt']}</div>",
                            unsafe_allow_html=True)

                user_input = st.text_input("Your answer in Danish:",
                                           key=f"answer_{scene_idx}",
                                           placeholder="Type in Danish…")

                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    submit = st.button("Submit ✓", use_container_width=True,
                                       type="primary", key=f"submit_{scene_idx}")
                with c2:
                    hint = st.button("Hint 💡", use_container_width=True,
                                     key=f"hint_{scene_idx}")
                with c3:
                    if scene.get("tutor_break"):
                        if st.button("Ask Lars 🎓", use_container_width=True,
                                     key=f"tutor_btn_{scene_idx}"):
                            st.session_state.rs_tutor_mode = True
                            st.rerun()

                if hint:
                    st.markdown(f"<div class='hint-box'>💡 {scene['hint']}</div>",
                                unsafe_allow_html=True)

                if submit and user_input.strip():
                    with st.spinner("Lars is listening…"):
                        feedback = _claude_evaluate(
                            user_input.strip(), scene,
                            st.session_state.rs_chat,
                            knowledge_profile, name, level, bg_lang,
                        )
                    st.session_state.rs_chat.extend([
                        {"role": "user",      "content": user_input.strip()},
                        {"role": "assistant", "content": feedback},
                    ])
                    audio = _tts_b64(feedback, voice_id)
                    if audio:
                        _play_audio(audio)

                    next_idx = scene_idx + 1
                    if next_idx >= len(SCENES):
                        st.session_state.rs_complete = True
                    else:
                        st.session_state.rs_scene_idx = next_idx
                        st.session_state.rs_watching  = True
                    st.rerun()

with col_sidebar:
    st.markdown("""<div style='font:700 10px system-ui;color:rgba(255,255,255,.4);
      letter-spacing:2px;text-transform:uppercase;margin-bottom:12px'>
      💡 Lars · Tutor</div>""", unsafe_allow_html=True)

    # ── Tutor break ────────────────────────────────────────────────────────────
    if st.session_state.rs_tutor_mode:
        st.markdown("""<div style='background:rgba(13,148,136,.15);border:1px solid
          rgba(13,148,136,.3);border-radius:10px;padding:10px 12px;font-size:12px;
          color:#2dd4bf;margin-bottom:10px'>Ask Lars anything — vocabulary, how to say something.</div>""",
                    unsafe_allow_html=True)
        q = st.text_input("Your question:", key="tutor_q",
                          placeholder="How do I ask for a fork?")
        if st.button("Ask", key="ask_tutor", type="primary"):
            if q.strip():
                with st.spinner("Lars is thinking…"):
                    answer = _tutor_reply(q.strip(), knowledge_profile, name, level, bg_lang)
                st.session_state.rs_chat.extend([
                    {"role": "user",      "content": f"[Question] {q.strip()}"},
                    {"role": "assistant", "content": answer},
                ])
                audio = _tts_b64(answer, voice_id)
                if audio:
                    _play_audio(audio)
                st.rerun()
        if st.button("← Back to lesson", key="back_lesson"):
            st.session_state.rs_tutor_mode = False
            st.rerun()
        st.markdown("<hr style='border-color:rgba(255,255,255,.1);margin:12px 0'>",
                    unsafe_allow_html=True)

    # ── Transcript ─────────────────────────────────────────────────────────────
    if st.session_state.rs_chat:
        st.markdown("""<div style='font:700 10px system-ui;color:rgba(255,255,255,.3);
          letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px'>Conversation</div>""",
                    unsafe_allow_html=True)
        for msg in st.session_state.rs_chat:
            content = msg["content"].removeprefix("[Question] ")
            if msg["role"] == "user":
                st.markdown(f"<div class='chat-msg chat-user'>🧑 {content}</div>",
                            unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='chat-msg chat-tutor'>💡 {content}</div>",
                            unsafe_allow_html=True)
    else:
        st.markdown("""<div style='font:400 12px system-ui;color:rgba(255,255,255,.25);margin-top:8px'>
          Your conversation will appear here.</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🏠 Exit lesson", use_container_width=True):
        for k in ["rs_scene_idx","rs_watching","rs_chat","rs_tutor_mode","rs_complete"]:
            st.session_state.pop(k, None)
        st.switch_page("pages/home.py")
