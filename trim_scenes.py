"""
Mix generated speech audio into silent scene videos at a specific start time.

Workflow:
  1. Run generate_scene_audio.py  →  assets/restaurant/sceneN.mp3
  2. Edit SCENES below
  3. Run python trim_scenes.py    →  static/restaurant/sceneN.mp4

audio_start : seconds into the video where the speech begins
audio_end   : optional cap — speech is trimmed if it would run past this point
              (leave None to play the full audio clip)
"""
import subprocess
import pathlib

VIDEO_DIR = pathlib.Path("static/restaurant")
AUDIO_DIR = pathlib.Path("assets/restaurant")

# ── Configure per scene ───────────────────────────────────────────────────────
SCENES = {
    "scene1": {"audio_start": 1.16, "audio_end": None},
    "scene2": {"audio_start": 0.75, "audio_end": None},
    "scene3": {"audio_start": 0,    "audio_end": None},
    "scene4": {"audio_start": 0,    "audio_end": None},
    "scene5": {"audio_start": 0,    "audio_end": None},
    "scene6": {"audio_start": 0,    "audio_end": None},
}
# ─────────────────────────────────────────────────────────────────────────────


def get_duration(path: pathlib.Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def mix(name: str, audio_start: float, audio_end: float | None) -> None:
    silent = VIDEO_DIR / f"{name}_silent.mp4"
    audio  = AUDIO_DIR / f"{name}.mp3"
    out    = VIDEO_DIR / f"{name}.mp4"

    if not silent.exists():
        print(f"  ✗ {silent} not found"); return
    if not audio.exists():
        print(f"  ✗ {audio} not found — run generate_scene_audio.py first"); return

    video_dur = get_duration(silent)
    delay_ms  = int(audio_start * 1000)

    # Build audio filter:
    # 1. Optionally cap speech length
    # 2. Delay to start at the right moment
    # 3. Pad with silence so the stream matches the full video length
    #    (prevents -shortest from cutting the video early)
    if audio_end is not None:
        max_dur = audio_end - audio_start
        af = (f"[1:a]atrim=duration={max_dur},"
              f"adelay={delay_ms}:all=1,"
              f"apad=whole_dur={video_dur}[a]")
    else:
        af = (f"[1:a]adelay={delay_ms}:all=1,"
              f"apad=whole_dur={video_dur}[a]")

    tmp = out.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(silent),
        "-i", str(audio),
        "-filter_complex", af,
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(video_dur),
        str(tmp),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"  ✗ ffmpeg error:\n{result.stderr.decode()[-600:]}")
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(out)
        end_label = f"capped at {audio_end}s" if audio_end else "natural end"
        print(f"  ✓ video {video_dur:.2f}s | audio starts {audio_start}s ({end_label})  →  {out}")


for name, cfg in SCENES.items():
    start = cfg.get("audio_start")
    if start is None:
        print(f"{name}: skipped")
        continue
    print(f"{name}: mixing…")
    mix(name, start, cfg.get("audio_end"))

print("\nDone.")
