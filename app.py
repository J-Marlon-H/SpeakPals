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

# ── Session restore from cookie ───────────────────────────────────────────────
# Cookie components need one render cycle to initialize before data is readable.
# We do a single controlled rerun the first time, then read on the second pass.
if "sb_user_id" not in st.session_state:
    # st.rerun() and st.stop() raise subclasses of Exception — they MUST stay
    # outside any try/except block or they get silently swallowed.
    _stored_token = None
    _session_restored = False
    try:
        from streamlit_cookies_controller import CookieController
        from db import refresh_session
        _cookies = CookieController(key="sp_ctrl")
        _stored_token = _cookies.get("sp_refresh_token")
        if _stored_token:
            _sess, _err = refresh_session(_stored_token)
            if _sess:
                st.session_state.sb_access_token  = _sess["access_token"]
                st.session_state.sb_refresh_token = _sess["refresh_token"]
                st.session_state.sb_user_id       = _sess["user_id"]
                st.session_state.sb_email         = _sess["email"]
                _cookies.set("sp_refresh_token", _sess["refresh_token"])
                _session_restored = True
    except Exception:
        pass

    if _session_restored:
        st.rerun()
    elif _stored_token is None and not st.session_state.get("_cookie_init_done"):
        # First render — component hasn't sent back cookie data yet.
        # Set a flag so require_auth() waits (via st.stop()) instead of
        # redirecting to login. pg.run() still executes, which keeps
        # Streamlit's navigation state pointing at the correct page.
        st.session_state["_cookie_init_done"] = True
        st.session_state["_cookie_restoring"] = True
    else:
        # Cookie init is complete (token found-and-restored, or no cookie at all).
        st.session_state.pop("_cookie_restoring", None)

pages = [
    st.Page("pages/home.py",               title="Home",              default=True),
    st.Page("pages/login.py",              title="Login",             visibility="hidden"),
    st.Page("pages/account.py",            title="Account",           visibility="hidden"),
    st.Page("pages/telegram_settings.py",  title="Telegram",          visibility="hidden"),
    st.Page("pages/scene_select.py",       title="Scene Select",      visibility="hidden"),
    st.Page("pages/lesson.py",             title="Lesson",            visibility="hidden"),
    st.Page("pages/feedback.py",           title="Feedback",          visibility="hidden"),
]
pg = st.navigation(pages, position="hidden")
pg.run()
