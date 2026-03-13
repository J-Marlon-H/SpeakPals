import requests, urllib3, base64, json, re, time, threading
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@st.cache_resource
def get_session():
    s = requests.Session()
    s.verify = False
    s.mount("https://", requests.adapters.HTTPAdapter(
        pool_connections=10, pool_maxsize=10, max_retries=1))
    return s


def clean_for_tts(text):
    text = re.sub(r'<ok\s*/>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[*_~`#]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


def tts_chunk(text, voice_id, eleven_key):
    for attempt in range(3):
        r = get_session().post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            headers={"xi-api-key": eleven_key, "Content-Type": "application/json"},
            json={"text": text.strip(), "model_id": "eleven_turbo_v2_5",
                  "language_code": "da",
                  "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "speed": 0.92}},
            stream=True, timeout=30,
        )
        if r.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        return b"".join(r.iter_content(4096))
    r.raise_for_status()


MODELS = {
    "Sonnet 4.6 — best quality": "claude-sonnet-4-6",
    "Haiku 4.5 — fastest":       "claude-haiku-4-5-20251001",
}

VOICES = {
    "Mathias — male baritone": "ygiXC2Oa1BiHksD3WkJZ",
    "Camilla — female":        "4RklGmuxoAskAbGXplXN",
    "Casper — male, calm":     "ADRrvIX3j1uTFlD5q6DE",
}

# ── Scene catalog — single source of truth for all scenes ──────────────────────
SCENE_CATALOG = [
    {
        "key":         "meet_a_friend",
        "level":       "A1",
        "title":       "Meet a Friend",
        "desc":        "Introduce yourself and get to know someone in Danish",
        "file":        "meet_a_friend.png",
        "gradient":    "linear-gradient(135deg,#064e3b,#065f46)",
        "char_name":   "Friend",
        "scene_description": "A friendly young Dane smiling at you in a sunny park, ready to chat and get to know you",
    },
    {
        "key":         "cafe",
        "level":       "A1",
        "title":       "At the Café",
        "desc":        "Order a coffee and have a short chat with the barista",
        "file":        "cafe.png",
        "gradient":    "linear-gradient(135deg,#451a03,#78350f)",
        "char_name":   "Barista",
        "scene_description": "A cosy Danish café — the barista is at the counter with coffee cups and pastries, ready to take your order",
    },
    {
        "key":         "supermarket",
        "level":       "A1",
        "title":       "Supermarket Checkout",
        "desc":        "Pay for your groceries and chat with the cashier",
        "file":        "supermarket_cashier.png",
        "gradient":    "linear-gradient(135deg,#1e3a8a,#312e81)",
        "char_name":   "Cashier",
        "scene_description": "Danish supermarket checkout — the cashier is facing you, ready to scan your items",
    },
    {
        "key":         "flower_store",
        "level":       "A2",
        "title":       "At the Flower Shop",
        "desc":        "Buy flowers and chat with the florist in Danish",
        "file":        "flower_store.png",
        "gradient":    "linear-gradient(135deg,#4a1942,#831843)",
        "char_name":   "Florist",
        "scene_description": "Danish flower shop — the florist is behind the counter, surrounded by colourful flowers, ready to help you",
    },
    {
        "key":         "bakery",
        "level":       "A2",
        "title":       "At the Bakery",
        "desc":        "Order pastries and bread from the baker in Danish",
        "file":        "bakery.png",
        "gradient":    "linear-gradient(135deg,#78350f,#92400e)",
        "char_name":   "Baker",
        "scene_description": "Danish bakery — the baker is at the counter with fresh pastries and bread on display",
    },
    {
        "key":         "restaurant",
        "level":       "B1",
        "title":       "At the Restaurant",
        "desc":        "Order a meal and interact with the waiter in Danish",
        "file":        "restaurant.png",
        "gradient":    "linear-gradient(135deg,#7c2d12,#9a3412)",
        "char_name":   "Waiter",
        "scene_description": "Danish restaurant — a waiter is at your table, ready to take your order",
    },
]

# Session state keys that belong to one lesson — cleared when starting a new one
LESSON_STATE_KEYS = [
    "chat", "last_chunks", "last_response", "last_id",
    "scene_images", "scene_idx", "scene_loading",
    "interaction_idx", "char_audio",
    "scene_celebration", "char_loaded_for",
    "pipeline_error", "pending_student", "avatar_thinking",
    "correct_log", "lesson_started", "tutor_play_seq", "char_play_seq",
    "replay_char_seq",
]

# ── Structured output schema ────────────────────────────────────────────────────

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict":    {"type": "string", "enum": ["accept", "coach"]},
        "text":       {"type": "string"},
        "scene_done": {"type": "boolean"},
    },
    "required": ["verdict", "text", "scene_done"],
    "additionalProperties": False,
}


