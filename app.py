# SpeakPals — Danish Tutor

import streamlit as st
import streamlit.components.v1 as components
import hashlib, pathlib, time  # time used for replay nonce
from dotenv import load_dotenv
import os

from pipeline import run_pipeline_stream, MODELS
from avatar import avatar_html
from prompts import build_system_prompt
from ws_proxy import start_in_thread, PROXY_PORT

load_dotenv("keys.env")
CLAUDE_KEY = os.getenv("CLAUDE_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_EN   = "21m00Tcm4TlvDq8ikWAM"
VOICE_DA   = "ygiXC2Oa1BiHksD3WkJZ"  # Mathias - Danish baritone

# ── Start WebSocket proxy (once per process) ──────────────────────────────────

@st.cache_resource
def _start_proxy():
    return start_in_thread()

_start_proxy()

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="SpeakPals", page_icon="DK", layout="centered",
                   initial_sidebar_state="expanded")

components.html("""<script>
Object.keys(localStorage).forEach(function(k){
  if(k.indexOf('Sidebar')>-1) localStorage.removeItem(k);
});
</script>""", height=0)

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="collapsedControl"]{display:none!important}
  [data-testid="stSidebarCollapseButton"]{display:none!important}
  [data-testid="stAppViewContainer"]{background:#f8faff}
  [data-testid="stSidebar"]{background:#f0f4ff}
  .block-container{max-width:580px;padding-top:1rem;padding-bottom:1rem}
</style>""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")
    mode  = st.radio("Mode", ["Danish", "English Debug"], index=1)
    debug = "Debug" in mode
    st.divider()
    st.subheader("Student Profile")
    name    = st.text_input("Name", "Alex")
    level   = st.selectbox("Level", ["A1", "A2", "B1"])
    bg_lang = st.selectbox("Your native language", ["English", "German", "Swedish"])
    today   = st.text_area("Today's topics", "Daily life, shopping")
    st.divider()
    model_label = st.selectbox("AI model", list(MODELS.keys()))
    model_id    = MODELS[model_label]
    st.divider()
    if st.button("Clear chat"):
        for k in ["chat", "last_chunks", "last_response", "last_id"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── State ─────────────────────────────────────────────────────────────────────

for k, v in [("chat", []), ("last_chunks", None), ("last_response", None), ("last_id", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

system   = build_system_prompt(debug, name, level, today, bg_lang)
stt_lang = "en" if debug else "da"
voice_id = VOICE_EN if debug else VOICE_DA

# ── Layout ────────────────────────────────────────────────────────────────────

_vad_dir = pathlib.Path(__file__).parent / "vad_component"
mic      = components.declare_component("vad_mic", path=str(_vad_dir))

avatar_slot     = st.empty()
transcript_slot = st.empty()

transcript_raw = mic(key="vad_mic", lang=stt_lang, proxy_port=PROXY_PORT,
                     default=None, height=160)

with st.expander("type instead", expanded=False):
    text_in   = st.text_input("msg", placeholder="Type here...", label_visibility="collapsed")
    send_text = st.button("Send", use_container_width=True)

# ── Detect new input ──────────────────────────────────────────────────────────

voice_transcript = None
if transcript_raw and isinstance(transcript_raw, str) and transcript_raw.strip():
    h = hashlib.md5(transcript_raw.encode()).hexdigest()
    if h != st.session_state.last_id:
        st.session_state.last_id = h
        voice_transcript = transcript_raw.strip()

trigger_text = text_in.strip() if (send_text and text_in.strip()) else None
student_text = voice_transcript or trigger_text

# ── Pipeline ──────────────────────────────────────────────────────────────────

if student_text:
    with avatar_slot:
        components.html(avatar_html(thinking=True), height=310)
    try:
        all_chunks = []
        tutor_text = ""

        for tutor_text, chunk_b64 in run_pipeline_stream(
                system, student_text, st.session_state.chat, voice_id, CLAUDE_KEY, ELEVEN_KEY,
                model=model_id):
            all_chunks.append(chunk_b64)

        st.session_state.chat.extend([
            {"role": "user",      "content": student_text},
            {"role": "assistant", "content": tutor_text},
        ])
        st.session_state.last_chunks   = all_chunks
        st.session_state.last_response = (student_text, tutor_text)
    except Exception as e:
        st.error(f"Error: {e}")
        st.session_state.last_chunks = None

# ── Render avatar ─────────────────────────────────────────────────────────────

chunks = st.session_state.last_chunks or []
nonce  = hashlib.md5("".join(chunks[:1]).encode()).hexdigest()[:8] if chunks else "empty"
with avatar_slot:
    components.html(avatar_html(chunks=chunks) + f"<!-- {nonce} -->", height=310, scrolling=False)

# ── Transcript + replay ───────────────────────────────────────────────────────

if st.session_state.last_response:
    you, tutor = st.session_state.last_response
    with transcript_slot:
        with st.expander("last exchange", expanded=False):
            st.markdown(f"<small style='color:#94a3b8'><b>You:</b> {you}</small>", unsafe_allow_html=True)
            st.markdown(f"<small style='color:#6d7aad'><b>Tutor:</b> {tutor}</small>", unsafe_allow_html=True)
            if chunks:
                if st.button("replay", use_container_width=True):
                    with avatar_slot:
                        components.html(avatar_html(chunks=chunks) + f"<!-- replay-{time.time()} -->",
                                        height=310, scrolling=False)

# ── Conversation history ──────────────────────────────────────────────────────

if st.session_state.chat:
    with st.expander("conversation history", expanded=False):
        for m in st.session_state.chat:
            role  = "You" if m["role"] == "user" else "Tutor"
            color = "#94a3b8" if m["role"] == "user" else "#6d7aad"
            st.markdown(
                f"<div style='margin:6px 0'><small style='color:{color}'><b>{role}:</b> {m['content']}</small></div>",
                unsafe_allow_html=True)
