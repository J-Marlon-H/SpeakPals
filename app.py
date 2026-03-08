# Danish Tutor

import streamlit as st
import streamlit.components.v1 as components
import requests, urllib3, base64, json, re, concurrent.futures, hashlib
import pathlib
from dotenv import load_dotenv
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv("keys.env")

CLAUDE_KEY = os.getenv("CLAUDE_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_EN   = "21m00Tcm4TlvDq8ikWAM"
VOICE_DA   = "pNInz6obpgDQGcFmaJgB"

@st.cache_resource
def get_session():
    s = requests.Session()
    s.verify = False
    s.mount("https://", requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=1))
    return s

def clean_for_tts(text):
    text = re.sub(r'[*_~`#]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()

def tts_chunk(text, voice_id):
    r = get_session().post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={"text": text.strip(), "model_id": "eleven_turbo_v2",
              "voice_settings": {"stability": 0.4, "similarity_boost": 0.75}},
        stream=True, timeout=30,
    )
    r.raise_for_status()
    return b"".join(r.iter_content(4096))

def run_pipeline(system, user_input, history, voice_id):
    sess = get_session()
    messages = [{"role": m["role"], "content": m["content"]}
                for m in history if m["role"] in {"user","assistant"} and m["content"]]
    messages.append({"role": "user", "content": user_input})
    resp = sess.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        json={"model": "claude-sonnet-4-6", "max_tokens": 120, "temperature": 0.3,
              "stream": True, "system": system, "messages": messages},
        stream=True, timeout=30,
    )
    resp.raise_for_status()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
    ordered, buf, idx = [], "", 0
    def submit(text):
        nonlocal idx
        t = clean_for_tts(text)
        if len(t) > 1:
            ordered.append((idx, t, executor.submit(tts_chunk, t, voice_id)))
            idx += 1
    for raw in resp.iter_lines():
        if not raw: continue
        line = raw.decode() if isinstance(raw, bytes) else raw
        if not line.startswith("data: "): continue
        payload = line[6:]
        if payload.strip() in ("[DONE]", ""): continue
        try: ev = json.loads(payload)
        except: continue
        if ev.get("type") == "content_block_delta":
            buf += ev.get("delta", {}).get("text", "")
            while re.search(r'[.!?,;]\s', buf):
                m = re.search(r'[.!?,;]\s', buf)
                submit(buf[:m.end()]); buf = buf[m.end():]
            if len(buf.split()) > 2 and buf.endswith(" "):
                submit(buf); buf = ""
    if buf.strip(): submit(buf)
    executor.shutdown(wait=True)
    results = sorted(ordered, key=lambda x: x[0])
    return (" ".join(t for _,t,_ in results),
            [base64.b64encode(f.result()).decode() for _,_,f in results])

def stt(audio_bytes, lang):
    r = get_session().post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": ELEVEN_KEY},
        files={"file": ("input.webm", audio_bytes, "audio/webm")},
        data={"model_id": "scribe_v1", "language_code": lang},
        timeout=20,
    )
    r.raise_for_status()
    t = r.json().get("text") or r.json().get("transcript") or ""
    if not t: raise RuntimeError("No transcript")
    return t

def warmup_claude(system, history):
    try:
        msgs = [{"role": m["role"], "content": m["content"]}
                for m in history[-4:] if m["role"] in {"user","assistant"} and m["content"]]
        msgs.append({"role": "user", "content": "..."})
        get_session().post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 1, "stream": False, "system": system, "messages": msgs},
            timeout=5,
        )
    except: pass

PROMPT_EN = """You are a warm Danish tutor for beginners (A1-B1). Respond conversationally in English with Danish examples.
Student: {name} | Level: {level} | Known mistakes: {mistakes} | Topics: {covered} | Today: {today}
Rules: Max 2-3 short sentences. Natural tone. Always end with a question."""

PROMPT_DA = """Du er en venlig dansk sprogunderviser (A1-B1).
Elev: {name} | Niveau: {level} | Fejl: {mistakes} | Emner: {covered} | I dag: {today}
Regler: Max 2-3 korte saetninger. Naturlig tone. Afslut ALTID med sporgsmaal."""


# Component served from vad_component/index.html — works locally and on Streamlit Cloud
_component_dir = pathlib.Path(__file__).parent / "vad_component"
mic = components.declare_component("vad_mic", path=str(_component_dir))

def avatar_html(chunks=None, thinking=False):
    clips = chunks or []
    audio_tags = "\n".join(
        f'<audio id="c{i}" src="data:audio/mpeg;base64,{b}" preload="auto"></audio>'
        for i, b in enumerate(clips))
    chain_js = ""
    if clips:
        chain_js = f"""
const clips = Array.from({{length:{len(clips)}}}, (_,i) => document.getElementById('c'+i));
function playNext(i) {{
  if (i >= clips.length) {{ idle(); return; }}
  speak();
  clips[i].play().catch(e => playNext(i+1));
  clips[i].onended = () => playNext(i+1);
}}
setTimeout(() => playNext(0), 100);"""
    dot_d = "flex" if thinking else "none"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:transparent;display:flex;justify-content:center;align-items:center;height:100vh;overflow:hidden}}
