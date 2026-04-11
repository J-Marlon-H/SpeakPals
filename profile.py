"""profile.py — User knowledge profile: Claude-powered post-session update."""
from __future__ import annotations
import json
import re
import datetime
import requests

# ── Predefined category keys ───────────────────────────────────────────────────

REQUIRED_CATEGORIES = [
    "language_level",
    "learning_motivation",
    "personal_use_context",
    "common_errors",
    "conversation_history",
]

# ── Claude prompt ──────────────────────────────────────────────────────────────

_UPDATE_PROMPT = """\
You are a language learning analyst. Update a learner's knowledge profile based on a completed lesson.

## Current profile (JSON)
{current_profile_json}

## Lesson data

Student: {name}  |  Level: {level}  |  Target language: {target_lang}  |  Native language: {bg_lang}

### Conversation log
{conversation_text}

### Error log (mistakes noted during the lesson)
{error_text}

## Your task

Return an updated profile JSON object that incorporates everything you learned about this student from the session.

Rules:
1. Always include all 5 predefined keys: language_level, learning_motivation, personal_use_context, common_errors, conversation_history.
2. You may add up to 2 additional snake_case keys if the session reveals something important that does not fit the predefined categories. Choose short, descriptive key names (e.g. "pronunciation_notes", "cultural_interests").
3. The total number of keys must not exceed 7.
4. Preserve any existing custom keys from the current profile unless you have a strong reason to merge or remove them.
5. Each category value must be a JSON object with exactly two fields:
   - "content": A comprehensive summary about the learner. Rules per category type:
     • For conversation_history: write as Markdown bullet points (each starting with "- "), \
one bullet per notable topic or fact that has come up across all sessions. \
Accumulate bullets from prior sessions — never delete existing bullets, only add new ones. \
Keep each bullet concise (one line). Example: "- Mentioned Danish partner named Sofie\n- Plans to move to Copenhagen in June 2026"
     • For all other categories: write in present tense, third person, plain prose. Include all \
relevant observations — specific words, phrases, patterns, examples. \
Do not truncate; write as much as is genuinely useful. Accumulate and enrich across sessions.
   - "updated_at": The ISO 8601 UTC timestamp "{now_iso}" — use this exact value if content changed, keep the old timestamp if the category was not updated.
6. If a session reveals nothing new for a category, keep the existing content and timestamp completely unchanged.
7. If the current profile is empty ({{}}) this is the first session — populate all 5 predefined categories with whatever the session reveals. Set content to "" for categories with no evidence yet.
8. Do not include any explanation, markdown, or text outside the JSON object.

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
    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt = _UPDATE_PROMPT.format(
        current_profile_json=json.dumps(current_profile, ensure_ascii=False, indent=2),
        name=name,
        level=level,
        target_lang=target_lang,
        bg_lang=bg_lang,
        conversation_text=_format_conversation(correct_log),
        error_text=_format_errors(coaching_log),
        now_iso=now_iso,
    )

    sess = http_session or requests.Session()
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
                "max_tokens": 1500,
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

        # Enforce max 7 keys: keep 5 required + up to 2 custom (alphabetical if >2)
        custom_keys = [k for k in updated if k not in REQUIRED_CATEGORIES]
        if len(custom_keys) > 2:
            for k in sorted(custom_keys)[2:]:
                del updated[k]

        return updated

    except Exception:
        return current_profile
