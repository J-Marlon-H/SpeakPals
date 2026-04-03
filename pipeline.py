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


def tts_chunk(text, voice_id, eleven_key, lang_code="da"):
    for attempt in range(3):
        r = get_session().post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            headers={"xi-api-key": eleven_key, "Content-Type": "application/json"},
            json={"text": text.strip(), "model_id": TTS_MODEL.get(lang_code, "eleven_turbo_v2_5"),
                  "language_code": lang_code,
                  "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "speed": 0.92}},
            stream=True, timeout=30,
        )
        if r.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        return b"".join(r.iter_content(4096))
    r.raise_for_status()


def generate_language_tip(conversation_lines: list, bg_lang: str, claude_key: str,
                          model: str = "claude-haiku-4-5-20251001") -> str:
    """Generate a conversation-specific language tip for a given background language.
    Returns plain text (2-3 sentences). Raises on API error."""
    conv_text = "\n".join(
        f"{'Character' if e['who'] == 'character' else 'Student'}: {e['text']}"
        for e in conversation_lines
    )
    prompt = (
        f"A student whose native language is {bg_lang} just completed this short Danish conversation:\n\n"
        f"{conv_text}\n\n"
        f"Write a short tip (2–3 sentences max) specifically for {bg_lang} speakers, based only on "
        f"the words that appear in this conversation. Focus on: cognates (Danish words that look or "
        f"sound similar to {bg_lang}), false friends, or notable pronunciation differences. "
        f"Reference specific words from the conversation. Plain text only — no markdown, no bullet points."
    )
    r = get_session().post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": model, "max_tokens": 150, "temperature": 0.5,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


