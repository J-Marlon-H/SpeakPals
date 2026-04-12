# SpeakPals — entry point
# Streamlit Cloud is configured to run this file.
# All page routing is defined here; each page is exec'd by pg.run().
import streamlit as st
from scene_images import preload_all_images

# Warm the image cache on first server start so home page loads instantly
preload_all_images()

# ── Telegram bot (embedded background thread) ─────────────────────────────────
@st.cache_resource
def _start_telegram_bot():
    """Start the Telegram bot once per server process.
    Only starts if TELEGRAM_BOT_ENABLED is set to 'true' in secrets or env."""
    import os
    enabled = False
    try:
        enabled = st.secrets.get("TELEGRAM_BOT_ENABLED", "false").lower() == "true"
    except Exception:
        enabled = os.getenv("TELEGRAM_BOT_ENABLED", "false").lower() == "true"
    if not enabled:
        return
    try:
        from telegram_bot import start_bot_thread
        start_bot_thread()
    except Exception as e:
        import logging
        logging.getLogger("speakpals").warning("Telegram bot not started: %s", e)

_start_telegram_bot()

pages = [
    st.Page("pages/home.py",              title="Home",         default=True),
    st.Page("pages/login.py",             title="Login",        visibility="hidden"),
    st.Page("pages/account.py",           title="Account",      visibility="hidden"),
    st.Page("pages/telegram_settings.py", title="Telegram",     visibility="hidden"),
    st.Page("pages/scene_select.py",      title="Scene Select", visibility="hidden"),
    st.Page("pages/lesson.py",            title="Lesson",       visibility="hidden"),
    st.Page("pages/feedback.py",          title="Feedback",     visibility="hidden"),
    st.Page("pages/onboarding.py",        title="Onboarding",   visibility="hidden"),
]
pg = st.navigation(pages, position="hidden")
pg.run()
