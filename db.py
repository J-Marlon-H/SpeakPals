"""db.py — Supabase client, auth, and per-user data access."""
from __future__ import annotations
import os
import json as _json
from dotenv import load_dotenv

# ── Local dev: bypass Windows SSL certificate chain issues ────────────────────
# Supabase uses httpx which has its own SSL stack — the stdlib ssl monkey-patch
# doesn't reach it. Patch httpx.Client / AsyncClient to skip verification and
# also point the stdlib ssl context at certifi's bundle as a belt-and-suspenders fix.
# Guard is keys.env presence so this never runs on the cloud deployment.
if os.path.exists("keys.env"):
    import ssl as _ssl
    import httpx as _httpx

    # stdlib fallback (for requests-based code)
    _ssl._create_default_https_context = _ssl._create_unverified_context

    # httpx patch — supabase-py explicitly passes verify=True so we must force-override it
    _httpx_Client_orig       = _httpx.Client.__init__
    _httpx_AsyncClient_orig  = _httpx.AsyncClient.__init__

    def _httpx_client_no_verify(self, *args, **kwargs):
        kwargs["verify"] = False          # force — supabase passes verify=True explicitly
        _httpx_Client_orig(self, *args, **kwargs)

    def _httpx_async_client_no_verify(self, *args, **kwargs):
        kwargs["verify"] = False
        _httpx_AsyncClient_orig(self, *args, **kwargs)

    _httpx.Client.__init__       = _httpx_client_no_verify        # type: ignore[method-assign]
    _httpx.AsyncClient.__init__  = _httpx_async_client_no_verify  # type: ignore[method-assign]

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


def refresh_session(refresh_token: str) -> tuple[dict | None, str | None]:
    """Exchange a refresh token for a new session. Returns (session_dict, error_str)."""
    try:
        res = _client().auth.refresh_session(refresh_token)
        if res.session and res.user:
            return {
                "access_token":  res.session.access_token,
                "refresh_token": res.session.refresh_token,
                "user_id":       res.user.id,
                "email":         res.user.email or "",
            }, None
        return None, "Session expired."
    except Exception as e:
        return None, str(e)


def sign_out(access_token: str) -> None:
    try:
        _client(access_token).auth.sign_out()
    except Exception:
        pass


def send_reset_email(email: str) -> str | None:
    """Send a password-reset email via Supabase. Returns error string or None on success."""
    try:
        _client().auth.reset_password_for_email(email)
        return None
    except Exception as e:
        return str(e)


def verify_recovery_token(token_hash: str) -> tuple[dict | None, str | None]:
    """Exchange a Supabase recovery token_hash (from the reset-link URL) for a session.
    Returns (session_dict, error_str)."""
    try:
        res = _client().auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
        if res.session and res.user:
            return {
                "access_token":  res.session.access_token,
                "refresh_token": res.session.refresh_token,
                "user_id":       res.user.id,
                "email":         res.user.email or "",
            }, None
        return None, "Recovery failed — please request a new reset link."
    except Exception as e:
        return None, str(e)


def update_password(access_token: str, new_password: str, refresh_token: str = "") -> str | None:
    """Update the authenticated user's password. Returns error string or None on success."""
    try:
        c = create_client(SUPABASE_URL, SUPABASE_KEY)  # type: ignore[name-defined]
        c.auth.set_session(access_token, refresh_token)
        c.auth.update_user({"password": new_password})
        return None
    except Exception as e:
        return str(e)


def get_user_email(access_token: str) -> str:
    """Return the email address for the authenticated user, or '' on failure."""
    try:
        res = _client(access_token).auth.get_user(access_token)
        return res.user.email if res and res.user else ""
    except Exception:
        return ""


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


# ── Telegram account linking ─────────────────────────────────────────────────

def create_link_code(user_id: str, access_token: str) -> tuple[str | None, str | None]:
    """Generate a 6-char link code valid for 10 minutes.
    Returns (code, None) on success or (None, error_message) on failure."""
    import secrets, string
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    try:
        c = _client(access_token)
        c.table("telegram_link_codes").delete().eq("user_id", user_id).execute()
        c.table("telegram_link_codes").insert({"code": code, "user_id": user_id}).execute()
        return code, None
    except Exception as e:
        return None, str(e)


def consume_link_code(code: str, chat_id: int) -> str | None:
    """Atomically validate the code and write chat_id to the user row.
    Returns user_id on success, None if the code is invalid/expired.
    Calls the link_telegram_account RPC (SECURITY DEFINER — no JWT needed)."""
    try:
        res = (_client()
               .rpc("link_telegram_account", {"p_code": code.upper(), "p_chat_id": chat_id})
               .execute())
        uid = res.data
        return str(uid) if uid else None
    except Exception:
        return None