def extract_vocabulary(conversation_lines: list, bg_lang: str, level: str,
                       claude_key: str, model: str = "claude-haiku-4-5-20251001") -> list:
    """Extract key vocab from conversation.
    Returns list of {word, translation, example} dicts (4–6 items)."""
    conv_text = "\n".join(
        f"{'Character' if e['who'] == 'character' else 'Student'}: {e['text']}"
        for e in conversation_lines
    )
    prompt = (
        f"From this Danish conversation (student level: {level}, native language: {bg_lang}):\n\n"
        f"{conv_text}\n\n"
        f"Extract 4–6 useful Danish words or short phrases a beginner should practice. "
        f"Prefer content words (nouns, verbs, useful phrases). Skip bare filler like 'ja' or 'hej' "
        f"unless there is a genuine nuance worth noting for {bg_lang} speakers. "
        f"For each word provide:\n"
        f"  - 'word': the Danish word/phrase as it appeared\n"
        f"  - 'translation': concise English translation\n"
        f"  - 'example': a short new Danish sentence (5–8 words) using this word — "
        f"different from the conversation, appropriate for {level} level\n\n"
        f"Reply with a JSON array only, no other text:\n"
        f'[{{"word":"...","translation":"...","example":"..."}}]'
    )
    r = get_session().post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": model, "max_tokens": 500, "temperature": 0.4,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=20,
    )
    r.raise_for_status()
    raw = r.json()["content"][0]["text"].strip()
    # Strip markdown code fences Claude sometimes adds (```json ... ```)
    raw = re.sub(r'^```[a-z]*\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


SETTINGS_DEFAULTS = {
    "s_name":        "Marlon",
    "s_level":       "A1",
    "s_bg_lang":     "German",
    "s_language":    "Danish",
    "s_voice_label": "Mathias — male baritone",
    "s_model_label": "Haiku 4.5 — fastest",
}

MODELS = {
    "Sonnet 4.6 — best quality": "claude-sonnet-4-6",
    "Haiku 4.5 — fastest":       "claude-haiku-4-5-20251001",
}

VOICES = {
    "Mathias — male baritone": "ygiXC2Oa1BiHksD3WkJZ",
    "Camilla — female":        "4RklGmuxoAskAbGXplXN",
    "Søren — male, calm":      "xj6X4BCUsv9oxohm1E8o",
}

# Per-language voice menus
VOICES_BY_LANG = {
    "Danish": VOICES,
    "Portuguese (Brazilian)": {
        "Matheus — male baritone": "36rVQA1AOIPwpA3Hg1tC",
        "Camila — female":         "4RklGmuxoAskAbGXplXN",
        "Flavio — male, calm":     "x6uRgOliu4lpcrqMH3s1",
    },
}

TTS_LANG_CODE = {
    "Danish":                 "da",
    "Portuguese (Brazilian)": "pt",
}

STT_LANG_CODE = {
    "Danish":                 "da",
    "Portuguese (Brazilian)": "por",
}

TTS_MODEL = {
    "da": "eleven_turbo_v2_5",
    "pt": "eleven_turbo_v2_5",
}

# ── Scene catalog — single source of truth for all scenes ──────────────────────
SCENE_CATALOG = [
    {
        "key":         "meet_a_friend",
        "level":       "A1",
        "title":       "Meet a Friend",
        "desc":        "Introduce yourself and get to know someone in Danish",
        "file":        "friend.jpg",
        "gradient":    "linear-gradient(135deg,#064e3b,#065f46)",
        "char_name":   "Friend",
        "scene_description": "A friendly young Dane smiling at you in a sunny park, ready to chat and get to know you",
    },
    {
        "key":         "cafe",
        "level":       "A1",
        "title":       "At the Café",
        "desc":        "Order a coffee and have a short chat with the barista",
        "file":        "cafe.jpg",
        "gradient":    "linear-gradient(135deg,#451a03,#78350f)",
        "char_name":   "Barista",
        "scene_description": "A cosy Danish café — the barista is at the counter with coffee cups and pastries, ready to take your order",
    },
    {
        "key":         "supermarket",
        "level":       "A1",
        "title":       "Supermarket Checkout",
        "desc":        "Pay for your groceries and chat with the cashier",
        "file":        "supermarket_cashier.jpg",
        "gradient":    "linear-gradient(135deg,#1e3a8a,#312e81)",
        "char_name":   "Cashier",
        "scene_description": "Danish supermarket checkout — the cashier is facing you, ready to scan your items",
    },
    {
        "key":         "flower_store",
        "level":       "A2",
        "title":       "At the Flower Shop",
        "desc":        "Buy flowers and chat with the florist in Danish",
        "file":        "flower_store.jpg",
        "gradient":    "linear-gradient(135deg,#4a1942,#831843)",
        "char_name":   "Florist",
        "scene_description": "Danish flower shop — the florist is behind the counter, surrounded by colourful flowers, ready to help you",
    },
    {
        "key":         "bakery",
        "level":       "A2",
        "title":       "At the Bakery",
        "desc":        "Order pastries and bread from the baker in Danish",
        "file":        "bakery.jpg",
        "gradient":    "linear-gradient(135deg,#78350f,#92400e)",
        "char_name":   "Baker",
        "scene_description": "Danish bakery — the baker is at the counter with fresh pastries and bread on display",
    },
    {
        "key":         "restaurant",
        "level":       "B1",
        "title":       "At the Restaurant",
        "desc":        "Order a meal and interact with the waiter in Danish",
        "file":        "restaurant.jpg",
        "gradient":    "linear-gradient(135deg,#7c2d12,#9a3412)",
        "char_name":   "Waiter",
        "scene_description": "Danish restaurant — a waiter is at your table, ready to take your order",
    },
]

# Session state keys that belong to one lesson — cleared when starting a new one
LESSON_STATE_KEYS = [
    "chat", "last_chunks", "last_response", "last_id",
    "scene_images", "scene_idx", "scene_loading",
    "turn_count", "opener_loaded", "scene_complete", "char_audio",
    "pipeline_error", "pending_student", "avatar_thinking",
    "correct_log", "coaching_log", "lesson_started",
    "tutor_play_seq", "char_play_seq", "replay_char_seq",
    "current_session_id",
]

# ── Structured output schema ────────────────────────────────────────────────────

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict":    {"type": "string", "enum": ["accept"]},
        "speaker":    {"type": "string", "enum": ["character", "tutor"]},
        "text":       {"type": "string"},
        "scene_done": {"type": "boolean"},
        "correct":    {"type": "boolean"},
        "correction": {"type": "string"},
    },
    "required": ["verdict", "speaker", "text", "scene_done", "correct"],
    "additionalProperties": False,
}


