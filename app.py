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

# ── Navigation setup (must happen before any st.switch_page call) ─────────────
pages = [
    st.Page("pages/home.py",              title="Home",           default=True),
    st.Page("pages/login.py",             title="Login",          visibility="hidden"),
    st.Page("pages/reset_password.py",    title="Reset Password", visibility="hidden"),
    st.Page("pages/account.py",           title="Account",        visibility="hidden"),
    st.Page("pages/telegram_settings.py", title="Telegram",       visibility="hidden"),
    st.Page("pages/scene_select.py",      title="Scene Select",   visibility="hidden"),
    st.Page("pages/lesson.py",            title="Lesson",         visibility="hidden"),
    st.Page("pages/feedback.py",          title="Feedback",       visibility="hidden"),
    st.Page("pages/onboarding.py",        title="Onboarding",     visibility="hidden"),
]
pg = st.navigation(pages, position="hidden")

# ── Intercept password-reset redirect before session restore ───────────────────
# Supabase redirects back with ?code= (PKCE) or ?token_hash=&type=recovery.
# Route to the dedicated reset page. Guard pg.title to prevent looping.
_qp = st.query_params
if (_qp.get("code") or (_qp.get("token_hash") and _qp.get("type") == "recovery")) \
        and pg.title != "Reset Password":
    st.switch_page("pages/reset_password.py")

# ── Cookie controller (needed for both restore-on-load and persist-after-login) ─
# st.rerun() and st.stop() raise subclasses of Exception — they MUST stay
# outside any try/except block or they get silently swallowed.
_cookies = None
try:
    from streamlit_cookies_controller import CookieController
    _cookies = CookieController(key="sp_ctrl")
except Exception:
    pass

# ── Session restore from cookie ───────────────────────────────────────────────
# Cookie components need one render cycle to initialize before data is readable.
# We do a single controlled rerun the first time, then read on the second pass.
if "sb_user_id" not in st.session_state:
    _stored_token = None
    _session_restored = False

    if _cookies is not None:
        try:
            from db import refresh_session
            _stored_token = _cookies.get("sp_refresh_token")
            if _stored_token:
                _sess, _err = refresh_session(_stored_token)
                if _sess:
                    st.session_state.sb_access_token  = _sess["access_token"]
                    st.session_state.sb_refresh_token = _sess["refresh_token"]
                    st.session_state.sb_user_id       = _sess["user_id"]
                    st.session_state.sb_email         = _sess["email"]
                    _session_restored = True
        except Exception:
            pass

    if _session_restored:
        st.rerun()
    elif _cookies is not None and _stored_token is None and not st.session_state.get("_cookie_init_done"):
        # First render — component hasn't sent back cookie data yet.
        # Set a flag so require_auth() waits (via st.stop()) instead of
        # redirecting to login. Only set when the component actually loaded;
        # if the import failed this flag must not be set or the app hangs blank.
        st.session_state["_cookie_init_done"] = True
        st.session_state["_cookie_restoring"] = True
    else:
        # Cookie init is complete (token found-and-restored, or no cookie at all).
        st.session_state.pop("_cookie_restoring", None)

# ── Persist refresh token to cookie after login (or after token rotation) ─────
# The login/onboarding pages set sb_refresh_token in session state but can't
# write cookies directly. app.py runs on every render so we catch it here.
# _last_written_token guards against re-writing the same value every render.
elif _cookies is not None and "sb_refresh_token" in st.session_state:
    _current_rt = st.session_state.sb_refresh_token
    if st.session_state.get("_last_written_token") != _current_rt:
        _cookies.set("sp_refresh_token", _current_rt)
        st.session_state["_last_written_token"] = _current_rt

# ── Load knowledge profile once per login session ────────────────────────────
# knowledge_profile is NOT in LESSON_STATE_KEYS so it persists across lessons.
# Load it here once so every page (lesson, free conv) can read it from session
# state without a DB round-trip on every render.  feedback.py keeps it fresh
# by writing the updated profile back to session state after each lesson.
if "knowledge_profile" not in st.session_state and "sb_user_id" in st.session_state:
    try:
        from db import load_knowledge_profile
        st.session_state["knowledge_profile"] = load_knowledge_profile(
            st.session_state.sb_user_id,
            st.session_state.sb_access_token,
        )
    except Exception:
        st.session_state["knowledge_profile"] = {}

pg.run()
