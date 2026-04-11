#!/usr/bin/env python3
"""
SpeakPals Telegram Bot
──────────────────────
Run:  python telegram_bot.py
Needs TELEGRAM_BOT_TOKEN in keys.env (alongside the existing API keys).

Commands:
  /start  — welcome & onboarding
  /scene  — pick or change scene
  /level  — change level
  /stop   — end lesson + corrections summary
  /help   — list commands

Send text or a voice note to practise.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import subprocess

import requests
from dotenv import load_dotenv
from telegram import InputFile, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pipeline import (
    SCENE_CATALOG,
    STT_LANG_CODE,
    TTS_LANG_CODE,
    VERDICT_SCHEMA,
    VOICES_BY_LANG,
    clean_for_tts,
    get_session,
    parse_claude_response,
    tts_chunk,
)
from prompts import build_system_prompt, get_tutor_name

# ── Setup ─────────────────────────────────────────────────────────────────────

load_dotenv("keys.env")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("speakpals_bot")

CLAUDE_KEY = os.getenv("CLAUDE_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")

USERS_DIR = pathlib.Path("telegram_users")
USERS_DIR.mkdir(exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=4)

FFMPEG = "/opt/homebrew/bin/ffmpeg"

# ── User state ────────────────────────────────────────────────────────────────

DEFAULT_STATE: dict = {
    "name":         None,
    "level":        "A1",
    "bg_lang":      "English",
    "language":     "Danish",
    "voice_label":  "Mathias — male baritone",
    "scene_key":    None,
    "chat":         [],
    "turn_count":   0,
    "correct_log":  [],
    "coaching_log": [],
    "setup_step":   "name",   # None = fully set up
}

BG_LANGS = ["English", "German", "Swedish", "Other"]


def _user_file(chat_id: int) -> pathlib.Path:
    return USERS_DIR / f"{chat_id}.json"


def load_user(chat_id: int) -> dict:
    f = _user_file(chat_id)
    if f.exists():
        try:
            data = json.loads(f.read_text())
            for k, v in DEFAULT_STATE.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return dict(DEFAULT_STATE)


def save_user(chat_id: int, state: dict) -> None:
    _user_file(chat_id).write_text(json.dumps(state, indent=2))


# ── Audio conversion ─────────────────────────────────────────────────────────

def _mp3_to_ogg_opus(mp3_bytes: bytes) -> bytes:
    """Convert MP3 bytes → OGG Opus via ffmpeg using temp files.
    Temp files are required because the OGG container needs to seek back
    and rewrite its headers after encoding — not possible with a pipe."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as src:
        src.write(mp3_bytes)
        src_path = src.name
    dst_path = src_path.replace(".mp3", ".ogg")
    try:
        subprocess.run(
            [FFMPEG, "-y", "-i", src_path, "-c:a", "libopus", "-b:a", "32k", dst_path,
             "-loglevel", "error"],
            check=True,
        )
        with open(dst_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(src_path)
        if os.path.exists(dst_path):
            os.unlink(dst_path)


# ── ElevenLabs STT (REST) ─────────────────────────────────────────────────────

def _stt_sync(audio_bytes: bytes, lang_code: str = "da") -> str:
    """Transcribe audio via ElevenLabs Scribe REST API (blocking)."""
    r = requests.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": ELEVEN_KEY},
        data={"model_id": "scribe_v1", "language_code": lang_code},
        files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("text", "").strip()


# ── Inline keyboards ──────────────────────────────────────────────────────────

def _lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇩🇰 Danish",      callback_data="language:Danish"),
        InlineKeyboardButton("🇧🇷 Portuguese",  callback_data="language:Portuguese (Brazilian)"),
    ]])


def _level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("A1 — Beginner",      callback_data="level:A1"),
            InlineKeyboardButton("A2 — Elementary",    callback_data="level:A2"),
        ],
        [
            InlineKeyboardButton("B1 — Intermediate",       callback_data="level:B1"),
            InlineKeyboardButton("B2 — Upper Intermediate", callback_data="level:B2"),
        ],
    ])


def _bg_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang, callback_data=f"bg_lang:{lang}")]
        for lang in BG_LANGS
    ])


