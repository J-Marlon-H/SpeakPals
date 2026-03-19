<div align="center">

# SpeakPals

**AI-powered language tutor with real-time voice conversation**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.55-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6_%7C_Haiku_4.5-D97757?style=flat-square)](https://anthropic.com)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-Turbo_v2.5-black?style=flat-square)](https://elevenlabs.io)

</div>

---

## What is SpeakPals?

SpeakPals is a conversational language tutor for beginners (A1–B1). Currently supports **Danish** and **Brazilian Portuguese**. Tap the mic, speak into a scene (e.g. a café or supermarket), and the tutor responds in the target language — transcribed via ElevenLabs Scribe, understood by Claude, and spoken back through an animated avatar in roughly 3–4 seconds.

---

## How It Works

```
You speak
    │
    ▼
┌─────────────────┐   PCM 16kHz   ┌──────────────────────┐
│  VAD Mic        │──────────────▶│  ws_proxy.py          │
│  (AudioWorklet) │               │  (local WS server)    │
└─────────────────┘               └──────────┬────────────┘
                                             │ wss://
                                             ▼
                                  ┌──────────────────────┐
                                  │  ElevenLabs Scribe   │
                                  │  v2 Realtime (STT)   │
                                  └──────────┬────────────┘
                                             │ transcript
                                             ▼
                                  ┌──────────────────────┐
                                  │  Claude Sonnet 4.6   │
                                  │  (streaming LLM)     │
                                  └──────────┬────────────┘
                                             │ full response
                                             ▼
                                  ┌──────────────────────┐
                                  │  ElevenLabs TTS      │
                                  │  Turbo / Flash v2.5  │
                                  └──────────┬────────────┘
                                             │ base64 audio
                                             ▼
                                  ┌──────────────────────┐
                                  │  Animated Avatar     │
                                  │  (SVG + Web Audio)   │
                                  └──────────────────────┘
```

**Latency breakdown (~3–4 s end-to-end):**

| Stage | Typical time |
|---|---|
| VAD silence detection | ~1.2 s |
| ElevenLabs STT commit → transcript | ~0.3 s |
| Claude response (streaming) | ~0.8 s |
| ElevenLabs TTS (single call) | ~0.6 s |
| Streamlit rerun + component render | ~0.2 s |

---

## Features

| Feature | Detail |
|---|---|
| **Realtime STT** | ElevenLabs Scribe v2 Realtime — streaming PCM over WebSocket, language set via init message |
| **Secure local proxy** | `ws_proxy.py` keeps the API key server-side; browser connects to `localhost:8502` |
| **Cloud fallback** | On Streamlit Cloud, a single-use token is issued server-side; browser connects directly to ElevenLabs |
| **VAD** | AudioWorklet-based voice activity detection — 1.2 s silence threshold |
| **LLM** | Claude Sonnet 4.6 (quality) or Haiku 4.5 (speed), streamed, max 180 tokens |
| **TTS** | ElevenLabs Turbo v2.5 (Danish) / Flash v2.5 (Portuguese) — per-language model selection |
| **Character TTS** | Scene character (barista, cashier…) speaks questions in a separate native-accented voice |
| **Animated avatar** | SVG with blink, breathe, and lip-sync animations |
| **Scene scripts** | Scripted interactions per scene — tutor evaluates responses via structured JSON output |
| **Language profiles** | Tutor adapts silently based on student's native language (EN / DE / SV) |
| **Multi-language** | Danish and Brazilian Portuguese — each with native voice IDs, correct STT language code, and per-language TTS model |
| **Conversation log** | Accepted answers shown in sidebar chat; replay character audio |
| **Scene selection** | Six scenes across A1–B1 levels |
| **AI image generation** | fal.ai Flux Schnell generates scene transition images (optional, requires FAL_KEY) |

---

## Supported Languages

| Language | Tutor | STT code | TTS model | Voices |
|---|---|---|---|---|
| Danish | Lars | `da` | eleven_turbo_v2_5 | Mathias, Camilla, Casper |
| Brazilian Portuguese | João | `por` | eleven_flash_v2_5 | Matheus, Camila, Flavio |

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Anthropic API key](https://console.anthropic.com/)
- [ElevenLabs API key](https://elevenlabs.io/)
- *(Optional)* [fal.ai API key](https://fal.ai/) — only needed for AI-generated scene images

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
CLAUDE_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=sk_...
FAL_KEY=...          # optional — leave blank to disable scene image generation
```

**Streamlit Cloud:** add the same keys in **Settings → Secrets** (TOML format):

```toml
CLAUDE_API_KEY     = "sk-ant-..."
ELEVENLABS_API_KEY = "sk_..."
FAL_KEY            = "..."
```

### Run locally

```bash
streamlit run app.py
```

Open `http://localhost:8501`. The WebSocket proxy starts automatically on port `8502`.

### Deploy to Streamlit Cloud

Push to GitHub and connect the repo at [share.streamlit.io](https://share.streamlit.io).
Add secrets in the app settings panel. No proxy is needed — the component uses a single-use token fetched server-side to connect directly to ElevenLabs.

---

## Project Structure

```
SpeakPals/
├── app.py                   # Main lesson UI — layout, sidebar, pipeline orchestration
├── pipeline.py              # Claude LLM streaming + ElevenLabs TTS + fal.ai image gen
├── prompts.py               # System prompts, level rules, language profile loader
├── ws_proxy.py              # Local WebSocket proxy: browser → ElevenLabs STT
├── scene_images.py          # Scene image loader with base64 caching
├── pages/
│   ├── home.py              # Home screen with language/scene selection
│   ├── account.py           # Student settings (name, level, voice, model)
│   ├── feedback.py          # End-of-lesson conversation summary
│   └── scene_select.py      # Scene selection screen (bakery, flower shop, …)
├── vad_component/
│   └── index.html           # Browser mic component (AudioWorklet VAD + avatar)
├── lang_profiles/
│   ├── english.txt          # Teaching tips for English speakers
│   ├── german.txt           # Teaching tips for German speakers
│   └── swedish.txt          # Teaching tips for Swedish speakers
├── assets/
│   └── scenes/
│       ├── friend.jpg
│       ├── cafe.jpg
│       ├── supermarket_cashier.jpg
│       ├── flower_store.jpg
│       ├── bakery.jpg
│       └── restaurant.jpg
├── requirements.txt
└── keys.env                 # API keys — never commit this file
```

---

## Student Settings

| Setting | Options | Description |
|---|---|---|
| **Name** | text | Used in the tutor's system prompt |
| **Language** | Danish / Portuguese (Brazilian) | Target language for the lesson |
| **Level** | A1 / A2 / B1 | CEFR proficiency level — controls language mix and expectations |
| **Native language** | English / German / Swedish | Loads a language-specific teaching profile |
| **Tutor voice** | Per-language voice menu | ElevenLabs voice for the tutor |
| **AI model** | Sonnet 4.6 / Haiku 4.5 | Quality vs speed |

---

## Scene Catalog

| Scene | Level | Character |
|---|---|---|
| Meet a Friend | A1 | Friend |
| At the Café | A1 | Barista |
| Supermarket Checkout | A1 | Cashier |
| At the Flower Shop | A2 | Florist |
| At the Bakery | A2 | Baker |
| At the Restaurant | B1 | Waiter |

---

## Turn Flow

```
1. SCENE LOADS
   Character TTS pre-fetched (character voice, native accent)
   Character Q0 audio queued but NOT played yet

2. STUDENT clicks "Start lesson"
   Component → sends "__started__" → Python sets lesson_started=True
   Queued character audio plays immediately
   Sidebar chat reveals (character Q0 already logged)

3. STUDENT speaks
   VAD (AudioWorklet) streams 16 kHz PCM → WebSocket → ElevenLabs Scribe
   Silence > 1.2 s → transcript committed
   Component → sends transcript string → Python: pending_student set

4. PIPELINE (Python)
   Claude receives: system prompt + full chat history + student transcript
   Claude streams structured JSON response (verdict + text)
   Full response assembled → TTS call in target language
   tutor_play_seq incremented → component detects new audio

5. TUTOR SPEAKS
   Avatar mouth animates, "Speaking…" label shown
   Character's next audio queued for after tutor finishes

6. ROUTING — Claude verdict is either:

   ├── ACCEPT: student answered correctly
   │   Student answer logged to sidebar chat
   │   interaction_idx advances
   │   Tutor finishes → 350 ms pause → character plays next question
   │   If last question: confetti + "Scene complete!" overlay
   │
   └── COACH: student did not answer correctly
       Tutor corrects the answer
       Tutor finishes → character replays the SAME question
       Student must answer again

7. BETWEEN SCENES (if FAL_KEY set)
   Scene image generated in background thread (fal.ai Flux Schnell)
   On completion: scene_idx advances, new image loads
   Character Q0 of next scene pre-fetched and queued
```

---

## Tech Stack

- **Frontend** — [Streamlit](https://streamlit.io) + custom HTML/JS components
- **LLM** — [Claude Sonnet 4.6 / Haiku 4.5](https://anthropic.com) via Anthropic API (streaming, structured outputs)
- **STT** — [ElevenLabs Scribe v2 Realtime](https://elevenlabs.io/speech-to-text) over WebSocket
- **TTS** — [ElevenLabs Turbo / Flash v2.5](https://elevenlabs.io/text-to-speech) — tutor and character voices
- **Image gen** — [fal.ai Flux Schnell](https://fal.ai/) — scene transition images (optional)
- **Avatar** — Inline SVG + CSS animations

---

<div align="center">
  <sub>Built for X-Tech · A1–B1 language learners</sub>
</div>
