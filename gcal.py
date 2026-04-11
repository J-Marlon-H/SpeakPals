"""
Google Calendar integration for SpeakPals Telegram bot.
──────────────────────────────────────────────────────
Uses the OAuth 2.0 Device Flow — no redirect URL needed, works on VPS.

Setup (one-time):
  1. Go to console.cloud.google.com
  2. Create a project → Enable "Google Calendar API"
  3. APIs & Services → Credentials → Create OAuth client ID
     Type: "TV and Limited Input devices"
  4. Download JSON → save as google_credentials.json in the project root
"""
from __future__ import annotations

import json
import logging
import pathlib
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

log = logging.getLogger("speakpals_bot.gcal")

USERS_DIR   = pathlib.Path("telegram_users")

def _find_creds_file() -> pathlib.Path | None:
    """Find the Google OAuth credentials file by common names."""
    candidates = list(pathlib.Path(".").glob("client_secret_*.json")) + \
                 [pathlib.Path("google_credentials.json")]
    for p in candidates:
        if p.exists():
            return p
    return None

DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL       = "https://oauth2.googleapis.com/token"
CALENDAR_SCOPE  = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_API    = "https://www.googleapis.com/calendar/v3"


# ── Credential file helpers ───────────────────────────────────────────────────

def _load_client() -> tuple[str, str]:
    """Return (client_id, client_secret) from the Google OAuth credentials file."""
    path = _find_creds_file()
    if not path:
        raise FileNotFoundError(
            "Google credentials file not found. "
            "Download client_secret_*.json from Google Cloud Console "
            "(APIs & Services → Credentials → OAuth 2.0 Client IDs) "
            "and place it in the project root."
        )
    data = json.loads(path.read_text())
    info = data.get("installed") or data.get("web") or data
    return info["client_id"], info["client_secret"]


def _token_file(chat_id: int) -> pathlib.Path:
    return USERS_DIR / f"{chat_id}_gcal.json"


def load_token(chat_id: int) -> dict | None:
    f = _token_file(chat_id)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return None


def save_token(chat_id: int, token: dict) -> None:
    USERS_DIR.mkdir(exist_ok=True)
    _token_file(chat_id).write_text(json.dumps(token, indent=2))


def revoke_token(chat_id: int) -> None:
    f = _token_file(chat_id)
    if f.exists():
        f.unlink()


# ── Device flow ───────────────────────────────────────────────────────────────

def start_device_flow() -> dict:
    """
    Start the OAuth device flow.
    Returns the full response dict including:
      device_code, user_code, verification_url, expires_in, interval
    """
    client_id, _ = _load_client()
    r = requests.post(
        DEVICE_CODE_URL,
        data={"client_id": client_id, "scope": CALENDAR_SCOPE},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def poll_for_token(device_code: str, interval: int = 5, expires_in: int = 1800) -> dict | None:
    """
    Poll Google's token endpoint until the user approves or the code expires.
    Returns the token dict on success, None on timeout.
    Raises on hard errors (access_denied, etc.).
    """
    client_id, client_secret = _load_client()
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
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
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error == "access_denied":
            raise PermissionError("User denied calendar access.")
        if error == "expired_token":
            return None
        if "access_token" in data:
            data["obtained_at"] = time.time()
            return data
    return None


# ── Token refresh ─────────────────────────────────────────────────────────────

def _refresh(token: dict) -> dict:
    """Exchange a refresh_token for a new access_token."""
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
    new = r.json()
    token = {**token, **new, "obtained_at": time.time()}
    return token


def _valid_token(chat_id: int) -> dict | None:
    """Load token, refresh if expired, return up-to-date token or None."""
    token = load_token(chat_id)
    if not token:
        return None
    expires_in  = token.get("expires_in", 3600)
    obtained_at = token.get("obtained_at", 0)
    # Refresh 5 minutes before expiry
    if time.time() > obtained_at + expires_in - 300:
        try:
            token = _refresh(token)
            save_token(chat_id, token)
        except Exception as e:
            log.warning("Token refresh failed for %s: %s", chat_id, e)
            return None
    return token


# ── Calendar API ──────────────────────────────────────────────────────────────

def get_upcoming_events(chat_id: int, days: int = 7) -> list[str]:
    """
    Fetch the next `days` days of events from the user's primary calendar.
    Returns a list of human-readable strings like:
      "Monday Apr 14 at 10:00 — Team standup"
    Returns an empty list if not connected or on error.
    """
    token = _valid_token(chat_id)
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
    except Exception as e:
        log.warning("Calendar fetch failed for %s: %s", chat_id, e)
        return []

    events = []
    for item in r.json().get("items", []):
        title = item.get("summary", "Untitled event")
        start = item.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        try:
            if "T" in dt_str:
                dt = datetime.fromisoformat(dt_str)
                label = dt.strftime("%A %b %-d at %H:%M")
            else:
                dt = datetime.fromisoformat(dt_str)
                label = dt.strftime("%A %b %-d (all day)")
        except Exception:
            label = dt_str
        events.append(f"{label} — {title}")

    return events


def is_connected(chat_id: int) -> bool:
    return _token_file(chat_id).exists()
