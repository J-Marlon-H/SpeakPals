# SpeakPals — Lesson

import streamlit as st
import streamlit.components.v1 as components
import hashlib, pathlib, base64
from dotenv import load_dotenv
import os

from pipeline import (run_pipeline_stream, MODELS, VOICES, SCENE_CATALOG,
                      parse_claude_response, generate_scene_image, character_tts_b64)
from prompts import build_system_prompt
from ws_proxy import start_in_thread, PROXY_PORT

load_dotenv("keys.env")

def _secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)

CLAUDE_KEY = _secret("CLAUDE_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
FAL_KEY    = _secret("FAL_KEY")

# ── Scene scripts ──────────────────────────────────────────────────────────────

SCENE_SCRIPTS = {
    "supermarket": [
        "Vil du betale med kort eller kontanter?",
        "Vil du have en kvittering?",
        "Hav en god dag!",
    ],
    "restaurant": [
        "Goddag og velkommen! Har du reserveret bord?",
        "Hvad kan jeg bringe dig i dag?",
        "Vil du have noget at drikke til maden?",
        "Er alt til din tilfredshed?",
        "Ønsker du dessert eller kaffe?",
    ],
}

SCENE_NEXT_PROMPT = {
    "supermarket": (
        "interior of a Danish bakery, a friendly baker facing directly toward you "
        "behind the counter with eye contact, warm morning light, pastries on display"
    )
}

# Build scene lookup from catalog
_SCENE_BY_KEY = {s["key"]: s for s in SCENE_CATALOG}

def _scene_key(scene_src: str) -> str | None:
    for key in SCENE_SCRIPTS:
        if key in (scene_src or ""):
            return key
    return None

# ── Local proxy vs cloud direct ────────────────────────────────────────────────

IS_LOCAL = pathlib.Path("keys.env").exists()

@st.cache_resource
def _start_proxy():
    if IS_LOCAL:
        return start_in_thread()
    return None

_start_proxy()


@st.cache_data
def _scene_to_data_url(src: str) -> str:
    """Load image from assets/scenes/ and return as base64 data URL."""
    path = pathlib.Path(__file__).parent / "assets" / src
    if not path.exists():
        return src   # fallback: pass raw path (won't render but won't crash)
    data = path.read_bytes()
    mime = "image/jpeg" if src.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode()

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Lesson — SpeakPals", page_icon="DK", layout="wide",
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
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stHeader"],header[data-testid="stHeader"],.stAppHeader{
    display:none!important;height:0!important;min-height:0!important}
  [data-testid="stAppViewContainer"]{background:#1a1a2e}
  /* Sidebar — dark conversation panel, 320px wide */
  [data-testid="stSidebar"]{background:#0b0b1a!important;border-right:1px solid rgba(129,140,248,.15)!important;width:320px!important;min-width:320px!important;color:#e2e8f0!important}
  [data-testid="stSidebar"] *{color:#e2e8f0!important}
  [data-testid="stSidebar"] section{padding:0!important}
  [data-testid="stSidebar"] .stButton button{
    background:rgba(129,140,248,.12)!important;color:#a5b4fc!important;
    border:1px solid rgba(129,140,248,.25)!important;border-radius:8px!important;
    font-size:13px!important}
  [data-testid="stSidebar"] .stButton button:hover{background:rgba(129,140,248,.22)!important}
  /* Remove ALL Streamlit main padding */
  .stMainBlockContainer,.block-container{padding:0!important;margin:0!important;max-width:100%!important}
  [data-testid="stVerticalBlock"]{gap:0!important;padding:0!important}
  section[data-testid="stMain"]{padding:0!important;overflow:hidden}
  [data-testid="stCustomComponentV1"]{padding:0!important;margin:0!important}
  /* Force iframe to fill the full main area */
  [data-testid="stCustomComponentV1"]{height:100vh!important;overflow:hidden!important}
  [data-testid="stCustomComponentV1"] iframe{
    position:fixed!important;top:0!important;left:320px!important;
    height:100vh!important;width:calc(100vw - 320px)!important;
    border:none!important;display:block!important;margin:0!important}
  /* Chat message slide-in animation */
  @keyframes msgSlideIn{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:translateX(0)}}
</style>""", unsafe_allow_html=True)

# ── Topic ──────────────────────────────────────────────────────────────────────

today = "Daily life, shopping"

# ── Read settings from session state (written by pages/account.py) ─────────────

name        = st.session_state.get("s_name",        "Marlon")
level       = st.session_state.get("s_level",       "A1")
bg_lang     = st.session_state.get("s_bg_lang",     "German")
voice_label = st.session_state.get("s_voice_label", list(VOICES.keys())[0])
model_label = st.session_state.get("s_model_label", "Sonnet 4.6 — best quality")
model_id    = MODELS[model_label]

# ── Session state ──────────────────────────────────────────────────────────────

for k, v in [
    ("chat", []), ("last_chunks", None), ("last_response", None), ("last_id", None),
    ("scene_images", []), ("scene_idx", 0), ("scene_loading", False),
    ("interaction_idx", 0), ("char_audio", []),
    ("scene_celebration", False), ("char_loaded_for", None),
    ("pipeline_error", None), ("pending_student", None), ("avatar_thinking", False),
    ("correct_log", []), ("lesson_started", False),
    ("tutor_play_seq", 0), ("char_play_seq", 0), ("replay_char_seq", 0),
    ("stop_audio_seq", 0),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Initialise first scene from selected_scene (set by home page) ──────────────

if not st.session_state.scene_images:
    selected = st.session_state.get("selected_scene")
    scene_data = _SCENE_BY_KEY.get(selected) if selected else None
    if scene_data:
        st.session_state.scene_images = [{
            "src":         f"scenes/{scene_data['file']}",
            "description": scene_data["scene_description"],
        }]
    else:
        st.switch_page("pages/home.py")

# ── Derived scene values ───────────────────────────────────────────────────────

scene_list        = st.session_state.scene_images
current_scene     = scene_list[st.session_state.scene_idx] if scene_list else None
scene_description = current_scene["description"] if current_scene else today
_scene_src_raw    = current_scene["src"] if current_scene else ""
scene_idx_1based  = st.session_state.scene_idx + 1
scene_history     = [s["description"] for s in scene_list[:st.session_state.scene_idx]]

# Convert local images to base64; FAL URLs pass through as-is
if _scene_src_raw and not _scene_src_raw.startswith(("http", "data:")):
    scene_src = _scene_to_data_url(_scene_src_raw)
else:
    scene_src = _scene_src_raw

voice_id = VOICES[voice_label]

char_voice_id = next(v for v in VOICES.values() if v != voice_id)

sk              = _scene_key(_scene_src_raw)
script          = SCENE_SCRIPTS.get(sk, []) if sk else []
char_label      = _SCENE_BY_KEY[sk]["char_name"] if sk and sk in _SCENE_BY_KEY else "Character"
interaction_idx = st.session_state.interaction_idx
char_question   = script[interaction_idx] if script and interaction_idx < len(script) else ""
is_last_question = bool(script) and interaction_idx == len(script) - 1

system = build_system_prompt(
    name, level, today, bg_lang,
    scene_description=scene_description,
    scene_idx=scene_idx_1based,
    scene_history=scene_history,
    char_question=char_question,
    is_last_question=is_last_question,
    step_current=interaction_idx + 1,
    step_total=max(len(script), 1),
)

# ── Character TTS — fetch when question changes, log it ONLY after student accepts ─
# (char question is added to correct_log in the pipeline section when has_ok)

char_loaded_key = (st.session_state.scene_idx, interaction_idx)

if (script
        and interaction_idx < len(script)
        and st.session_state.char_loaded_for != char_loaded_key
        and ELEVEN_KEY):
    line = script[interaction_idx]
    b64  = character_tts_b64(line, char_voice_id, ELEVEN_KEY)
    if b64:
        st.session_state.char_audio = [b64]
        st.session_state.char_play_seq += 1  # new seq → component always detects new audio
    else:
        st.session_state.char_audio = []
    # Log to sidebar chat immediately when cashier "speaks" (not waiting for has_ok)
    _log = st.session_state.correct_log
    if not any(e["who"] == "character" and e["text"] == line for e in _log):
        _log.append({"who": "character", "text": line})
    st.session_state.char_loaded_for = char_loaded_key

# ── Sidebar: conversation log ──────────────────────────────────────────────────

with st.sidebar:
    # Big header + account button
    col_title, col_acct = st.columns([3, 1])
    with col_title:
        st.markdown(
            "<div style='padding:20px 0 0 16px'>"
            "<div style='font:800 18px/1.2 Segoe UI,sans-serif;color:#e0e7ff;letter-spacing:-.3px'>Lesson Chat</div>"
            f"<div style='font:500 12px Segoe UI;color:rgba(129,140,248,.7);margin-top:4px'>Scene {scene_idx_1based} · {level} · {name}</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_acct:
        st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
        if st.button("⚙", help="Account settings", use_container_width=True):
            st.switch_page("pages/account.py")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,rgba(129,140,248,.3),transparent);margin:4px 16px 0'></div>",
        unsafe_allow_html=True
    )

    # Conversation log — only shown after lesson starts, single HTML block
    log = st.session_state.correct_log
    if not st.session_state.lesson_started:
        st.markdown(
            "<div style='padding:16px;font-size:12px;color:rgba(255,255,255,.55);font-style:italic'>"
            "Press Start Lesson to begin."
            "</div>",
            unsafe_allow_html=True
        )
    elif not log:
        st.markdown(
            "<div style='padding:16px;font-size:12px;color:rgba(255,255,255,.55);font-style:italic'>"
            "Start speaking — your accepted answers will appear here."
            "</div>",
            unsafe_allow_html=True
        )
    else:
        last_i = len(log) - 1
        parts = []
        for i, entry in enumerate(log):
            txt  = entry["text"].replace("<", "&lt;").replace(">", "&gt;")
            anim = "animation:msgSlideIn .4s cubic-bezier(.34,1.56,.64,1) both;" if i == last_i else ""
            if entry["who"] == "character":
                parts.append(
                    f"<div style='background:rgba(255,255,255,.07);border-radius:12px 12px 12px 3px;"
                    f"padding:10px 12px;margin:12px 12px 4px;font-size:13px;line-height:1.5;"
                    f"color:#e2e8f0;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Segoe UI;color:#94a3b8;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>{char_label}</span>"
                    f"<em>{txt}</em></div>"
                )
            else:
                parts.append(
                    f"<div style='background:rgba(129,140,248,.18);border-radius:12px 12px 3px 12px;"
                    f"padding:10px 12px;margin:4px 12px 12px;font-size:13px;line-height:1.5;"
                    f"color:#c7d2fe;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Segoe UI;color:#818cf8;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>You ✓</span>"
                    f"{txt}</div>"
                )
        st.markdown("".join(parts), unsafe_allow_html=True)

    # ── Replay cashier ────────────────────────────────────────────────────────
    if st.session_state.lesson_started and st.session_state.char_audio:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if st.button(f"↺ Replay {char_label.lower()}", use_container_width=True,
                     help=f"Replay {char_label.lower()}'s last line"):
            st.session_state.replay_char_seq += 1
            st.rerun()

    # Error debug
    if st.session_state.get("pipeline_error"):
        st.markdown(f"<div style='margin:8px 12px;padding:8px 10px;background:rgba(248,113,113,.12);border-radius:8px;color:#fca5a5;font-size:11px;word-break:break-word'>⚠ {st.session_state.pipeline_error}</div>", unsafe_allow_html=True)

    # Finish button
    if st.session_state.get("scene_idx", 0) >= 1:
        st.markdown("<div style='height:1px;background:rgba(255,255,255,.07);margin:8px 12px'></div>", unsafe_allow_html=True)
        if st.button("Finish Lecture", type="primary", use_container_width=True):
            st.switch_page("pages/feedback.py")

# ── VAD / scene component ──────────────────────────────────────────────────────

def _make_image_ready_cb(next_prompt, reset_interaction=False):
    def _cb(url):
        if url:
            st.session_state.scene_images.append({"description": next_prompt, "src": url})
            st.session_state.scene_idx += 1
            if reset_interaction:
                st.session_state.interaction_idx   = 0
                st.session_state.scene_celebration = False
                st.session_state.char_loaded_for   = None
        st.session_state.scene_loading = False
    return _cb

_vad_dir = pathlib.Path(__file__).parent / "vad_component"
mic = components.declare_component("vad_mic", path=str(_vad_dir))

chunks  = st.session_state.last_chunks or []
caption = ("Generating next scene…" if st.session_state.scene_loading
           else f"Scene {scene_idx_1based}")

def _scribe_token(eleven_key):
    try:
        import requests as _req
        r = _req.post(
            "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
            headers={"xi-api-key": eleven_key}, timeout=5)
        return r.json().get("token")
    except Exception:
        return None

mic_props = dict(
    lang              = "da",
    scene_src         = scene_src,
    scene_caption     = caption,
    avatar_chunks     = chunks,
    avatar_thinking   = st.session_state.avatar_thinking,
    char_audio        = st.session_state.char_audio,
    tutor_play_seq    = st.session_state.tutor_play_seq,
    char_play_seq     = st.session_state.char_play_seq,
    replay_char_seq   = st.session_state.replay_char_seq,
    stop_audio_seq    = st.session_state.stop_audio_seq,
    tutor_text        = (st.session_state.last_response[1]
                         if st.session_state.last_response else ""),
    progress_current  = min(interaction_idx, len(script)),
    progress_total    = len(script),
    scene_celebration = st.session_state.scene_celebration,
    default           = None,
    height            = 900,
)
if IS_LOCAL:
    mic_props["proxy_port"] = PROXY_PORT
else:
    ws_token = _scribe_token(ELEVEN_KEY)
    if ws_token:
        mic_props["ws_token"] = ws_token

transcript_raw = mic(key="vad_mic", **mic_props)

# ── Detect new voice input ─────────────────────────────────────────────────────

if transcript_raw == "__started__":
    if not st.session_state.lesson_started:
        st.session_state.lesson_started = True
        st.rerun()
elif transcript_raw == "__scene_select__":
    st.switch_page("pages/scene_select.py")
elif transcript_raw and isinstance(transcript_raw, str) and transcript_raw.strip():
    h = hashlib.md5(transcript_raw.encode()).hexdigest()
    if h != st.session_state.last_id:
        st.session_state.last_id        = h
        st.session_state.pending_student = transcript_raw.strip()
        st.session_state.avatar_thinking = True
        st.rerun()

# ── Pipeline ───────────────────────────────────────────────────────────────────

student_text = st.session_state.get("pending_student")
if student_text:
    st.session_state.pending_student = None
    st.session_state.pipeline_error  = None
    try:
        all_chunks     = []
        raw_tutor_text = ""

        for raw_tutor_text, chunk_b64 in run_pipeline_stream(
                system, student_text, st.session_state.chat, voice_id,
                CLAUDE_KEY, ELEVEN_KEY, model=model_id,
                use_structured=bool(script)):
            if chunk_b64:
                all_chunks.append(chunk_b64)

        tutor_text, has_ok, scene_done = parse_claude_response(raw_tutor_text)
        # Safety: Claude cannot declare scene done before all questions are answered
        if scene_done and script and interaction_idx + 1 < len(script):
            scene_done = False

        st.session_state.chat.extend([
            {"role": "user",      "content": student_text},
            {"role": "assistant", "content": tutor_text},
        ])
        st.session_state.avatar_thinking = False
        st.session_state.last_chunks     = all_chunks
        st.session_state.last_response   = (student_text, tutor_text)
        if all_chunks:
            st.session_state.tutor_play_seq += 1  # new seq → component always detects new audio

        # ── Log: accepted student answer (char question already logged when TTS loaded) ─
        if has_ok and char_question:
            st.session_state.correct_log.append({"who": "student", "text": student_text})

        # ── Advance interaction ────────────────────────────────────────────────
        if script and has_ok and interaction_idx < len(script):
            new_idx = interaction_idx + 1
            if new_idx >= len(script):
                st.session_state.scene_celebration = True
                st.session_state.interaction_idx   = new_idx

                if st.session_state.scene_idx < 4 and FAL_KEY:
                    next_prompt = SCENE_NEXT_PROMPT.get(sk, "")
                    if next_prompt:
                        st.session_state.scene_loading = True
                        generate_scene_image(next_prompt, FAL_KEY,
                                             _make_image_ready_cb(next_prompt, reset_interaction=True))
            else:
                st.session_state.interaction_idx = new_idx

        elif not script and scene_done:
            if st.session_state.scene_idx < 4 and FAL_KEY:
                next_prompt = SCENE_NEXT_PROMPT.get(sk, "")
                if next_prompt:
                    st.session_state.scene_loading = True
                    generate_scene_image(next_prompt, FAL_KEY,
                                         _make_image_ready_cb(next_prompt))

    except Exception as e:
        st.session_state.avatar_thinking = False
        st.session_state.pipeline_error  = str(e)
        st.session_state.last_chunks     = None

    # CRITICAL: rerun so component receives new chunks / clears thinking state
    st.rerun()
