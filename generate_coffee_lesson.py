"""
Coffee Room lesson setup script.

Steps per scene:
  1. Generate ElevenLabs TTS for the character's da_line
  2. Merge audio into the silent MP4  →  static/coffee/<name>.mp4
  3. Extract last frame               →  static/coffee/<name>_last.jpg

Run from project root:
    python generate_coffee_lesson.py

Edit SCENES below to match the actual dialogue in each video before running.
"""
import pathlib
import shutil
import subprocess

import requests
from dotenv import load_dotenv
from db import _secret

load_dotenv("keys.env")

ELEVEN_KEY = _secret("ELEVENLABS_API_KEY")
VOICE_ID   = "gfKKsLN1k0oYYN9n2dXX"

# ── Scene script ──────────────────────────────────────────────────────────────
# da_line   : what the character says (spoken via TTS + shown in sidebar)
# user_turn : True = mic phase follows; False = auto-advance after video
# en_prompt : hint shown to student during mic phase
# da_target : words to score the student's answer against (≥50% overlap = correct)
# hint      : what Lars says if student asks in English or answers wrong

SCENES = [
    {
        "name":      "scene1_coffee",
        "da_line":   "Godmorgen! Du ser lidt træt ud i dag.",
        "user_turn": True,
        "en_prompt": "Sofie says you look a little tired. Agree and say you need coffee.",
        "da_target": "Ja jeg har brug for kaffe",
        "hint":      "Try 'Ja, jeg tror, jeg har brug for meget kaffe' (Yes, I think I need a lot of coffee)",
    },
    {
        "name":      "scene2_coffee",
        "da_line":   "Det kender jeg godt. Jeg er heller ikke helt vågen endnu.",
        "user_turn": True,
        "en_prompt": "She says she's also not fully awake yet. Agree that coffee helps.",
        "da_target": "Det hjælper lidt med kaffe",
        "hint":      "Try 'Det hjælper lidt med kaffe' (Coffee helps a little)",
    },
    {
        "name":      "scene3_coffee",
        "da_line":   "Ja, kaffe er vigtigt på et dansk kontor.",
        "user_turn": True,
        "en_prompt": "She jokes that coffee is important in a Danish office. Say you've noticed.",
        "da_target": "Det har jeg lagt mærke til",
        "hint":      "Try 'Det har jeg lagt mærke til' (I've noticed that)",
    },
    {
        "name":      "scene4_coffee",
        "da_line":   "Har du planer efter arbejde i dag?",
        "user_turn": True,
        "en_prompt": "She's asking about your plans after work. Say not really, maybe just relax at home.",
        "da_target": "Ikke rigtigt måske slappe af derhjemme",
        "hint":      "Try 'Ikke rigtigt. Måske bare slappe af derhjemme.' (Not really. Maybe just relax at home.)",
    },
    {
        "name":      "scene5_coffee",
        "da_line":   "Jeg skal bare hjem og lave aftensmad. Ikke noget spændende.",
        "user_turn": True,
        "en_prompt": "She says she's just going home to cook dinner. Say that sounds nice.",
        "da_target": "Det lyder meget rart",
        "hint":      "Try 'Det lyder faktisk meget rart!' (That actually sounds very nice!)",
    },
    {
        "name":      "scene6_coffee",
        "da_line":   "Så er kaffen klar.",
        "user_turn": True,
        "en_prompt": "The coffee is ready! Thank her.",
        "da_target": "Perfekt tak",
        "hint":      "Try 'Perfekt, tak!' (Perfect, thank you!)",
    },
]

# ── Paths ─────────────────────────────────────────────────────────────────────

ASSETS_DIR = pathlib.Path("assets/coffee")
STATIC_DIR = pathlib.Path("static/coffee")
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_tts(text: str, out_path: pathlib.Path) -> None:
    print(f"    TTS  → {out_path.name}")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75, "speed": 0.9},
            "language_code": "da",
        },
        timeout=30,
    )
    r.raise_for_status()
    out_path.write_bytes(r.content)
    print(f"         {len(r.content) // 1024} KB")


def merge_audio(video: pathlib.Path, audio: pathlib.Path, out: pathlib.Path) -> None:
    print(f"    merge → {out.name}")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


def extract_last_frame(video: pathlib.Path, out: pathlib.Path) -> None:
    print(f"    frame → {out.name}")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-sseof", "-0.1",
            "-i", str(video),
            "-vframes", "1",
            "-q:v", "3",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

for scene in SCENES:
    name       = scene["name"]
    da_line    = scene.get("da_line", "").strip()
    silent_mp4 = ASSETS_DIR / f"{name}_silent.mp4"
    out_mp4    = STATIC_DIR / f"{name}.mp4"
    last_jpg   = STATIC_DIR / f"{name}_last.jpg"

    print(f"\n── {name} ──")

    if not silent_mp4.exists():
        print(f"    ⚠  {silent_mp4} not found — skipping")
        continue

    if da_line:
        mp3_path = ASSETS_DIR / f"{name}.mp3"
        generate_tts(da_line, mp3_path)
        merge_audio(silent_mp4, mp3_path, out_mp4)
    else:
        shutil.copy2(silent_mp4, out_mp4)
        print(f"    copy (no dialogue) → {out_mp4.name}")

    extract_last_frame(out_mp4, last_jpg)

print("\n✓ Done — static/coffee/ is ready.")