def _scene_keyboard(level: str) -> InlineKeyboardMarkup:
    scenes = [s for s in SCENE_CATALOG if s["level"] == level] or SCENE_CATALOG
    rows = []
    for i in range(0, len(scenes), 2):
        rows.append([
            InlineKeyboardButton(s["title"], callback_data=f"scene:{s['key']}")
            for s in scenes[i:i + 2]
        ])
    return InlineKeyboardMarkup(rows)


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = load_user(chat_id)

    if user["name"] and not user.get("setup_step"):
        level_labels = {"A1": "Beginner", "A2": "Elementary",
                        "B1": "Intermediate", "B2": "Upper Intermediate"}
        await update.message.reply_text(
            f"Velkommen tilbage, *{user['name']}*! 👋\n"
            f"Level: *{user['level']} — {level_labels.get(user['level'], '')}*  |  "
            f"Language: *{user['language']}*\n\n"
            "Use /scene to start a conversation, or just send me a message to continue.",
            parse_mode="Markdown",
        )
    else:
        user["setup_step"] = "name"
        save_user(chat_id, user)
        await update.message.reply_text(
            "👋 Welcome to *SpeakPals*!\n\n"
            "I'm your AI language tutor. Here's how it works:\n\n"
            "1️⃣ Pick a *scene* — a real-life situation like a café, supermarket, or meeting a friend\n"
            "2️⃣ Have a conversation in the language you're learning — "
            "type or send a *voice note*, whatever feels natural\n"
            "3️⃣ Your tutor plays the character and gently corrects mistakes along the way\n"
            "4️⃣ Use /stop at any time to end the lesson and see a corrections summary\n\n"
            "*Commands:*\n"
            "/scene — pick a scene\n"
            "/level — change your level\n"
            "/stop  — end lesson & see feedback\n"
            "/reset — start over with a new profile\n"
            "/help  — show this again\n\n"
            "Let's get you set up. What's your name?",
            parse_mode="Markdown",
        )


