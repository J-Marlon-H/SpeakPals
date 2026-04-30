"""
Generate ElevenLabs TTS audio for each restaurant scene.
Output: assets/restaurant/scene1.mp3 … scene6.mp3
Run from project root: python generate_scene_audio.py
"""
import requests
import pathlib
from dotenv import load_dotenv
from db import _secret

load_dotenv("keys.env")

ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
VOICE_ID   = "ygiXC2Oa1BiHksD3WkJZ"  # Mathias — male baritone

LINES = {
    "scene1": "Hej! Velkommen! Vil du sidde ved baren eller ved vinduet?",
    "scene2": "Velkommen til vores restaurant! Følg mig venligst – her er et bord ved vinduet. Værsgo at sætte jer. Her er menuen. Vi har ramen og gyoza i dag. Hvad må det være?",
    "scene3": "Ja, selvfølgelig – det ordner jeg med det samme. Værsgo.",
    "scene4": "Værsgo! Ramen til dig! God appetit!",
    "scene5": "Selvfølgelig, jeg henter en gaffel til dig. Undskyld fejlen.",
    "scene6": "Jeg håber, at alt var lækkert, og vi ses forhåbentlig igen snart.",
}

out = pathlib.Path("assets/restaurant")
out.mkdir(parents=True, exist_ok=True)

for name, text in LINES.items():
    print(f"Generating {name}…")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "speed": 1.0},
            "language_code": "da",
        },
        timeout=30,
    )
    r.raise_for_status()
    path = out / f"{name}.mp3"
    path.write_bytes(r.content)
    print(f"  ✓ {path}  ({len(r.content)//1024} KB)")

print("\nDone — check assets/restaurant/ for the MP3s.")
