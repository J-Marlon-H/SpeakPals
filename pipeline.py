import requests, urllib3, base64, json, re, concurrent.futures, time
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
    text = re.sub(r'[*_~`#]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


def tts_chunk(text, voice_id, eleven_key):
    for attempt in range(3):
        r = get_session().post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
            headers={"xi-api-key": eleven_key, "Content-Type": "application/json"},
            json={"text": text.strip(), "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.4, "similarity_boost": 0.75}},
            stream=True, timeout=30,
        )
        if r.status_code == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        return b"".join(r.iter_content(4096))
    r.raise_for_status()


def run_pipeline(system, user_input, history, voice_id, claude_key, eleven_key):
    sess = get_session()
    messages = [{"role": m["role"], "content": m["content"]}
                for m in history if m["role"] in {"user", "assistant"} and m["content"]]
    messages.append({"role": "user", "content": user_input})

    resp = sess.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
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
            ordered.append((idx, t, executor.submit(tts_chunk, t, voice_id, eleven_key)))
            idx += 1

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
            buf += ev.get("delta", {}).get("text", "")
            while re.search(r'[.!?,;]\s', buf):
                m = re.search(r'[.!?,;]\s', buf)
                submit(buf[:m.end()])
                buf = buf[m.end():]
            if len(buf.split()) > 2 and buf.endswith(" "):
                submit(buf)
                buf = ""

    if buf.strip():
        submit(buf)
    executor.shutdown(wait=True)

    results = sorted(ordered, key=lambda x: x[0])
    return (
        " ".join(t for _, t, _ in results),
        [base64.b64encode(f.result()).decode() for _, _, f in results],
    )


def stt(audio_bytes, lang, eleven_key):
    r = get_session().post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": eleven_key},
        files={"file": ("input.webm", audio_bytes, "audio/webm")},
        data={"model_id": "scribe_v1", "language_code": lang},
        timeout=20,
    )
    r.raise_for_status()
    t = r.json().get("text") or r.json().get("transcript") or ""
    if not t:
        raise RuntimeError("No transcript")
    return t


def warmup_claude(system, history, claude_key):
    try:
        msgs = [{"role": m["role"], "content": m["content"]}
                for m in history[-4:] if m["role"] in {"user", "assistant"} and m["content"]]
        msgs.append({"role": "user", "content": "..."})
        get_session().post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01",
                     "Content-Type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 1, "stream": False,
                  "system": system, "messages": msgs},
            timeout=5,
        )
    except Exception:
        pass
