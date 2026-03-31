"""db.py — Supabase client, auth, and per-user data access."""
from __future__ import annotations
import os
from dotenv import load_dotenv

try:
    from supabase import create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False

load_dotenv("keys.env")


def _secret(key: str) -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")


SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_ANON_KEY") or _secret("SUPABASE_PUBLISHABLE_KEY")


def _client(access_token: str | None = None):
    """Return a Supabase client, optionally authenticated with a user JWT."""
    if not _SUPABASE_AVAILABLE:
        raise RuntimeError("supabase package not installed")
    c = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore[name-defined]
    if access_token:
        c.auth.set_session(access_token, "")
    return c


# ── Auth ──────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> tuple[dict | None, str | None]:
    """Returns (user_dict, error_str)."""
    try:
        res = _client().auth.sign_up({"email": email, "password": password})
        if res.user:
            return {"id": res.user.id, "email": res.user.email}, None
        return None, "Sign-up failed — please try again."
    except Exception as e:
        return None, str(e)


def sign_in(email: str, password: str) -> tuple[dict | None, str | None]:
    """Returns (session_dict, error_str).
    session_dict has keys: access_token, refresh_token, user_id, email.
    """
    try:
        res = _client().auth.sign_in_with_password({"email": email, "password": password})
        if res.session and res.user:
            return {
                "access_token":  res.session.access_token,
                "refresh_token": res.session.refresh_token,
                "user_id":       res.user.id,
                "email":         res.user.email,
            }, None
        return None, "Login failed — please try again."
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg:
            return None, "Incorrect email or password."
        if "Email not confirmed" in msg:
            return None, "Please confirm your email before logging in."
        return None, msg


def sign_out(access_token: str) -> None:
    try:
        _client(access_token).auth.sign_out()
    except Exception:
        pass


# ── Profile key mapping ───────────────────────────────────────────────────────
# App session_state uses "s_" prefixed keys; DB columns use plain names.

_KEY_TO_COL: dict[str, str] = {
    "s_name":        "name",
    "s_level":       "level",
    "s_language":    "language",
    "s_voice_label": "voice_label",
    "s_model_label": "model_label",
    "s_bg_lang":     "bg_lang",
}
_COL_TO_KEY: dict[str, str] = {v: k for k, v in _KEY_TO_COL.items()}


def _to_db(data: dict) -> dict:
    """Translate app keys → DB column names."""
    return {_KEY_TO_COL.get(k, k): v for k, v in data.items()}


def _from_db(data: dict) -> dict:
    """Translate DB column names → app keys."""
    return {_COL_TO_KEY.get(k, k): v for k, v in data.items()}


# ── User profile / settings ───────────────────────────────────────────────────

def load_profile(user_id: str, access_token: str) -> dict:
    """Return the user's settings row as app-keyed dict, or {} if not found."""
    try:
        res = (_client(access_token)
               .table("users")
               .select("*")
               .eq("id", user_id)
               .maybe_single()
               .execute())
        if res is not None and res.data:
            return _from_db(dict(res.data))
        return {}
    except Exception:
        return {}


def upsert_profile(user_id: str, access_token: str, data: dict) -> None:
    """Create or update the user's settings row."""
    try:
        (_client(access_token)
         .table("users")
         .upsert({"id": user_id, **_to_db(data)})
         .execute())
    except Exception:
        pass


# ── Session history ───────────────────────────────────────────────────────────

def save_session(user_id: str, access_token: str, session_data: dict) -> None:
    """Insert a completed lesson session."""
    try:
        (_client(access_token)
         .table("sessions")
         .insert({"user_id": user_id, **session_data})
         .execute())
    except Exception:
        pass


def load_sessions(user_id: str, access_token: str) -> list[dict]:
    """Return all sessions for this user, newest first."""
    try:
        res = (_client(access_token)
               .table("sessions")
               .select("*")
               .eq("user_id", user_id)
               .order("created_at", desc=True)
               .execute())
        return res.data or []
    except Exception:
        return []


# ── Streamlit auth guard ──────────────────────────────────────────────────────

def require_auth() -> None:
    """Call at the top of every protected page.
    Redirects to the login page if no session is active.
    Skipped entirely if Supabase is not configured (e.g. hosted without secrets).
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    import streamlit as st
    if "sb_user_id" not in st.session_state:
        st.switch_page("pages/login.py")
