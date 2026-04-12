# SpeakPals — Lesson
from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
import hashlib, pathlib, base64
from dotenv import load_dotenv
import os

import json as _json
from pipeline import (run_pipeline_stream, MODELS, VOICES, VOICES_BY_LANG, VOICE_GENDER,
                      SCENE_CATALOG, SETTINGS_DEFAULTS, TTS_LANG_CODE, STT_LANG_CODE,
                      parse_claude_response, generate_scene_image, character_tts_b64)
from prompts import build_system_prompt, get_tutor_name
from ws_proxy import start_in_thread, PROXY_PORT
from db import require_auth, load_knowledge_profile

load_dotenv("keys.env")

def _secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)

CLAUDE_KEY = _secret("CLAUDE_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
FAL_KEY    = _secret("FAL_KEY")

# Opening line per scene — spoken by the character at lesson start (TTS pre-loaded)
SCENE_OPENERS_BY_LANG = {
    "Danish": {
        "meet_a_friend": "Hej! Hvad hedder du?",
        "cafe":          "Hej! Hvad må det være?",
        "supermarket":   "Vil du betale med kort eller kontanter?",
        "flower_store":  "Hej! Hvad kan jeg hjælpe dig med i dag?",
        "bakery":        "Godmorgen! Hvad må det være?",
        "restaurant":    "Goddag og velkommen! Har du reserveret bord?",
    },
    "Portuguese (Brazilian)": {
        "meet_a_friend": "Oi! Qual é o seu nome?",
        "cafe":          "Olá! O que vai ser?",
        "supermarket":   "Vai pagar no débito ou no crédito?",
        "flower_store":  "Oi! Em que posso ajudar você hoje?",
        "bakery":        "Bom dia! O que vai ser?",
        "restaurant":    "Boa tarde e bem-vindo! Tem reserva?",
    },
}

# Gender of the visible character in each scene image
SCENE_CHAR_GENDER = {
    "meet_a_friend": "male",
    "cafe":          "female",
    "supermarket":   "female",
    "flower_store":  "male",
    "bakery":        "female",
    "restaurant":    "male",
}

SCENE_NEXT_PROMPT = {
    "supermarket": (
        "interior of a Danish bakery, a friendly baker facing directly toward you "
        "behind the counter with eye contact, warm morning light, pastries on display"
    )
}

# Build scene lookup from catalog
_SCENE_BY_KEY = {s["key"]: s for s in SCENE_CATALOG}

def _scene_key(_: str) -> str | None:
    return st.session_state.get("selected_scene")

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
    path = pathlib.Path(__file__).parent.parent / "assets" / src
    if not path.exists():
        return src   # fallback: pass raw path (won't render but won't crash)
    data = path.read_bytes()
    mime = "image/jpeg" if src.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode()

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Lesson — SpeakPals", page_icon="DK", layout="wide",
                   initial_sidebar_state="expanded")
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
  [data-testid="collapsedControl"]{display:none!important}
  [data-testid="stSidebarCollapseButton"]{display:none!important}
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stHeader"],header[data-testid="stHeader"],.stAppHeader{
    display:none!important;height:0!important;min-height:0!important}
  [data-testid="stAppViewContainer"]{background:#ffffff}
  /* Sidebar — warm conversation panel, 320px wide */
  [data-testid="stSidebar"]{background:#f5f5f5!important;border-right:1px solid #e5e5e5!important;width:320px!important;min-width:320px!important;color:#111827!important}
  [data-testid="stSidebar"] *{color:#111827!important}
  [data-testid="stSidebar"] section{padding:0!important}
  [data-testid="stSidebar"] .stButton button{
    background:rgba(13,148,136,.1)!important;color:#0d9488!important;
    border:1px solid rgba(13,148,136,.25)!important;border-radius:8px!important;
    font-size:13px!important}
  [data-testid="stSidebar"] .stButton button:hover{background:rgba(13,148,136,.2)!important}
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
  /* Prevent Streamlit from fading/dimming content during reruns */
  [data-stale="true"],[data-stale="true"] *{opacity:1!important;transition:none!important}
  /* Chat message slide-in animation */
  @keyframes msgSlideIn{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:translateX(0)}}
  /* Sidebar scroll area — leaves room for the pinned Home button */
  [data-testid="stSidebar"] > div:first-child{
    padding-bottom:80px!important;overflow-y:auto!important}
  /* Each sidebar element — small gap so bubbles don't collapse */
  [data-testid="stSidebar"] [data-testid="stVerticalBlock"]{
    gap:2px!important;overflow:visible!important}
  /* Pin Back-to-Home button to bottom — keyed so it ONLY matches that button */
  [data-testid="stSidebar"] .st-key-btn_home{
    position:fixed!important;bottom:0!important;left:0!important;
    width:320px!important;padding:10px 16px 14px!important;
    background:#f5f5f5!important;border-top:1px solid #e5e5e5!important;
    z-index:100!important}
</style>""", unsafe_allow_html=True)

# ── Read settings — seed session_state from file if not already set ────────────
_saved = SETTINGS_DEFAULTS.copy()
try:
    _saved.update(_json.loads(pathlib.Path("user_settings.json").read_text(encoding="utf-8")))
except Exception:
    pass
for _k, _v in _saved.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Load knowledge profile once per lesson session
if "knowledge_profile" not in st.session_state:
    if "sb_user_id" in st.session_state:
        st.session_state["knowledge_profile"] = load_knowledge_profile(
            st.session_state.sb_user_id,
            st.session_state.sb_access_token,
        )
    else:
        st.session_state["knowledge_profile"] = {}

name        = st.session_state.get("s_name",        SETTINGS_DEFAULTS["s_name"])
_sel_scene  = st.session_state.get("selected_scene")
level       = _SCENE_BY_KEY[_sel_scene]["level"] if _sel_scene in _SCENE_BY_KEY else "A1"
bg_lang     = st.session_state.get("s_bg_lang",     SETTINGS_DEFAULTS["s_bg_lang"])
voice_label = st.session_state.get("s_voice_label", SETTINGS_DEFAULTS["s_voice_label"])
model_label = st.session_state.get("s_model_label", SETTINGS_DEFAULTS["s_model_label"])
model_id    = MODELS[model_label]
target_lang    = st.session_state.get("s_language", SETTINGS_DEFAULTS["s_language"])
lang_voices    = VOICES_BY_LANG.get(target_lang, VOICES)
tts_lang_code  = TTS_LANG_CODE.get(target_lang, "da")
stt_lang_code  = STT_LANG_CODE.get(target_lang, "da")

# ── Session state ──────────────────────────────────────────────────────────────

for k, v in [
    ("chat", []), ("last_chunks", None), ("last_response", None), ("last_id", None),
    ("scene_images", []), ("scene_idx", 0), ("scene_loading", False),
    ("turn_count", 0), ("opener_loaded", False), ("scene_complete", False), ("char_audio", []),
    ("pipeline_error", None), ("pending_student", None), ("avatar_thinking", False),
    ("correct_log", []), ("coaching_log", []), ("lesson_started", False),
    ("tutor_play_seq", 0), ("char_play_seq", 0), ("replay_char_seq", 0),
    ("stop_audio_seq", 0), ("current_session_id", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Initialise first scene from selected_scene (set by home page) ──────────────

if not st.session_state.scene_images:
    selected = st.session_state.get("selected_scene")
    scene_data = _SCENE_BY_KEY.get(selected) if selected else None
    if scene_data:
        is_free_conv = scene_data.get("free_conv", False)
        st.session_state.scene_images = [{
            "src":         "" if is_free_conv else f"scenes/{scene_data['file']}",
            "description": scene_data["scene_description"],
            "free_conv":   is_free_conv,
        }]
    else:
        st.switch_page("pages/home.py")

# ── Derived scene values ───────────────────────────────────────────────────────

scene_list        = st.session_state.scene_images
current_scene     = scene_list[st.session_state.scene_idx] if scene_list else None
scene_description = current_scene["description"] if current_scene else ""
_scene_src_raw    = current_scene["src"] if current_scene else ""
is_free_conv      = current_scene.get("free_conv", False) if current_scene else False
scene_idx_1based  = st.session_state.scene_idx + 1

# Convert local images to base64; FAL URLs pass through as-is
if _scene_src_raw and not _scene_src_raw.startswith(("http", "data:")):
    scene_src = _scene_to_data_url(_scene_src_raw)
else:
    scene_src = _scene_src_raw  # "" for free conversation — ob_mode handles the background

voice_id = lang_voices[voice_label] if voice_label in lang_voices else next(iter(lang_voices.values()))

_scene_gender = SCENE_CHAR_GENDER.get(st.session_state.get("selected_scene") or "", None)
_same_gender  = [vid for lbl, vid in lang_voices.items()
                 if VOICE_GENDER.get(lbl) == _scene_gender]
char_voice_id = (
    next((v for v in _same_gender if v != voice_id), None)
    or (_same_gender[0] if _same_gender else None)
    or next((v for v in lang_voices.values() if v != voice_id), next(iter(lang_voices.values())))
)

sk          = _scene_key(_scene_src_raw)
char_label  = _SCENE_BY_KEY[sk]["char_name"] if sk and sk in _SCENE_BY_KEY else "Character"
tutor_name  = get_tutor_name(target_lang)
turn_count = st.session_state.turn_count
_lang_openers = SCENE_OPENERS_BY_LANG.get(target_lang, SCENE_OPENERS_BY_LANG["Danish"])
opener_line   = _lang_openers.get(sk, "") if (sk and not is_free_conv) else ""

system = build_system_prompt(
    name, level, bg_lang,
    target_lang=target_lang,
    scene_description=scene_description,
    turn_count=turn_count,
    knowledge_profile=st.session_state.get("knowledge_profile"),
    free_conv=is_free_conv,
)

# Load opener TTS once at lesson start
if (opener_line
        and not st.session_state.opener_loaded
        and ELEVEN_KEY):
    b64 = character_tts_b64(opener_line, char_voice_id, ELEVEN_KEY, lang_code=tts_lang_code)
    if b64:
        st.session_state.char_audio = [b64]
        st.session_state.char_play_seq += 1
    else:
        st.session_state.char_audio = []
    _log = st.session_state.correct_log
    if not any(e["who"] == "character" and e["text"] == opener_line for e in _log):
        _log.append({"who": "character", "text": opener_line})
    st.session_state.opener_loaded = True

# ── Sidebar: conversation log ──────────────────────────────────────────────────

with st.sidebar:
    # Big header + account button
    col_title, col_acct = st.columns([3, 1])
    with col_title:
        st.markdown(
            "<div style='padding:20px 0 0 16px'>"
            "<div style='font:800 18px/1.2 Inter,sans-serif;color:#111827;letter-spacing:-.3px'>Lesson Chat</div>"
            f"<div style='font:500 12px Inter;color:rgba(17,24,39,.55);margin-top:4px'>Scene {scene_idx_1based} · {level} · {name}</div>"
            "</div>",
            unsafe_allow_html=True
        )
    with col_acct:
        st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
        if st.button("⚙", help="Account settings", use_container_width=True):
            st.switch_page("pages/account.py")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='height:1px;background:linear-gradient(90deg,rgba(13,148,136,.3),transparent);margin:4px 16px 0'></div>",
        unsafe_allow_html=True
    )

    # Conversation log — only shown after lesson starts, single HTML block
    log = st.session_state.correct_log
    if not st.session_state.lesson_started:
        st.markdown(
            "<div style='padding:16px;font-size:12px;color:rgba(17,24,39,.45);font-style:italic'>"
            "Press Start Lesson to begin."
            "</div>",
            unsafe_allow_html=True
        )
    elif not log:
        st.markdown(
            "<div style='padding:16px;font-size:12px;color:rgba(17,24,39,.45);font-style:italic'>"
            "Start speaking — your accepted answers will appear here."
            "</div>",
            unsafe_allow_html=True
        )
    else:
        last_i = len(log) - 1
        last_char_i = next((i for i in range(len(log)-1, -1, -1) if log[i]["who"] in ("character", "tutor")), None)
        # Build entire chat as one HTML block to avoid Streamlit element spacing issues
        parts = []
        for i, entry in enumerate(log):
            txt  = entry["text"].replace("<", "&lt;").replace(">", "&gt;")
            anim = "animation:msgSlideIn .4s cubic-bezier(.34,1.56,.64,1) both;" if i == last_i else ""
            if entry["who"] == "character":
                parts.append(
                    f"<div style='padding:8px 12px 4px'>"
                    f"<div style='background:#ffffff;border:1px solid #e5e5e5;border-radius:12px 12px 12px 3px;"
                    f"padding:10px 12px;font-size:13px;line-height:1.5;"
                    f"color:#111827;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Inter;color:#9ca3af;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>{char_label}</span>"
                    f"<em>{txt}</em></div></div>"
                )
            elif entry["who"] == "tutor":
                parts.append(
                    f"<div style='padding:8px 12px 4px'>"
                    f"<div style='background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);border-radius:12px 12px 12px 3px;"
                    f"padding:10px 12px;font-size:13px;line-height:1.5;"
                    f"color:#78350f;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Inter;color:#d97706;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>💡 {tutor_name}</span>"
                    f"{txt}</div></div>"
                )
            else:
                parts.append(
                    f"<div style='padding:4px 12px 8px'>"
                    f"<div style='background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.2);border-radius:12px 12px 3px 12px;"
                    f"padding:10px 12px;font-size:13px;line-height:1.5;"
                    f"color:#0f3d39;word-break:break-word;{anim}'>"
                    f"<span style='font:600 10px Inter;color:#0d9488;display:block;margin-bottom:4px;letter-spacing:.5px;text-transform:uppercase'>You ✓</span>"
                    f"{txt}</div></div>"
                )
        st.markdown("".join(parts), unsafe_allow_html=True)
        # Replay button rendered separately after the chat block
        if last_char_i is not None and st.session_state.char_audio:
            _, rb = st.columns([5, 1])
            with rb:
                if st.button("↺", key=f"rch_{last_char_i}",
                             help=f"Replay {char_label.lower()}",
                             use_container_width=True):
                    st.session_state.replay_char_seq += 1
                    st.rerun()

    # Error debug
    if st.session_state.get("pipeline_error"):
        st.markdown(f"<div style='margin:8px 12px;padding:8px 10px;background:rgba(220,38,38,.08);border-radius:8px;color:#dc2626;font-size:11px;word-break:break-word'>⚠ {st.session_state.pipeline_error}</div>", unsafe_allow_html=True)

    # Feedback CTA — prominent when scene is complete, plain when just available
    if st.session_state.get("scene_complete"):
        st.markdown(
            "<div style='margin:10px 12px;padding:14px 16px;"
            "background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.3);"
            "border-radius:12px;font:500 12px Inter;color:#0d9488;line-height:1.5'>"
            "Great session! Head to the feedback page to review what I noted.</div>",
            unsafe_allow_html=True
        )
        if st.button("View Feedback →", type="primary", use_container_width=True):
            st.switch_page("pages/feedback.py")
    elif st.session_state.get("turn_count", 0) >= 1:
        st.markdown("<div style='height:1px;background:rgba(17,24,39,.1);margin:8px 12px'></div>", unsafe_allow_html=True)
        if st.button("Finish Lesson", type="primary", use_container_width=True):
            st.switch_page("pages/feedback.py")

    # Back to Home — always last → pinned to bottom by CSS (.st-key-btn_home)
    if st.button("🏠 Back to Home", key="btn_home", use_container_width=True):
        st.switch_page("pages/home.py")

# ── VAD / scene component ──────────────────────────────────────────────────────

def _make_image_ready_cb(next_prompt):
    def _cb(url):
        if url:
            st.session_state.scene_images.append({"description": next_prompt, "src": url})
            st.session_state.scene_idx  += 1
            st.session_state.turn_count  = 0
            st.session_state.opener_loaded = False
        st.session_state.scene_loading = False
    return _cb

from vad_helper import mic

chunks  = st.session_state.last_chunks or []
caption = ("Generating next scene…" if st.session_state.scene_loading
           else f"Scene {scene_idx_1based}")

def _scribe_token(eleven_key):
    """Fetch a fresh single-use token for the ElevenLabs Scribe WS.
    Must NOT be cached — tokens are consumed on first WS connection."""
    if not eleven_key:
        return None
    try:
        import requests as _req
        r = _req.post(
            "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
            headers={"xi-api-key": eleven_key},
            timeout=8,
        )
        r.raise_for_status()
        return r.json().get("token")
    except Exception:
        return None

mic_props = dict(
    lang              = stt_lang_code,
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
    progress_current  = 0,
    progress_total    = 0,
    ob_mode           = is_free_conv,   # light bg + centred avatar for free conversation
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
        last_speaker   = "character"

        for raw_tutor_text, chunk_b64, last_speaker in run_pipeline_stream(
                system, student_text, st.session_state.chat, voice_id,
                CLAUDE_KEY, ELEVEN_KEY, model=model_id,
                use_structured=True, lang_code=tts_lang_code,
                char_voice_id=char_voice_id):
            if chunk_b64:
                all_chunks.append(chunk_b64)

        tutor_text, has_ok, scene_done, is_correct, correction_note, speaker = parse_claude_response(raw_tutor_text)

        st.session_state.chat.extend([
            {"role": "user",      "content": student_text},
            {"role": "assistant", "content": tutor_text},
        ])
        st.session_state.avatar_thinking = False
        st.session_state.last_response   = (student_text, tutor_text)

        # ── Route audio: free conv always goes to tutor avatar ───────────────
        if all_chunks:
            if is_free_conv or last_speaker != "character":
                st.session_state.last_chunks    = all_chunks
                st.session_state.tutor_play_seq += 1
            else:
                st.session_state.char_audio    = all_chunks
                st.session_state.char_play_seq += 1
                st.session_state.last_chunks   = None

        # ── Determine last character line (for coaching log context) ──────────
        _last_char = next(
            (e["text"] for e in reversed(st.session_state.correct_log) if e["who"] == "character"),
            ""
        )

        # ── Always log student turn — conversation is never blocked ───────────
        st.session_state.correct_log.append({"who": "student", "text": student_text})
        st.session_state.turn_count += 1
        if tutor_text and not scene_done:
            st.session_state.correct_log.append({"who": speaker, "text": tutor_text})

        # ── Log mistakes silently for the feedback page ───────────────────────
        # Only log when the CHARACTER responded — that means the student was
        # speaking Danish. When the TUTOR responds, the student was speaking
        # English intentionally, so there is nothing to log.
        if not is_correct and correction_note and speaker == "character":
            st.session_state.coaching_log.append({
                "question":   _last_char,
                "attempt":    student_text,
                "correction": correction_note,
                "bg_lang":    bg_lang,
            })

        # ── Handle scene done ─────────────────────────────────────────────────
        if scene_done:
            st.session_state.scene_complete = True
            if not is_free_conv and st.session_state.scene_idx < 4 and FAL_KEY:
                next_prompt = SCENE_NEXT_PROMPT.get(sk, "")
                if next_prompt:
                    st.session_state.scene_loading = True
                    generate_scene_image(next_prompt, FAL_KEY,
                                         _make_image_ready_cb(next_prompt))

    except Exception as e:
        st.session_state.avatar_thinking = False
        st.session_state.pipeline_error  = str(e)
        st.session_state.last_chunks     = None

    st.rerun()
