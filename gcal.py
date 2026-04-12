"""
Google Calendar integration for SpeakPals.
──────────────────────────────────────────
Uses the OAuth 2.0 Device Flow — no redirect URL needed, works on VPS and web.

Tokens are keyed by a user_key string:
  - Telegram bot:  str(chat_id)        e.g. "1994825035"
  - Web app:       "web_{sb_user_id}"  e.g. "web_abc123"

This makes it easy to sync both via database later — just migrate the files
to DB rows keyed by user_key.

Setup (one-time):
  1. Go to console.cloud.google.com
  2. Create a project → Enable "Google Calendar API"
  3. APIs & Services → Credentials → Create OAuth client ID
     Type: "TV and Limited Input devices"
  4. Download JSON → save as client_secret_*.json in the project root
     OR paste the JSON as GOOGLE_CLIENT_SECRET_JSON in Streamlit secrets
"""
from __future__ import annotations

import json
import logging
import pathlib
import time
from datetime import datetime, timezone, timedelta

import requests

log = logging.getLogger("speakpals.gcal")

TOKENS_DIR = pathlib.Path("telegram_users")   # reuse existing dir for now

DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL       = "https://oauth2.googleapis.com/token"
CALENDAR_SCOPE  = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_API    = "https://www.googleapis.com/calendar/v3"


# ── Credentials ───────────────────────────────────────────────────────────────

def _find_creds_file() -> pathlib.Path | None:
    candidates = list(pathlib.Path(".").glob("client_secret_*.json")) + \
                 [pathlib.Path("google_credentials.json")]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_client() -> tuple[str, str]:
    """Return (client_id, client_secret) from Streamlit secrets or file on disk."""
    raw = None
    try:
        import streamlit as st
        raw = st.secrets["GOOGLE_CLIENT_SECRET_JSON"]
    except Exception:
        pass

    if raw:
        data = json.loads(raw)
    else:
        path = _find_creds_file()
        if not path:
            raise FileNotFoundError(
                "Google credentials not found. Either:\n"
                "  • Set GOOGLE_CLIENT_SECRET_JSON in Streamlit secrets\n"
                "  • Place client_secret_*.json in the project root (local)"
            )
        data = json.loads(path.read_text())

    info = data.get("installed") or data.get("web") or data
    return info["client_id"], info["client_secret"]


# ── Token storage (keyed by user_key string) ──────────────────────────────────

def _token_file(user_key: str) -> pathlib.Path:
    return TOKENS_DIR / f"{user_key}_gcal.json"


def load_token(user_key: str) -> dict | None:
    f = _token_file(user_key)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return None


def save_token(user_key: str, token: dict) -> None:
    TOKENS_DIR.mkdir(exist_ok=True)
    _token_file(user_key).write_text(json.dumps(token, indent=2))


def revoke_token(user_key: str) -> None:
    f = _token_file(user_key)
    if f.exists():
        f.unlink()


def is_connected(user_key: str) -> bool:
    return _token_file(user_key).exists()


# ── Device flow ───────────────────────────────────────────────────────────────

def start_device_flow() -> dict:
    """Start OAuth device flow. Returns device_code, user_code, verification_url, etc."""
    client_id, _ = _load_client()
    r = requests.post(
        DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": CALENDAR_SCOPE},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def try_poll_once(device_code: str) -> dict | None:
    """
    Make a single poll attempt. Returns:
      - token dict if approved
      - None if still pending
    Raises PermissionError if user denied, ValueError if code expired.
    Used by the Streamlit web app (polls on each rerun).
    """
    client_id, client_secret = _load_client()
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "device_code":   device_code,
            "grant_type":    "urn:ietf:params:oauth:grant-type:device_code",
        },
        timeout=15,
    )
    data = r.json()
    error = data.get("error")
    if error in ("authorization_pending", "slow_down"):
        return None
    if error == "access_denied":
        raise PermissionError("User denied calendar access.")
    if error == "expired_token":
        raise ValueError("Device code expired.")
    if "access_token" in data:
        data["obtained_at"] = time.time()
        return data
    return None


def poll_for_token(device_code: str, interval: int = 5, expires_in: int = 1800) -> dict | None:
    """
    Blocking poll loop — used by the Telegram bot background thread.
    Returns token dict on success, None on timeout.
    Raises PermissionError if user denied.
    """
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        try:
            token = try_poll_once(device_code)
            if token:
                return token
        except PermissionError:
            raise
        except ValueError:
            return None
    return None


# ── Token refresh ─────────────────────────────────────────────────────────────

def _refresh(token: dict) -> dict:
    client_id, client_secret = _load_client()
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "refresh_token": token["refresh_token"],
            "grant_type":    "refresh_token",
        },
        timeout=15,
    )
    r.raise_for_status()
    return {**token, **r.json(), "obtained_at": time.time()}


def _valid_token(user_key: str) -> dict | None:
    token = load_token(user_key)
    if not token:
        return None
    expires_in  = token.get("expires_in", 3600)
    obtained_at = token.get("obtained_at", 0)
    if time.time() > obtained_at + expires_in - 300:
        try:
            token = _refresh(token)
            save_token(user_key, token)
        except Exception as e:
            log.warning("Token refresh failed for %s: %s", user_key, e)
            return None
    return token


# ── Calendar API ──────────────────────────────────────────────────────────────

def _fetch_raw_items(user_key: str, days: int = 7) -> list[dict]:
    token = _valid_token(user_key)
    if not token:
        return []
    now   = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    try:
        r = requests.get(
            f"{CALENDAR_API}/calendars/primary/events",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            params={
                "timeMin":      now.isoformat(),
                "timeMax":      until.isoformat(),
                "maxResults":   10,
                "singleEvents": "true",
                "orderBy":      "startTime",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        log.warning("Calendar fetch failed for %s: %s", user_key, e)
        return []


def _format_item(item: dict) -> tuple[str, str]:
    title  = item.get("summary", "Untitled event")
    start  = item.get("start", {})
    dt_str = start.get("dateTime") or start.get("date", "")
    try:
        dt = datetime.fromisoformat(dt_str)
        label = dt.strftime("%A %b %-d at %H:%M") if "T" in dt_str \
                else dt.strftime("%A %b %-d (all day)")
    except Exception:
        label = dt_str
    return label, title


def get_upcoming_events(user_key: str, days: int = 7) -> list[str]:
    """Return human-readable strings: 'Monday Apr 14 at 10:00 — Team standup'"""
    return [f"{label} — {title}"
            for label, title in (_format_item(i) for i in _fetch_raw_items(user_key, days))]


def get_upcoming_events_raw(user_key: str, days: int = 7) -> list[dict]:
    """Return list of dicts with 'title' and 'date_label' for scene generation."""
    result = []
    for item in _fetch_raw_items(user_key, days):
        label, title = _format_item(item)
        result.append({"title": title, "date_label": label})
    return result