.scene{{display:flex;flex-direction:column;align-items:center;gap:10px}}
.blob{{position:absolute;width:240px;height:240px;border-radius:60% 40% 55% 45%/50% 55% 45% 50%;
  background:linear-gradient(135deg,#e0e9ff,#f5e6ff);animation:blobmorph 6s ease-in-out infinite;z-index:0}}
@keyframes blobmorph{{0%,100%{{border-radius:60% 40% 55% 45%/50% 55% 45% 50%}}
  33%{{border-radius:45% 55% 40% 60%/55% 40% 60% 45%}}
  66%{{border-radius:55% 45% 60% 40%/40% 60% 50% 55%}}}}
svg{{position:relative;z-index:1}}
@keyframes breathe{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
.head{{animation:breathe 3.5s ease-in-out infinite}}
@keyframes blink{{0%,92%,100%{{transform:scaleY(1)}}96%{{transform:scaleY(0.05)}}}}
.eyes{{animation:blink 5s ease-in-out infinite;transform-origin:center 178px}}
@keyframes talk{{0%,100%{{d:path("M 165 292 Q 200 300 235 292 Q 200 316 165 292 Z")}}
  40%{{d:path("M 167 287 Q 200 274 233 287 Q 200 323 167 287 Z")}}}}
.mouth.on{{animation:talk 0.2s ease-in-out infinite}}
@keyframes dot{{0%,80%,100%{{opacity:.2;transform:translateY(0)}}40%{{opacity:1;transform:translateY(-5px)}}}}
.dots{{display:{dot_d};gap:6px;align-items:center}}
.dots span{{width:7px;height:7px;border-radius:50%;background:#a78bfa;animation:dot 1.1s ease-in-out infinite}}
.dots span:nth-child(2){{animation-delay:.18s}}.dots span:nth-child(3){{animation-delay:.36s}}
.lbl{{font:13px/1 'Segoe UI',sans-serif;color:#94a3b8;letter-spacing:.4px}}
.lbl.s{{color:#818cf8}}
</style></head><body>
{audio_tags}
<div class="scene">
  <div style="position:relative;width:240px;height:240px;display:flex;align-items:center;justify-content:center">
    <div class="blob"></div>
    <svg class="head" width="210" height="210" viewBox="0 0 400 400">
      <ellipse cx="200" cy="138" rx="136" ry="132" fill="#c8956c"/>
      <rect x="168" y="346" width="64" height="48" rx="20" fill="#FECBA1"/>
      <ellipse cx="200" cy="415" rx="168" ry="78" fill="#818cf8"/>
      <ellipse cx="200" cy="208" rx="128" ry="146" fill="#FECBA1"/>
      <ellipse cx="128" cy="256" rx="30" ry="18" fill="#ffb3a7" opacity=".38"/>
      <ellipse cx="272" cy="256" rx="30" ry="18" fill="#ffb3a7" opacity=".38"/>
      <ellipse cx="200" cy="88" rx="136" ry="70" fill="#c8956c"/>
      <ellipse cx="88" cy="168" rx="27" ry="70" fill="#c8956c"/>
      <ellipse cx="312" cy="168" rx="27" ry="70" fill="#c8956c"/>
      <ellipse cx="144" cy="80" rx="54" ry="42" fill="#c8956c"/>
      <ellipse cx="256" cy="80" rx="54" ry="42" fill="#c8956c"/>
      <g class="eyes">
        <ellipse cx="152" cy="178" rx="31" ry="27" fill="white"/>
        <circle cx="152" cy="180" r="18" fill="#5b8dd9"/>
        <circle cx="152" cy="180" r="10" fill="#1a1a2e"/>
        <circle cx="158" cy="173" r="5.5" fill="white"/>
        <circle cx="145" cy="184" r="2.5" fill="white" opacity=".6"/>
        <path d="M120 162 Q152 148 184 162" stroke="#a0522d" stroke-width="5" fill="none" stroke-linecap="round"/>
        <ellipse cx="248" cy="178" rx="31" ry="27" fill="white"/>
        <circle cx="248" cy="180" r="18" fill="#5b8dd9"/>
        <circle cx="248" cy="180" r="10" fill="#1a1a2e"/>
        <circle cx="254" cy="173" r="5.5" fill="white"/>
        <circle cx="241" cy="184" r="2.5" fill="white" opacity=".6"/>
        <path d="M216 162 Q248 148 280 162" stroke="#a0522d" stroke-width="5" fill="none" stroke-linecap="round"/>
      </g>
      <ellipse cx="200" cy="234" rx="9" ry="6" fill="#e8a87c" opacity=".45"/>
      <g class="mouth" id="mouth">
        <path d="M 165 292 Q 200 300 235 292 Q 200 316 165 292 Z" fill="#e05c6a"/>
        <path d="M 165 292 Q 200 286 235 292" fill="#f28b82"/>
        <path d="M 174 293 Q 200 306 226 293" stroke="#c0404e" stroke-width="1.5" fill="none"/>
      </g>
    </svg>
  </div>
  <div class="dots"><span></span><span></span><span></span></div>
  <div class="lbl" id="lbl">{'Thinking...' if thinking else 'Ready'}</div>
</div>
<script>
const mouth=document.getElementById('mouth'),lbl=document.getElementById('lbl');
function speak(){{mouth.classList.add('on');lbl.textContent='Speaking...';lbl.className='lbl s'}}
function idle(){{mouth.classList.remove('on');lbl.textContent='Ready';lbl.className='lbl'}}
{chain_js}
</script></body></html>"""

# ── Page ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Danish Tutor", page_icon="DK", layout="centered",
                   initial_sidebar_state="expanded")

components.html("""<script>
Object.keys(localStorage).forEach(function(k){
  if(k.indexOf('Sidebar')>-1) localStorage.removeItem(k);
});
</script>""", height=0)

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="collapsedControl"]{display:block!important;opacity:1!important;visibility:visible!important;width:2rem!important}
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
    name     = st.text_input("Name", "Alex")
    level    = st.selectbox("Level", ["A1","A2","B1"])
    mistakes = st.text_area("Known mistakes", "heve->har, forgets -et")
    covered  = st.text_area("Topics covered", "family, food")
    today    = st.text_area("Today's topics", "Daily life, shopping")
    st.divider()
    if st.button("Clear chat"):
        for k in ["chat","last_chunks","last_response","last_id"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── State ─────────────────────────────────────────────────────────────────────

for k,v in [("chat",[]),("last_chunks",None),("last_response",None),("last_id",None)]:
    if k not in st.session_state: st.session_state[k] = v

system   = (PROMPT_EN if debug else PROMPT_DA).format(
    name=name, level=level, mistakes=mistakes, covered=covered, today=today)
stt_lang = "en" if debug else "da"
voice_id = VOICE_EN if debug else VOICE_DA

# ── Layout ────────────────────────────────────────────────────────────────────

avatar_slot     = st.empty()
transcript_slot = st.empty()


audio_b64 = mic(key="vad_mic", default=None, height=160)

with st.expander("type instead", expanded=False):
    text_in   = st.text_input("msg", placeholder="Type here...", label_visibility="collapsed")
    send_text = st.button("Send", use_container_width=True)

# ── Detect new audio ──────────────────────────────────────────────────────────

new_audio_b64 = None
if audio_b64 and isinstance(audio_b64, str) and len(audio_b64) > 200:
    h = hashlib.md5(audio_b64.encode()).hexdigest()
    if h != st.session_state.last_id:
        st.session_state.last_id = h
        new_audio_b64 = audio_b64

trigger_text = text_in.strip() if (send_text and text_in.strip()) else None

# ── Pipeline ─────────────────────────────────────────────────────────────────

if new_audio_b64 or trigger_text:
    with avatar_slot:
        components.html(avatar_html(thinking=True), height=310)
    try:
        if new_audio_b64:
            audio_bytes = base64.b64decode(new_audio_b64)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as tex:
                stt_future   = tex.submit(stt, audio_bytes, stt_lang)
                _            = tex.submit(warmup_claude, system, st.session_state.chat)
                student_text = stt_future.result()
        else:
            student_text = trigger_text

        tutor_text, audio_chunks = run_pipeline(system, student_text, st.session_state.chat, voice_id)
        st.session_state.chat.extend([
            {"role":"user",      "content": student_text},
            {"role":"assistant", "content": tutor_text},
        ])
        st.session_state.last_chunks   = audio_chunks
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
                    import time
                    with avatar_slot:
                        components.html(avatar_html(chunks=chunks) + f"<!-- replay-{time.time()} -->",
                                        height=310, scrolling=False)

# ── Conversation history ──────────────────────────────────────────────────────

if st.session_state.chat:
    with st.expander("conversation history", expanded=False):
        for m in st.session_state.chat:
            role  = "You" if m["role"]=="user" else "Tutor"
            color = "#94a3b8" if m["role"]=="user" else "#6d7aad"
            st.markdown(f"<div style='margin:6px 0'><small style='color:{color}'><b>{role}:</b> {m['content']}</small></div>",
                        unsafe_allow_html=True)