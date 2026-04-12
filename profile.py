"""profile.py — User knowledge profile: Claude-powered post-session update."""
from __future__ import annotations
import json
import re
import datetime
import requests
from pipeline import get_session as _get_pipeline_session

# ── Predefined category keys ───────────────────────────────────────────────────

REQUIRED_CATEGORIES = [
    "language_level",
    "learning_motivation",
    "personal_use_context",
    "common_errors",
    "conversation_history",
    "personal_facts",
    "tutor_observations",
]

# ── Claude prompt ──────────────────────────────────────────────────────────────

_UPDATE_PROMPT = """\
You are a language learning analyst. Update a learner's knowledge profile based on a completed session.

## Current profile (JSON)
{current_profile_json}

## Session data

Student: {name}  |  Level: {level}  |  Target language: {target_lang}  |  Native language: {bg_lang}

### Conversation log
{conversation_text}

### Error log (mistakes noted during the session)
{error_text}

## Your task

Return an updated profile JSON object that incorporates what you learned about this student.

**Tone: concise, human-readable, like notes a good tutor would write.**
Use bullet points where listing multiple items. Use short prose for single observations.
No padding, no filler, no generic statements. Every word should be signal.

Rules:
1. Always include exactly these 7 keys — no more, no fewer:
   language_level, learning_motivation, personal_use_context, common_errors,
   conversation_history, personal_facts, tutor_observations.
2. Do NOT create new keys. If an observation does not fit the first 6 categories,
   add it to tutor_observations instead.
3. Each category value must be a JSON object with exactly two fields:
   - "content": Updated notes about the learner. Style rules per category:
     • conversation_history — Markdown bullet list, one entry per session, date prefix required.
       Format: "- YYYY-MM-DD: what was covered, practised, or discussed (be specific)."
       Use today's date {today_date} for this session. Keep all prior dated entries — never delete.
       Sort newest first. Max 1–2 lines per session bullet.
     • personal_facts — Markdown bullet list, one confirmed fact per line.
       E.g. "- Lives in Copenhagen", "- Partner is Danish", "- Works at Tryg as an engineer".
       Only include what the user explicitly stated. Never infer. Accumulate across sessions.
     • tutor_observations — Markdown bullet list, one observation per line.
       Include meaningful patterns: learning style, confidence, pacing, breakthroughs,
       cultural curiosity, frustration points, pronunciation notes, cultural interests —
       anything a good tutor would want to remember that doesn't fit another category.
       Skip anything generic or obvious.
     • common_errors — Short bullets listing specific patterns:
       e.g. "- Drops definite articles (-en/-et)", "- Reverts to English under pressure".
       Update with new patterns; keep all prior entries that are still relevant.
     • language_level — 2–4 sentences or short bullets. State level, what they can do,
       what they struggle with. Be specific (e.g. "knows 'hej', 'tak', 'undskyld'" not just "A1").
     • learning_motivation — 1–3 sentences. Capture the personal 'why' specifically.
     • personal_use_context — 1–3 sentences or bullets. Specific real-life situations.
   - "updated_at": ISO 8601 UTC timestamp "{now_iso}" if content changed; keep old timestamp if unchanged.
4. If a session reveals nothing new for a category, keep existing content and timestamp unchanged.
5. First session (empty profile): populate all 7 keys. Use "" for categories with no evidence yet.
6. Reply with only the JSON object — no markdown, no explanation, no text outside {{ }}.

Reply with only the JSON object, starting with {{ and ending with }}.
"""


def _format_conversation(correct_log: list[dict]) -> str:
    lines = []
    for e in correct_log:
        who = e.get("who", "unknown").capitalize()
        lines.append(f"{who}: {e.get('text', '')}")
    return "\n".join(lines) if lines else "(no conversation recorded)"


def _format_errors(coaching_log: list[dict]) -> str:
    if not coaching_log:
        return "(no errors recorded)"
    lines = []
    for i, e in enumerate(coaching_log, 1):
        lines.append(
            f"{i}. Prompt: \"{e.get('question', '')}\"  |  "
            f"Student said: \"{e.get('attempt', '')}\"  |  "
            f"Correction: \"{e.get('correction', '')}\""
        )
    return "\n".join(lines)


# ── Main function ──────────────────────────────────────────────────────────────

def update_knowledge_profile(
    current_profile: dict,
    name: str,
    level: str,
    target_lang: str,
    bg_lang: str,
    correct_log: list[dict],
    coaching_log: list[dict],
    claude_key: str,
    model: str = "claude-haiku-4-5-20251001",
    http_session=None,
) -> dict:
    """
    Call Claude to produce an updated knowledge profile dict.

    Returns the updated profile dict on success, or the unchanged current_profile
    on any error — data is never lost.
    """
    now_iso    = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    today_date = datetime.date.today().isoformat()
    prompt = _UPDATE_PROMPT.format(
        current_profile_json=json.dumps(current_profile, ensure_ascii=False, indent=2),
        name=name,
        level=level,
        target_lang=target_lang,
        bg_lang=bg_lang,
        conversation_text=_format_conversation(correct_log),
        error_text=_format_errors(coaching_log),
        now_iso=now_iso,
        today_date=today_date,
    )

    sess = http_session or _get_pipeline_session()
    try:
        r = sess.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": claude_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        r.raise_for_status()
        raw = r.json()["content"][0]["text"].strip()

        # Strip optional markdown code fence
        raw = re.sub(r"^```[a-z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        updated = json.loads(raw)

        if not isinstance(updated, dict):
            return current_profile

        # Ensure all required keys are present
        for key in REQUIRED_CATEGORIES:
            if key not in updated:
                updated[key] = {"content": "", "updated_at": now_iso}

        # Remove any extra keys Claude may have added despite instructions
        for k in [k for k in updated if k not in REQUIRED_CATEGORIES]:
            del updated[k]

        return updated

    except Exception:
        return current_profile