async def cmd_scene(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = load_user(chat_id)
    if not user["name"] or user.get("setup_step"):
        await update.message.reply_text("Please finish setup first — use /start.")
        return
    await update.message.reply_text(
        "Choose a scene to practise:",
        reply_markup=_scene_keyboard(user["level"]),
    )


async def cmd_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Choose your level:", reply_markup=_level_keyboard())


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = load_user(chat_id)
    turns = user.get("turn_count", 0)

    if turns == 0:
        await update.message.reply_text(
            "No lesson in progress. Use /scene to start one!"
        )
        return

    coaching = user.get("coaching_log", [])
    if coaching:
        corrections = "\n".join(
            f"• _{c['student']}_ → *{c['correct_form']}*"
            for c in coaching[-6:]
        )
    else:
        corrections = "_No corrections — great work!_ 🎉"

    scene = next((s for s in SCENE_CATALOG if s["key"] == user.get("scene_key")), None)
    scene_title = scene["title"] if scene else "—"

    await update.message.reply_text(
        f"*Lesson complete!* 📋\n\n"
        f"Scene: *{scene_title}*  |  Turns: *{turns}*\n\n"
        f"*Things to remember:*\n{corrections}\n\n"
        "Use /scene to start a new conversation!",
        parse_mode="Markdown",
    )

    # Clear lesson state, keep profile
    user.update({"chat": [], "turn_count": 0, "correct_log": [],
                 "coaching_log": [], "scene_key": None})
    save_user(chat_id, user)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*SpeakPals* 🇩🇰\n\n"
        "*How it works:*\n"
        "1️⃣ Pick a scene with /scene — a real-life situation to practise in\n"
        "2️⃣ Send a *text message* or *voice note* to reply to the character\n"
        "3️⃣ Your tutor plays the character and corrects mistakes gently\n"
        "4️⃣ Use /stop to end the lesson and see what to remember\n\n"
        "*Commands:*\n"
        "/start — welcome & profile setup\n"
        "/scene — pick or change your scene\n"
        "/level — change your level (A1 → B2)\n"
        "/stop  — end lesson & see corrections\n"
        "/help  — show this message\n\n"
        "*Tips:*\n"
        "• Voice notes are transcribed automatically — speak naturally\n"
        "• Your tutor echoes back what it heard before replying\n"
        "• Corrections appear in _italics_ — note them for next time\n"
        "• You can switch scenes any time with /scene\n"
        "• Use /reset to start fresh with a new profile",
        parse_mode="Markdown",
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    f = _user_file(chat_id)
    if f.exists():
        f.unlink()
    await update.message.reply_text(
        "Profile cleared! Use /start to set up a new one."
    )


# ── Onboarding (text step) ────────────────────────────────────────────────────

def _extract_name(raw: str) -> str:
    """Pull just the first name out of phrases like 'Hi, my name is Milla!'"""
    text = raw.strip().rstrip("!.,")
    # Strip common intro phrases, case-insensitive
    patterns = [
        r"(?:hi|hello|hey)[,\s]+(?:my name is|i(?:'m| am)|i'm)\s+",
        r"(?:my name is|i(?:'m| am)|i'm|call me|it'?s)\s+",
        r"(?:hi|hello|hey)[,!\s]+",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip().rstrip("!.,")
    # Take only the first word (first name)
    first_word = text.split()[0] if text.split() else raw.strip()
    return first_word.capitalize()


async def _handle_setup_text(
    update: Update, user: dict, chat_id: int
) -> None:
    step = user.get("setup_step")

    if step == "name":
        name = _extract_name(update.message.text)
        user["name"] = name
        user["setup_step"] = "language"
        save_user(chat_id, user)
        await update.message.reply_text(
            f"Nice to meet you, *{name}*! 🎉\n\nWhat language would you like to practise?",
            parse_mode="Markdown",
            reply_markup=_lang_keyboard(),
        )
    else:
        # Other steps need button presses — remind the user
        prompts = {
            "language": ("Choose a language:", _lang_keyboard()),
            "level":    ("Choose your level:", _level_keyboard()),
            "bg_lang":  ("What's your native language?", _bg_lang_keyboard()),
        }
        if step in prompts:
            msg, kb = prompts[step]
            await update.message.reply_text(msg, reply_markup=kb)


# ── Callback queries (inline button presses) ──────────────────────────────────

async def callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user = load_user(chat_id)
    action, _, value = query.data.partition(":")

    if action == "language":
        user["language"] = value
        voices = VOICES_BY_LANG.get(value, {})
        user["voice_label"] = next(iter(voices.keys()), user["voice_label"])
        if user.get("setup_step") == "language":
            user["setup_step"] = "level"
            save_user(chat_id, user)
            await query.edit_message_text(
                f"Great — we'll practise *{value}*! 🎯\n\nWhat's your current level?",
                parse_mode="Markdown",
                reply_markup=_level_keyboard(),
            )
        else:
            save_user(chat_id, user)
            await query.edit_message_text(
                f"Language updated to *{value}*.", parse_mode="Markdown"
            )

    elif action == "level":
        level_labels = {"A1": "Beginner", "A2": "Elementary",
                        "B1": "Intermediate", "B2": "Upper Intermediate"}
        user["level"] = value
        if user.get("setup_step") == "level":
            user["setup_step"] = "bg_lang"
            save_user(chat_id, user)
            await query.edit_message_text(
                f"Level set to *{value} — {level_labels.get(value, '')}*.\n\n"
                "What's your native language?",
                parse_mode="Markdown",
                reply_markup=_bg_lang_keyboard(),
            )
        else:
            save_user(chat_id, user)
            await query.edit_message_text(
                f"Level updated to *{value}*.", parse_mode="Markdown"
            )

    elif action == "bg_lang":
        user["bg_lang"] = value
        if user.get("setup_step") == "bg_lang":
            user["setup_step"] = None
            save_user(chat_id, user)
            await query.edit_message_text(
                f"All set, *{user['name']}*! 🚀\n\n"
                f"Language: *{user['language']}*  |  Level: *{user['level']}*  |  Native: *{value}*\n\n"
                "Pick a scene below to start your first conversation.\n"
                "You can send *text* or a *voice note* — I'll handle the rest.\n"
                "Use /stop when you're done to see your corrections.",
                parse_mode="Markdown",
                reply_markup=_scene_keyboard(user["level"]),
            )
        else:
            save_user(chat_id, user)
            await query.edit_message_text(
                f"Native language updated to *{value}*.", parse_mode="Markdown"
            )

    elif action == "scene":
        scene = next((s for s in SCENE_CATALOG if s["key"] == value), None)
        if not scene:
            await query.edit_message_text("Scene not found.")
            return
        user.update({"scene_key": value, "chat": [], "turn_count": 0,
                     "correct_log": [], "coaching_log": []})
        save_user(chat_id, user)
        await query.edit_message_text(
            f"*{scene['title']}* 🎬\n_{scene['desc']}_\n\n"
            f"The {scene['char_name']} is ready. Start speaking!\n"
            "_(Send a text message or voice note)_",
            parse_mode="Markdown",
        )


# ── Pipeline helpers ──────────────────────────────────────────────────────────

def _build_context(user: dict) -> tuple[str, str, str, str, str]:
    """Return (system_prompt, voice_id, char_voice_id, lang_code, model)."""
    scene         = next((s for s in SCENE_CATALOG if s["key"] == user["scene_key"]), None)
    system        = build_system_prompt(
        user["name"], user["level"],
        date.today().strftime("%B %d, %Y"), user["bg_lang"],
        target_lang=user["language"],
        scene_description=scene["scene_description"] if scene else "",
        turn_count=user.get("turn_count", 0),
    )
    lang_voices   = VOICES_BY_LANG.get(user["language"], {})
    voice_id      = lang_voices.get(user["voice_label"]) or next(iter(lang_voices.values()))
    char_voice_id = next((v for v in lang_voices.values() if v != voice_id), voice_id)
    lang_code     = TTS_LANG_CODE.get(user["language"], "da")
    return system, voice_id, char_voice_id, lang_code, "claude-haiku-4-5-20251001"


def _claude_sync(system: str, user_text: str, chat: list, model: str) -> str:
    """Call Claude and return the raw response text (no TTS)."""
    sess     = get_session()
    messages = [{"role": m["role"], "content": m["content"]}
                for m in chat if m["role"] in {"user", "assistant"} and m["content"]]
    messages.append({"role": "user", "content": user_text})
    resp = sess.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": model, "max_tokens": 220, "temperature": 0.3,
              "stream": True, "system": system, "messages": messages,
              "output_config": {"format": {"type": "json_schema",
                                           "schema": VERDICT_SCHEMA}}},
        stream=True, timeout=30,
    )
    resp.raise_for_status()
    raw = ""
    for line in resp.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
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
            raw += ev.get("delta", {}).get("text", "")
    return raw


