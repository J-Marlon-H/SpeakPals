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
VOICE_ID   = "V34B5u5UbLdNJVEkcgXp"  # Noam

LINES = {
    "scene1": "Hej!<break time=\"0.07s\"/> Velkommen!<break time=\"0.45s\"/> Vil du sidde ved baren eller ved vinduet?",
    "scene2": "Velkommen til vores restaurant! Følg mig venligst, her er et bord ved vinduet.<break time=\"0.56s\"/> Sætte jer. <break time=\"1.13s\"/> Her er menuen. Vi har <break time=\"1.0s\"/> ramen og gyoza i dag. <break time=\"1.0s\"/> Hvad må det være?",
    "scene3": "Ja, selvfølgelig, det ordner jeg med det samme",
    "scene4": "Værsgo! Ramen til dig! God appetit!",
    "scene5": "Selvfølgelig, jeg henter en gaffel til dig.",
    "scene6": "Jeg håber, at alt var lækkert, og vi ses forhåbentlig igen snart.",
}

# Per-scene voice setting overrides (merged on top of defaults)
OVERRIDES = {
    "scene2": {"speed": 1.0},
    "scene6": {"speed": 1.0},
}

out = pathlib.Path("assets/restaurant")
out.mkdir(parents=True, exist_ok=True)

for name, text in LINES.items():
    print(f"Generating {name}…")
    voice_settings = {"stability": 0.4, "similarity_boost": 0.75, "speed": 0.8}
    voice_settings.update(OVERRIDES.get(name, {}))
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": voice_settings,
            "language_code": "da",
        },
        timeout=30,
    )
    r.raise_for_status()
    path = out / f"{name}.mp3"
    path.write_bytes(r.content)
    print(f"  ✓ {path}  ({len(r.content)//1024} KB)")

print("\nDone — check assets/restaurant/ for the MP3s.")