def run_pipeline_stream(system, user_input, history, voice_id, claude_key, eleven_key,
                        model="claude-sonnet-4-6", use_structured=False):
    """Generator: yields (raw_claude_text, chunk_b64).
    Streams Claude fully, then makes a single TTS call for the complete response.
    When use_structured=True, enforces VERDICT_SCHEMA via the structured outputs API
    and extracts the "text" field for TTS (not the raw JSON).
    """
    sess = get_session()
    messages = [{"role": m["role"], "content": m["content"]}
                for m in history if m["role"] in {"user", "assistant"} and m["content"]]
    messages.append({"role": "user", "content": user_input})

    body = {
        "model": model, "max_tokens": 220, "temperature": 0.3,
        "stream": True, "system": system, "messages": messages,
    }
    if use_structured:
        body["output_config"] = {
            "format": {"type": "json_schema", "schema": VERDICT_SCHEMA}
        }

    resp = sess.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json=body,
        stream=True, timeout=30,
    )
    resp.raise_for_status()

    raw_claude = ""
    for raw in resp.iter_lines():
        if not raw:
            continue
        line = raw.decode() if isinstance(raw, bytes) else raw
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload.strip() in ("[DONE]", ""):
            continue
        try:
            ev = json.loads(payload)
        except Exception:
            continue
        if ev.get("type") == "content_block_delta":
            raw_claude += ev.get("delta", {}).get("text", "")

    # Extract spoken text for TTS — use JSON "text" field if structured, else full text
    tts_text = None
    if use_structured:
        try:
            obj = json.loads(raw_claude.strip())
            spoken = str(obj.get("text", "")).strip()
            if spoken:
                tts_text = clean_for_tts(spoken)
        except Exception:
            pass

    if tts_text is None:
        tts_text = clean_for_tts(raw_claude)

    if tts_text:
        audio = tts_chunk(tts_text, voice_id, eleven_key)
        yield raw_claude, base64.b64encode(audio).decode()
    else:
        yield raw_claude, ""


# ── Response parsing ────────────────────────────────────────────────────────────

_SCENE_RE  = re.compile(r'<scene>(.*?)</scene>', re.DOTALL)
_OK_RE     = re.compile(r'<ok\s*/>', re.IGNORECASE)
_OK_AT_END = re.compile(r'<ok\s*/>\s*$', re.IGNORECASE)

_IMAGE_STYLE = (
    "photorealistic, ultra-realistic, first-person immersive view, "
    "person facing directly toward the viewer with full eye contact, "
    "as if someone is looking right at you and waiting for a response, "
    "realistic Danish everyday setting, natural lighting, "
    "no text, no labels, "
)


def strip_ok_tag(text: str) -> tuple[str, bool]:
    """Return (clean_text, has_ok). Kept for fallback path."""
    has_ok = bool(_OK_AT_END.search(text.strip()))
    return _OK_RE.sub('', text).strip(), has_ok


def strip_scene_tag(text: str) -> tuple[str, str | None]:
    """Return (clean_text, scene_directive_or_None). Kept for fallback path."""
    m = _SCENE_RE.search(text)
    directive = m.group(1).strip() if m else None
    clean = _SCENE_RE.sub("", text).strip()
    return clean, directive


_VERDICT_RE = re.compile(r'"verdict"\s*:\s*"(accept|coach)"', re.IGNORECASE)
_TEXT_RE    = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"')
_DONE_RE    = re.compile(r'"scene_done"\s*:\s*(true|false)', re.IGNORECASE)


def parse_claude_response(raw: str) -> tuple[str, bool, bool]:
    """Parse Claude's response. Returns (spoken_text, has_ok, scene_done).
    1. Try full JSON parse (structured output, guaranteed valid)
    2. Try regex extraction (malformed JSON but right fields)
    3. Fall back to <ok/> token + <scene> tag (legacy plain text)
    """
    stripped = raw.strip()

    # ── Attempt 1: full JSON parse ──────────────────────────────────────────
    try:
        obj        = json.loads(stripped)
        verdict    = str(obj.get("verdict", "")).lower()
        text       = str(obj.get("text", "")).strip()
        scene_done = bool(obj.get("scene_done", False))
        if verdict in ("accept", "coach") and text:
            return text, verdict == "accept", scene_done
    except Exception:
        pass

    # ── Attempt 2: regex field extraction (handles extra prose around JSON) ─
    v_match = _VERDICT_RE.search(stripped)
    t_match = _TEXT_RE.search(stripped)
    if v_match and t_match:
        verdict    = v_match.group(1).lower()
        text       = t_match.group(1).replace('\\"', '"').replace("\\n", " ").strip()
        d_match    = _DONE_RE.search(stripped)
        scene_done = d_match and d_match.group(1).lower() == "true" if d_match else False
        return text, verdict == "accept", bool(scene_done)

    # ── Attempt 3: legacy plain-text with <ok/> / <scene> tags ─────────────
    raw_no_scene, scene_directive = strip_scene_tag(stripped)
    text, has_ok = strip_ok_tag(raw_no_scene)
    return text, has_ok, bool(scene_directive)


def character_tts_b64(text: str, voice_id: str, eleven_key: str) -> str | None:
    """Synthesize a short line with the given voice; returns base64 string or None."""
    try:
        audio = tts_chunk(text, voice_id, eleven_key)
        return base64.b64encode(audio).decode()
    except Exception:
        return None


def generate_scene_image(scene_prompt: str, fal_key: str, callback) -> None:
    """Spawn a background thread; calls callback(url: str) when the image is ready."""
    def _run():
        import os
        os.environ["FAL_KEY"] = fal_key
        try:
            import fal_client
            result = fal_client.run(
                "fal-ai/flux/schnell",
                arguments={
                    "prompt": _IMAGE_STYLE + scene_prompt,
                    "image_size": "landscape_16_9",
                    "num_images": 1,
                },
            )
            url = result["images"][0]["url"]
            callback(url)
        except Exception:
            callback(None)
    threading.Thread(target=_run, daemon=True).start()
