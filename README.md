<div align="center">

# SpeakPals

**An AI-powered Danish language tutor with real-time voice conversation**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.55-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6_%7C_Haiku_4.5-D97757?style=flat-square)](https://anthropic.com)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-Turbo_v2.5-black?style=flat-square)](https://elevenlabs.io)

</div>

---

## What is SpeakPals?

SpeakPals is a conversational Danish tutor built for beginners (A1–B1). Tap the mic, speak, and the tutor responds in natural Danish — transcribed, understood by Claude, and spoken back through an animated avatar in roughly 3 seconds.

---

## How It Works

```
You speak
    │
    ▼
┌─────────────────┐   PCM 16kHz   ┌──────────────────────┐
│  VAD Mic        │──────────────▶│  ws_proxy.py          │
│  (AudioWorklet) │               │  (local WS server)    │
└─────────────────┘               └──────────┬───────────┘
                                             │ wss://
                                             ▼
                                  ┌──────────────────────┐
                                  │  ElevenLabs Scribe   │
                                  │  v2 Realtime (STT)   │
                                  └──────────┬───────────┘
                                             │ transcript
                                             ▼
                                  ┌──────────────────────┐
                                  │  Claude Sonnet 4.6   │
                                  │  (streaming LLM)     │
                                  └──────────┬───────────┘
                                             │ sentence chunks (parallel)
                                             ▼
                                  ┌──────────────────────┐
                                  │  ElevenLabs TTS      │
                                  │  Turbo v2.5 (Mathias)│
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │  Animated Avatar     │
                                  │  (SVG + audio)       │
                                  └──────────────────────┘
```

**Latency breakdown (~3 s end-to-end):**

| Stage | Time |
|---|---|
| VAD silence detection | ~1.2 s |
| Claude response (streaming) | ~0.8 s |
| TTS — parallel chunks, turbo model | ~0.5 s |
| Streamlit render | ~0.2 s |

---

## Features

| Feature | Detail |
|---|---|
| **Realtime STT** | ElevenLabs Scribe v2 Realtime — streaming over WebSocket |
| **Secure proxy** | API key stays server-side; browser connects to `localhost:8502` |
| **VAD** | AudioWorklet-based voice activity detection; 1.2 s silence threshold |
| **Partial transcript** | Pipeline starts the moment VAD fires — no extra round-trip |
| **LLM** | Claude Sonnet 4.6 (quality) or Haiku 4.5 (speed), streamed, max 120 tokens |
| **TTS** | ElevenLabs Turbo v2.5 — sentence chunks generated in parallel |
| **Animated avatar** | SVG with blink, breathe, and lip-sync animations |
| **Language profiles** | Tutor adapts tips based on native language (EN / DE / SV) |
| **English debug mode** | Switch to English voice + prompts for testing |
| **Conversation history** | Full session transcript with audio replay |
| **Type fallback** | Text input if mic is unavailable |

---

## Getting Started

### Prerequisites

- Python 3.11+
- [Anthropic API key](https://console.anthropic.com/)
- [ElevenLabs API key](https://elevenlabs.io/)

### Installation

```bash
git clone https://github.com/J-Marlon-H/SpeakPals.git
cd SpeakPals

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

**Local:** create `keys.env` in the project root:

```env
CLAUDE_API_KEY=your_anthropic_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
```

**Streamlit Cloud:** add the same two keys in your app's **Settings → Secrets** panel (TOML format):

```toml
CLAUDE_API_KEY     = "sk-ant-..."
ELEVENLABS_API_KEY = "sk_..."
```

### Run locally

```bash
streamlit run app.py
```

Open `http://localhost:8501`. The WebSocket proxy starts automatically on port `8502`.

### Deploy to Streamlit Cloud

Push to GitHub and connect the repo at [share.streamlit.io](https://share.streamlit.io).
Add secrets in the app settings panel. No proxy needed — the browser connects directly to ElevenLabs.

---

## Project Structure

```
SpeakPals/
├── app.py               # Streamlit UI — layout, sidebar, main loop
├── pipeline.py          # Claude LLM + ElevenLabs TTS (streaming generator)
├── avatar.py            # Animated SVG avatar HTML generator
├── prompts.py           # System prompts + language profile loader
├── ws_proxy.py          # WebSocket proxy: browser → ElevenLabs STT
├── vad_component/
│   └── index.html       # Browser mic component (AudioWorklet VAD)
├── lang_profiles/
│   ├── english.txt      # Teaching tips for English speakers
│   ├── german.txt       # Teaching tips for German speakers
│   └── swedish.txt      # Teaching tips for Swedish speakers
├── requirements.txt
└── keys.env             # API keys (not committed)
```

---

## Sidebar Settings

| Setting | Options | Description |
|---|---|---|
| **Mode** | Danish / English Debug | Language for prompts and voice |
| **Name** | text | Student name used in the system prompt |
| **Level** | A1 / A2 / B1 | CEFR proficiency level |
| **Native language** | English / German / Swedish | Loads a language-specific teaching profile |
| **Today's topics** | text | Focus area for the session |
| **AI model** | Sonnet 4.6 / Haiku 4.5 | Quality vs speed trade-off (~3 s vs ~2 s) |

---

## Tech Stack

- **Frontend** — [Streamlit](https://streamlit.io) + custom HTML/JS components
- **LLM** — [Claude Sonnet 4.6](https://anthropic.com) via Anthropic API (streaming)
- **STT** — [ElevenLabs Scribe v2 Realtime](https://elevenlabs.io/speech-to-text) over WebSocket
- **TTS** — [ElevenLabs Turbo v2.5](https://elevenlabs.io/text-to-speech) — voice: Mathias (Danish baritone)
- **Avatar** — Inline SVG + CSS animations

---

<div align="center">
  <sub>Built for X-Tech &middot; Danish A1–B1 learners</sub>
</div>