def _tts_sync(spoken_text: str, speaker: str,
              voice_id: str, char_voice_id: str, lang_code: str) -> bytes:
    """Generate TTS using a low-bitrate format for faster transfer and conversion."""
    tts_voice = char_voice_id if speaker == "character" else voice_id
    tts_lang  = lang_code     if speaker == "character" else "en"
    from pipeline import TTS_MODEL
    r = get_session().post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{tts_voice}/stream"
        f"?output_format=mp3_22050_32",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={
            "text": clean_for_tts(spoken_text),
            "model_id": TTS_MODEL.get(tts_lang, "eleven_turbo_v2_5"),
            "language_code": tts_lang,
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "speed": 0.92},
        },
        stream=True, timeout=30,
    )
    r.raise_for_status()
    return b"".join(r.iter_content(4096))


async def _process_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    user: dict,
    chat_id: int,
) -> None:
    """Feed user_text through the pipeline and reply with text + audio.

    Text is sent as soon as Claude responds (~2s).
    Voice note follows after TTS + conversion (~2s more).
    """
    if not user.get("scene_key"):
        await update.effective_message.reply_text("Use /scene to pick a scene first!")
        return

    loop = asyncio.get_running_loop()
    system, voice_id, char_voice_id, lang_code, model = _build_context(user)

    # ── Step 1: Claude (show typing indicator while waiting) ──────────────────
    async def _keep_typing():
        while True:
            await context.bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(_keep_typing())
    try:
        raw_claude = await loop.run_in_executor(
            _executor, lambda: _claude_sync(system, user_text, user["chat"], model)
        )
    except Exception:
        log.exception("Claude error for chat %s", chat_id)
        typing_task.cancel()
        await update.effective_message.reply_text("⚠️ Something went wrong. Please try again.")
        return
    finally:
        typing_task.cancel()

    spoken_text, _, scene_done, is_correct, correction, speaker = parse_claude_response(raw_claude)

    # Update conversation state
    user["chat"].extend([
        {"role": "user",      "content": user_text},
        {"role": "assistant", "content": spoken_text},
    ])
    user["turn_count"] = user.get("turn_count", 0) + 1
    user.setdefault("correct_log", []).append({"who": speaker, "text": spoken_text})
    if correction:
        user.setdefault("coaching_log", []).append(
            {"student": user_text, "correct_form": correction}
        )
    save_user(chat_id, user)

    # ── Step 2: Send text reply immediately ───────────────────────────────────
    scene      = next((s for s in SCENE_CATALOG if s["key"] == user["scene_key"]), None)
    char_label = scene["char_name"] if scene else "Character"
    tutor_name = get_tutor_name(user["language"])
    label      = char_label if speaker == "character" else f"💡 {tutor_name}"
    await update.effective_message.reply_text(
        f"*{label}:* {spoken_text}", parse_mode="Markdown"
    )
    if correction and not is_correct:
        await update.effective_message.reply_text(f"_✏️ {correction}_", parse_mode="Markdown")

    # ── Step 3: TTS + OGG conversion (show upload indicator while waiting) ────
    await context.bot.send_chat_action(chat_id, "upload_voice")
    try:
        mp3_bytes = await loop.run_in_executor(
            _executor,
            lambda: _tts_sync(spoken_text, speaker, voice_id, char_voice_id, lang_code)
        )
        ogg_bytes = await loop.run_in_executor(
            _executor, lambda: _mp3_to_ogg_opus(mp3_bytes)
        )
        await context.bot.send_voice(
            chat_id=chat_id,
            voice=InputFile(io.BytesIO(ogg_bytes), filename="speakpals.ogg"),
        )
    except Exception:
        log.exception("TTS/audio error for chat %s", chat_id)
        # Text was already sent — audio failure is non-fatal

    if scene_done:
        await update.effective_message.reply_text(
            "🎉 Scene complete! Use /stop to review corrections, or /scene for a new one."
        )


