<div align="center">

# SpeakPals

**AI-powered Danish language tutor with real-time voice conversation**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.55-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6_%7C_Haiku_4.5-D97757?style=flat-square)](https://anthropic.com)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-Turbo_v2.5-black?style=flat-square)](https://elevenlabs.io)

</div>

---

## What is SpeakPals?

SpeakPals is a conversational Danish tutor for beginners (A1–B1). Tap the mic, speak into a scene (e.g. a supermarket checkout), and the tutor responds in natural Danish — transcribed via ElevenLabs Scribe, understood by Claude, and spoken back through an animated avatar in roughly 3–4 seconds.

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
                                  │  Turbo v2.5          │
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
| ElevenLabs TTS (single call, turbo) | ~0.6 s |
| Streamlit rerun + component render | ~0.2 s |

---

## Features

| Feature | Detail |
|---|---|
| **Realtime STT** | ElevenLabs Scribe v2 Realtime — streaming PCM over WebSocket |
| **Secure local proxy** | `ws_proxy.py` keeps the API key server-side; browser connects to `localhost:8502` |
| **Cloud fallback** | On Streamlit Cloud, a single-use token is issued server-side; browser connects directly to ElevenLabs |
| **VAD** | AudioWorklet-based voice activity detection — 1.2 s silence threshold |
| **LLM** | Claude Sonnet 4.6 (quality) or Haiku 4.5 (speed), streamed, max 180 tokens |
| **TTS** | ElevenLabs Turbo v2.5 — single call per response; three Danish voice options |
| **Character TTS** | Scene character (cashier, baker…) speaks questions in a separate voice |
| **Animated avatar** | SVG with blink, breathe, and lip-sync animations |
| **Scene scripts** | Scripted interactions per scene — tutor routes responses via PATH A / PATH B |
| **Language profiles** | Tutor adapts silently based on student's native language (EN / DE / SV) |
| **Conversation log** | Accepted answers shown in sidebar chat; replay cashier / show tutor text |
| **Scene selection** | Choose between scenes at the end of a session |
| **AI image generation** | fal.ai Flux Schnell generates scene transition images (optional) |

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
├── pages/
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
│       ├── supermarket_cashier.png
│       ├── bakery.png        # drop your own image here
│       └── flower_store.png  # drop your own image here
├── requirements.txt
└── keys.env                 # API keys — never commit this file
```

---

## Student Settings

| Setting | Options | Description |
|---|---|---|
| **Name** | text | Used in the tutor's system prompt |
| **Level** | A1 / A2 / B1 | CEFR proficiency level — controls language mix and expectations |
| **Native language** | English / German / Swedish | Loads a language-specific teaching profile |
| **Tutor voice** | Mathias / Camilla / Casper | ElevenLabs voice for the tutor |
| **AI model** | Sonnet 4.6 / Haiku 4.5 | Quality vs speed |

---

## Turn Flow — one complete exchange

```
1. SCENE LOADS
   │  Character TTS pre-fetched (cashier voice, separate voice ID)
   │  Character Q0 audio queued but NOT played yet
   │
2. STUDENT clicks "Start lesson"
   │  Component → sends "__started__" → Python sets lesson_started=True
   │  Queued cashier audio plays immediately
   │  Sidebar chat reveals (cashier Q0 already logged there)
   │
3. STUDENT speaks
   │  VAD (AudioWorklet) streams 16 kHz PCM → WebSocket → ElevenLabs Scribe
   │  Silence > 1.2 s → transcript committed
   │  Component → sends transcript string → Python: pending_student set, avatar_thinking=True
   │
4. PIPELINE (Python)
   │  Claude receives: system prompt + full chat history + student transcript
   │  Claude streams response (max 180 tokens)
   │  Full response assembled → TTS call with language_code="da"
   │  tutor_play_seq incremented → component detects new audio
   │
5. TUTOR SPEAKS (in component)
   │  Avatar mouth animates, "Speaking…" label shown
   │  Cashier's next audio queued in pendingCharAfterTutor
   │
6. ROUTING — Claude's response contains either:
   │
   ├── PATH A (accepted): ends with literal token <ok/>
   │   │  Python: has_ok=True
   │   │  Student answer logged to sidebar chat
   │   │  interaction_idx advances
   │   │  Tutor finishes → 350 ms pause → cashier Q_next plays
   │   │  If last question: scene_celebration=True → confetti + "Scene complete!" overlay
   │   │  If all scenes done: "Finish Lecture" available in sidebar
   │   │
   │   └── Last question of scene: tutor explicitly celebrates before <ok/>
   │
   └── PATH B (coach): NO <ok/> anywhere in response
       │  Python: has_ok=False — interaction_idx stays the same
       │  Student answer NOT logged (not accepted)
       │  Tutor finishes → cashier replays the SAME question
       │  Student must answer again
   │
7. BETWEEN SCENES (if FAL_KEY set)
      Scene image generated in background thread (fal.ai Flux Schnell)
      On completion: scene_idx advances, new image loads
      Cashier Q0 of next scene pre-fetched and queued
```

## Routing Rules in Detail

### PATH A — Accept

Triggered when: the student's answer is correct enough for their CEFR level.

Required Claude output format:
```
[affirmation]. [Lad os fortsætte! — if more questions remain] <ok/>
```
- `<ok/>` must be the **very last token** — nothing after it
- On the last question: Claude celebrates the scene instead of "Lad os fortsætte!"
- Python only counts `<ok/>` as valid if it appears at the end of the stripped response (regex `<ok\s*/>\s*$`) — prevents false positives from coaching messages that reference the tag

### PATH B — Coach

Triggered when: the answer is wrong or incomplete.

Required Claude output format:
```
[echo what they said]. [correct Danish form + brief explanation]
```
- **No `<ok/>` anywhere** — not at the end, not mid-sentence
- Same question will repeat; cashier asks it again after tutor finishes coaching
- Claude is explicitly told: writing `<ok/>` advances the lesson even mid-sentence

### Anti-hallucination safeguards

| Safeguard | Purpose |
|---|---|
| `_OK_AT_END` regex (end-anchored) | Rejects `<ok/>` in coaching responses that mention it as an example |
| `is_last_question` flag in system prompt | Tells Claude this is the final exchange → explicit celebration required |
| `language_code: "da"` in TTS | Forces ElevenLabs to use Danish phonemes, not English guesses |
| Max 180 tokens | Prevents long responses that drift off-script |

---

## Tech Stack

- **Frontend** — [Streamlit](https://streamlit.io) + custom HTML/JS components
- **LLM** — [Claude Sonnet 4.6 / Haiku 4.5](https://anthropic.com) via Anthropic API (streaming)
- **STT** — [ElevenLabs Scribe v2 Realtime](https://elevenlabs.io/speech-to-text) over WebSocket
- **TTS** — [ElevenLabs Turbo v2.5](https://elevenlabs.io/text-to-speech) — tutor and character voices
- **Image gen** — [fal.ai Flux Schnell](https://fal.ai/) — scene transition images
- **Avatar** — Inline SVG + CSS animations

---

<div align="center">
  <sub>Built for X-Tech · Danish A1–B1 learners</sub>
</div>
