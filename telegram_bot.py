#!/usr/bin/env python3
"""
SpeakPals Telegram Bot
──────────────────────
Run:  python telegram_bot.py
Needs TELEGRAM_BOT_TOKEN in keys.env (alongside the existing API keys).

Commands:
  /stop   — end session + corrections summary
  /reset  — clear conversation history
  /link   — link to SpeakPals web account
  /help   — list commands

Send text or a voice note to chat with your tutor.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor

import subprocess

import requests
from dotenv import load_dotenv
from telegram import InputFile, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pipeline import (
    VERDICT_SCHEMA,
    clean_for_tts,
    get_session,
    parse_claude_response,
    tts_tutor_mixed,
)
from prompts import build_system_prompt, get_tutor_name
from tutor import Tutor

# ── Setup ─────────────────────────────────────────────────────────────────────

load_dotenv("keys.env")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("speakpals_bot")


def _secret(key: str) -> str | None:
    """Read from Streamlit secrets first, fall back to environment variable."""
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.getenv(key)


CLAUDE_KEY = _secret("CLAUDE_API_KEY")
ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
BOT_TOKEN  = _secret("TELEGRAM_BOT_TOKEN")

USERS_DIR = pathlib.Path("telegram_users")
USERS_DIR.mkdir(exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=4)

# ── Inactivity-based profile update ──────────────────────────────────────────
# After PROFILE_UPDATE_DELAY seconds of silence, update the knowledge profile.
PROFILE_UPDATE_DELAY = 120  # 2 minutes

# Pending asyncio tasks keyed by chat_id — cancelled when a new message arrives
_profile_tasks: dict[int, asyncio.Task] = {}


def _build_profile_log(user: dict) -> list[dict]:
    """Convert the bot chat history into the format expected by update_knowledge_profile."""
    log = []
    for m in user.get("chat", []):
        if m.get("role") == "user":
            log.append({"who": "student", "text": m.get("content", "")})
        elif m.get("role") == "assistant":
            log.append({"who": "tutor",   "text": m.get("content", "")})
    return log


def _run_profile_update(chat_id: int) -> None:
    """Blocking: update knowledge profile from latest chat and persist to Supabase."""
    from profile import update_knowledge_profile
    from db import save_knowledge_profile_for_bot
    user = load_user(chat_id)
    conv_log = _build_profile_log(user)
    if not conv_log or not user.get("sb_user_id"):
        return
    updated = update_knowledge_profile(
        user.get("knowledge_profile") or {},
        user.get("name", ""), user.get("level", "A1"),
        user.get("language", "Danish"), user.get("bg_lang", "English"),
        conv_log, user.get("coaching_log", []),
        CLAUDE_KEY,
    )
    if updated:
        user["knowledge_profile"] = updated
        save_user(chat_id, user)
        save_knowledge_profile_for_bot(chat_id, updated)
        log.info("Knowledge profile updated for chat %s", chat_id)


async def _schedule_profile_update(chat_id: int) -> None:
    """Wait for inactivity then save the knowledge profile in the background."""
    await asyncio.sleep(PROFILE_UPDATE_DELAY)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, lambda: _run_profile_update(chat_id))
    _profile_tasks.pop(chat_id, None)


def _reset_profile_timer(chat_id: int) -> None:
    """Cancel any pending profile update and start a fresh countdown."""
    existing = _profile_tasks.pop(chat_id, None)
    if existing:
        existing.cancel()
    task = asyncio.create_task(_schedule_profile_update(chat_id))
    _profile_tasks[chat_id] = task

# Scribe v1 REST API needs an explicit language code to avoid misidentifying
# similar languages (e.g. Danish → Swedish). Different from STT_LANG_CODE
# which is used by the Streamlit app's Scribe v2 Realtime WebSocket stream.
_BOT_STT_LANG = {
    "Danish":                 "dan",
    "Portuguese (Brazilian)": "por",
}

import shutil
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

# ── User state ────────────────────────────────────────────────────────────────

DEFAULT_STATE: dict = {
    "name":              None,
    "level":             "A1",
    "bg_lang":           "English",
    "language":          "Danish",
    "voice_label":       "Mathias — male baritone",
    "chat":              [],
    "coaching_log":      [],
    "sb_user_id":        None,     # set when linked to a web account
    "knowledge_profile": {},       # JSON profile synced from Supabase
}

# Mapping from Supabase column names to bot state keys (they match, listed for clarity)
_PROFILE_KEYS = ("name", "level", "language", "voice_label", "bg_lang")


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


def load_user_synced(chat_id: int) -> dict:
    """Load user state, pulling fresh settings and chat history from Supabase if linked."""
    user = load_user(chat_id)
    if user.get("sb_user_id"):
        try:
            from db import get_telegram_profile, load_knowledge_profile_for_bot, load_bot_chat_history
            profile = get_telegram_profile(chat_id)
            if profile:
                for key in _PROFILE_KEYS:
                    if profile.get(key):
                        user[key] = profile[key]
            kp = load_knowledge_profile_for_bot(chat_id)
            if kp:
                user["knowledge_profile"] = kp
            history = load_bot_chat_history(chat_id)
            if history:
                user["chat"] = history
            save_user(chat_id, user)
        except Exception:
            pass
    return user


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
    data = {"model_id": "scribe_v1"}
    if lang_code:
        data["language_code"] = lang_code
    r = requests.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": ELEVEN_KEY},
        data=data,
        files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
        timeout=30,
    )
    if not r.ok:
        log.error("ElevenLabs STT error %s: %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json().get("text", "").strip()


# ── Inline keyboards ──────────────────────────────────────────────────────────

# ── Commands ──────────────────────────────────────────────────────────────────


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*SpeakPals* 🇩🇰\n\n"
        "Chat with your AI language tutor — type or send a voice note, "
        "and your tutor will reply in text and audio.\n\n"
        "*Commands:*\n"
        "/link CODE — link to your SpeakPals web account\n"
        "/help      — show this message\n\n"
        "*Tips:*\n"
        "• Link your web account with /link to sync your profile (name, level, language)\n"
        "• Voice notes are transcribed automatically — speak naturally\n"
        "• Your tutor echoes back what it heard before replying\n"
        "• Corrections appear in _italics_ — note them for next time",
        parse_mode="Markdown",
    )


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Link this Telegram account to a SpeakPals web account via a one-time code."""
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "Usage: `/link CODE`\n\n"
            "Get your code from the *Telegram & Calendar* settings page on the "
            "SpeakPals web app, then paste it here.",
            parse_mode="Markdown",
        )
        return

    code = context.args[0].strip()
    try:
        from db import consume_link_code, get_telegram_profile
        user_id = consume_link_code(code, chat_id)
    except Exception as exc:
        log.error("Link code error for chat %s: %s", chat_id, exc)
        await update.message.reply_text("⚠️ Could not reach the account service. Try again later.")
        return

    if not user_id:
        await update.message.reply_text(
            "❌ That code is invalid or has expired.\n\n"
            "Generate a new one on the SpeakPals settings page."
        )
        return

    # Persist the link and pull the web-app profile into the bot state
    user = load_user(chat_id)
    user["sb_user_id"] = user_id
    try:
        from db import load_knowledge_profile_for_bot
        profile = get_telegram_profile(chat_id)
        if profile:
            for key in _PROFILE_KEYS:
                if profile.get(key):
                    user[key] = profile[key]
        kp = load_knowledge_profile_for_bot(chat_id)
        if kp:
            user["knowledge_profile"] = kp
    except Exception:
        pass
    save_user(chat_id, user)

    await update.message.reply_text(
        "✅ *Account linked!*\n\n"
        "Your SpeakPals settings (name, level, language, voice) are now active. "
        "Just send a message to start chatting!",
        parse_mode="Markdown",
    )