def get_telegram_profile(chat_id: int) -> dict:
    """Return the user profile keyed by plain DB column names (name, level, …).
    Uses the get_telegram_profile RPC (SECURITY DEFINER — no JWT needed).
    Returns {} when the chat_id is not linked."""
    try:
        res = (_client()
               .rpc("get_telegram_profile", {"p_chat_id": chat_id})
               .execute())
        rows = res.data or []
        return dict(rows[0]) if rows else {}
    except Exception:
        return {}


def get_telegram_link_status(user_id: str, access_token: str) -> int | None:
    """Return the linked telegram_chat_id for this user, or None if not linked."""
    try:
        res = (_client(access_token)
               .table("users")
               .select("telegram_chat_id")
               .eq("id", user_id)
               .single()
               .execute())
        if res and res.data:
            return res.data.get("telegram_chat_id")
        return None
    except Exception:
        return None


def unlink_telegram(user_id: str, access_token: str) -> None:
    """Remove the telegram_chat_id from the user's account."""
    try:
        (_client(access_token)
         .table("users")
         .update({"telegram_chat_id": None})
         .eq("id", user_id)
         .execute())
    except Exception:
        pass


# ── User knowledge profile ────────────────────────────────────────────────────

def load_knowledge_profile(user_id: str, access_token: str) -> dict:
    """Return the user's knowledge profile JSON, or {} if none exists yet."""
    try:
        res = (_client(access_token)
               .table("user_knowledge_profiles")
               .select("profile")
               .eq("user_id", user_id)
               .maybe_single()
               .execute())
        if res is not None and res.data:
            p = res.data.get("profile")
            if not p:
                return {}
            return p if isinstance(p, dict) else _json.loads(p)
        return {}
    except Exception:
        return {}


def save_knowledge_profile(user_id: str, access_token: str, profile: dict) -> None:
    """Upsert the user's knowledge profile JSON."""
    import datetime as _dt
    try:
        (_client(access_token)
         .table("user_knowledge_profiles")
         .upsert({
             "user_id":    user_id,
             "profile":    _json.dumps(profile, ensure_ascii=False),
             "updated_at": _dt.datetime.utcnow().isoformat() + "Z",
         })
         .execute())
    except Exception:
        pass


def save_knowledge_profile_for_bot(chat_id: int, profile: dict) -> None:
    """Upsert a user's knowledge profile from the Telegram bot (no user JWT needed).

    Uses the upsert_knowledge_profile_by_chat_id RPC (SECURITY DEFINER).

    Required SQL (run once in Supabase SQL editor):

        CREATE OR REPLACE FUNCTION upsert_knowledge_profile_by_chat_id(
            p_chat_id BIGINT, p_profile JSONB)
        RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
        DECLARE v_uid UUID; BEGIN
          SELECT id INTO v_uid FROM users WHERE telegram_chat_id = p_chat_id;
          IF NOT FOUND THEN RETURN; END IF;
          INSERT INTO user_knowledge_profiles (user_id, profile, updated_at)
          VALUES (v_uid, p_profile, now())
          ON CONFLICT (user_id) DO UPDATE
            SET profile = p_profile, updated_at = now();
        END; $$;
    """
    try:
        _client().rpc("upsert_knowledge_profile_by_chat_id",
                      {"p_chat_id": chat_id,
                       "p_profile": _json.dumps(profile, ensure_ascii=False)}).execute()
    except Exception:
        pass


def load_knowledge_profile_for_bot(chat_id: int) -> dict:
    """Load a user's knowledge profile from the Telegram bot (no user JWT needed).

    Uses the get_knowledge_profile_by_chat_id RPC (SECURITY DEFINER) — same
    pattern as get_telegram_profile.  Returns {} if not linked or no profile yet.
    """
    try:
        res = (_client()
               .rpc("get_knowledge_profile_by_chat_id", {"p_chat_id": chat_id})
               .execute())
        data = res.data
        if not data:
            return {}
        return data if isinstance(data, dict) else _json.loads(data)
    except Exception:
        return {}


def delete_knowledge_profile(user_id: str, access_token: str) -> None:
    """Delete the user's knowledge profile row entirely."""
    try:
        (_client(access_token)
         .table("user_knowledge_profiles")
         .delete()
         .eq("user_id", user_id)
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
        if st.session_state.get("_cookie_restoring"):
            # Cookie component is still initialising — pause here so the render
            # completes and the React component can send back the cookie value.
            # The component's setComponentValue() will trigger an automatic rerun.
            st.stop()
        st.switch_page("pages/login.py")
