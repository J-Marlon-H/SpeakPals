"""One-off script to seed default prototype users into Supabase.
Run with: .venv/bin/python create_users.py
"""
from db import sign_up, sign_in, upsert_profile
from pipeline import SETTINGS_DEFAULTS

USERS = [
    {"email": "alice@speakpals.dev",  "password": "speakpals1",
     "profile": {**SETTINGS_DEFAULTS, "s_name": "Alice",  "s_level": "A1", "s_bg_lang": "English"}},
    {"email": "bob@speakpals.dev",    "password": "speakpals2",
     "profile": {**SETTINGS_DEFAULTS, "s_name": "Bob",    "s_level": "A2", "s_bg_lang": "German"}},
    {"email": "milla@speakpals.dev",  "password": "speakpals3",
     "profile": {**SETTINGS_DEFAULTS, "s_name": "Milla",  "s_level": "B1", "s_bg_lang": "English"}},
]

for u in USERS:
    user, err = sign_up(u["email"], u["password"])
    if err:
        print(f"[SKIP] {u['email']}: {err}")
        # Still try to sign in and upsert profile in case user already exists
    else:
        print(f"[OK]   {u['email']} created")

    session, err2 = sign_in(u["email"], u["password"])
    if session:
        upsert_profile(session["user_id"], session["access_token"], u["profile"])
        print(f"       profile saved for {u['email']}")
    else:
        print(f"       could not sign in: {err2}")