# ── Pipeline helpers ──────────────────────────────────────────────────────────

def _build_context(user: dict) -> tuple[str, str, str, str]:
    """Return (system_prompt, voice_id, lang_code, model)."""
    tutor = Tutor.from_bot_user(user)
    system = build_system_prompt(
        tutor.name or "there", tutor.level, tutor.bg_lang,
        target_lang=tutor.target_lang,
        turn_count=user.get("turn_count", 0),
        knowledge_profile=tutor.knowledge_profile or None,
        free_conv=True,
        telegram=True,
    )
    return system, tutor.voice_id, tutor.tl_lang_code, tutor.model_id


def _claude_sync(system: str, user_text: str, chat: list, model: str) -> str:
    """Call Claude and return the raw response text (no TTS).

    Uses non-streaming mode — simpler and avoids SSE parsing fragility.
    The bot sends the full reply at once anyway so streaming offers no benefit.
    """
    sess     = get_session()
    messages = [{"role": m["role"], "content": m["content"]}
                for m in chat if m["role"] in {"user", "assistant"} and m["content"]]
    messages.append({"role": "user", "content": user_text})
    resp = sess.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": model, "max_tokens": 400, "temperature": 0.3,
              "system": system, "messages": messages,
              "output_config": {"format": {"type": "json_schema",
                                           "schema": VERDICT_SCHEMA}}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _tts_sync(spoken_text: str, voice_id: str, lang_code: str) -> bytes:
    """Generate TTS audio bytes (MP3) for the tutor voice.

    Uses tts_tutor_mixed to handle English prose that may contain embedded
    target-language phrases in quotes — correctly pronounced via lang_code.
    """
    return tts_tutor_mixed(clean_for_tts(spoken_text), voice_id, ELEVEN_KEY,
                           tl_lang_code=lang_code)


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
    loop = asyncio.get_running_loop()
    system, voice_id, lang_code, model = _build_context(user)

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

    spoken_text, _, _, is_correct, correction, _ = parse_claude_response(raw_claude)

    # Update conversation state
    user["chat"].extend([
        {"role": "user",      "content": user_text},
        {"role": "assistant", "content": spoken_text},
    ])
    if correction:
        user.setdefault("coaching_log", []).append(
            {"student": user_text, "correct_form": correction}
        )
    save_user(chat_id, user)
    # Persist chat history to Supabase so it survives app restarts
    if user.get("sb_user_id"):
        try:
            from db import save_bot_chat_history
            save_bot_chat_history(chat_id, user["chat"])
        except Exception:
            pass

    # ── Step 2: Send text reply immediately ───────────────────────────────────
    tutor_name = get_tutor_name(user["language"])
    await update.effective_message.reply_text(
        f"*💡 {tutor_name}:* {spoken_text}", parse_mode="Markdown"
    )
    if correction and not is_correct:
        await update.effective_message.reply_text(f"_✏️ {correction}_", parse_mode="Markdown")

    # ── Step 3: TTS + OGG conversion (show upload indicator while waiting) ────
    await context.bot.send_chat_action(chat_id, "upload_voice")
    try:
        mp3_bytes = await loop.run_in_executor(
            _executor,
            lambda: _tts_sync(spoken_text, voice_id, lang_code)
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

    # Start/reset the inactivity timer — profile is saved after 2 min of silence
    _reset_profile_timer(chat_id)


# ── Message handlers ──────────────────────────────────────────────────────────

async def text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = update.effective_chat.id
    user    = load_user_synced(chat_id)
    await _process_message(update, context, update.message.text.strip(), user, chat_id)


async def voice_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    chat_id = update.effective_chat.id
    user    = load_user_synced(chat_id)

    await context.bot.send_chat_action(chat_id, "typing")

    # Download the voice note Telegram sent as OGG
    voice_file  = await context.bot.get_file(update.message.voice.file_id)
    audio_bytes = bytes(await voice_file.download_as_bytearray())
    lang_code   = _BOT_STT_LANG.get(user["language"], "dan")

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

def build_app() -> Application:
    """Build and return the configured Application (without starting polling)."""
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set. Add it to keys.env and try again."
        )
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("link", cmd_link))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    return app


def start_bot_thread() -> None:
    """Start the bot in a background thread with its own event loop.
    Avoids run_polling() which registers OS signal handlers (main-thread only)."""
    import threading

    async def _run_async():
        app = build_app()
        log.info("SpeakPals bot starting (polling, embedded thread)…")
        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            # Block forever — daemon thread dies when the main process exits
            await asyncio.Event().wait()

    def _run():
        asyncio.run(_run_async())

    t = threading.Thread(target=_run, daemon=True, name="speakpals-bot")
    t.start()


def main() -> None:
    build_app().run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