# ── Message handlers ──────────────────────────────────────────────────────────

async def text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = update.effective_chat.id
    user    = load_user(chat_id)

    if user.get("setup_step"):
        await _handle_setup_text(update, user, chat_id)
    else:
        await _process_message(update, context, update.message.text.strip(), user, chat_id)


async def voice_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = update.effective_chat.id
    user    = load_user(chat_id)

    if user.get("setup_step"):
        await update.message.reply_text(
            "Please finish setup first — use the buttons above or /start."
        )
        return

    await context.bot.send_chat_action(chat_id, "typing")

    # Download the voice note Telegram sent as OGG
    voice_file  = await context.bot.get_file(update.message.voice.file_id)
    audio_bytes = bytes(await voice_file.download_as_bytearray())
    lang_code   = STT_LANG_CODE.get(user["language"], "da")

    loop = asyncio.get_running_loop()
    try:
        transcript = await loop.run_in_executor(
            _executor, lambda: _stt_sync(audio_bytes, lang_code)
        )
    except Exception:
        log.exception("STT error for chat %s", chat_id)
        await update.message.reply_text(
            "⚠️ Couldn't transcribe your voice note. Try again or type your response."
        )
        return

    if not transcript:
        await update.message.reply_text(
            "⚠️ Couldn't hear anything clearly. Please try again."
        )
        return

    # Echo the transcript so the user can see what was heard
    await update.message.reply_text(f"_{transcript}_", parse_mode="Markdown")
    await _process_message(update, context, transcript, user, chat_id)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set. Add it to keys.env and try again."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scene", cmd_scene))
    app.add_handler(CommandHandler("level", cmd_level))
    app.add_handler(CommandHandler("stop",  cmd_stop))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))

    log.info("SpeakPals bot starting (polling)…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