def run_pipeline_stream(system, user_input, history, voice_id, claude_key, eleven_key,
                        model="claude-sonnet-4-6", use_structured=False, lang_code="da",
                        char_voice_id=None):
    """Generator: yields (raw_claude_text, chunk_b64, speaker).
    Streams Claude fully, then makes a single TTS call for the complete response.
    When use_structured=True, enforces VERDICT_SCHEMA via the structured outputs API,
    extracts the "text" field for TTS, and picks the voice based on "speaker":
    "character" → char_voice_id (falls back to voice_id); "tutor" → voice_id.
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

    # Extract spoken text and speaker — use JSON fields if structured, else full text
    tts_text = None
    speaker = "character"
    if use_structured:
        try:
            obj = json.loads(raw_claude.strip())
            spoken = str(obj.get("text", "")).strip()
            if spoken:
                tts_text = clean_for_tts(spoken)
            speaker = obj.get("speaker", "character")
        except Exception:
            pass

    if tts_text is None:
        tts_text = clean_for_tts(raw_claude)

    # Pick voice and lang: character uses char_voice_id + target lang; tutor uses voice_id + English
    tts_voice    = (char_voice_id or voice_id) if speaker == "character" else voice_id
    tts_lang     = lang_code if speaker == "character" else "en"

    if tts_text:
        audio = tts_chunk(tts_text, tts_voice, eleven_key, lang_code=tts_lang)
        yield raw_claude, base64.b64encode(audio).decode(), speaker
    else:
        yield raw_claude, "", speaker


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


_CORRECT_RE    = re.compile(r'"correct"\s*:\s*(true|false)', re.IGNORECASE)
_CORRECTION_RE = re.compile(r'"correction"\s*:\s*"((?:[^"\\]|\\.)*)"')
_SPEAKER_RE    = re.compile(r'"speaker"\s*:\s*"(character|tutor)"', re.IGNORECASE)


def parse_claude_response(raw: str) -> tuple[str, bool, bool, bool, str, str]:
    """Parse Claude's response.
    Returns (spoken_text, has_ok, scene_done, is_correct, correction_note, speaker).
    has_ok is always True — the tutor never blocks the conversation flow.
    speaker is "character" or "tutor".
    """
    stripped = raw.strip()

    # ── Attempt 1: full JSON parse ──────────────────────────────────────────
    try:
        obj        = json.loads(stripped)
        text       = str(obj.get("text", "")).strip()
        scene_done = bool(obj.get("scene_done", False))
        is_correct = bool(obj.get("correct", True))
        correction = str(obj.get("correction", "")).strip()
        speaker    = obj.get("speaker", "character")
        if text:
            return text, True, scene_done, is_correct, correction, speaker
    except Exception:
        pass

    # ── Attempt 2: regex field extraction ───────────────────────────────────
    t_match = _TEXT_RE.search(stripped)
    if t_match:
        text       = t_match.group(1).replace('\\"', '"').replace("\\n", " ").strip()
        d_match    = _DONE_RE.search(stripped)
        scene_done = bool(d_match and d_match.group(1).lower() == "true") if d_match else False
        c_match    = _CORRECT_RE.search(stripped)
        is_correct = not (c_match and c_match.group(1).lower() == "false")
        r_match    = _CORRECTION_RE.search(stripped)
        correction = r_match.group(1).replace('\\"', '"').strip() if r_match else ""
        s_match    = _SPEAKER_RE.search(stripped)
        speaker    = s_match.group(1).lower() if s_match else "character"
        return text, True, bool(scene_done), is_correct, correction, speaker

    # ── Attempt 3: legacy plain-text fallback ────────────────────────────────
    raw_no_scene, scene_directive = strip_scene_tag(stripped)
    text, _ = strip_ok_tag(raw_no_scene)
    return text, True, bool(scene_directive), True, "", "character"


def character_tts_b64(text: str, voice_id: str, eleven_key: str, lang_code: str = "da") -> str | None:
    """Synthesize a short line with the given voice; returns base64 string or None."""
    try:
        audio = tts_chunk(text, voice_id, eleven_key, lang_code=lang_code)
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
