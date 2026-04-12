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
    "personal_facts",
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
1. Always include all 6 predefined keys: language_level, learning_motivation, personal_use_context, common_errors, conversation_history, personal_facts.
2. You may add up to 2 additional snake_case keys if the session reveals something important that does not fit the predefined categories. Choose short, descriptive key names (e.g. "pronunciation_notes", "cultural_interests").
3. The total number of keys must not exceed 8.
4. Preserve any existing custom keys from the current profile unless you have a strong reason to merge or remove them.
5. Each category value must be a JSON object with exactly two fields:
   - "content": A comprehensive summary about the learner. Rules per category type:
     • For conversation_history: write as Markdown bullet points with a date prefix on each line. \
Format: "- YYYY-MM-DD: description of what was covered or discussed — include as much detail as is useful". \
Use today's date {today_date} for entries from this session. \
Accumulate bullets from prior sessions — NEVER delete existing dated bullets, only add new ones. \
Sort with the most recent date at the top. \
There is no length limit — include everything meaningful.
     • For personal_facts: write as Markdown bullet points, one fact per line (e.g. "- Name: Marlon", "- Lives in: Copenhagen", "- Job: software engineer at Tryg"). \
Only include facts the user has explicitly stated — never infer or guess. \
Accumulate across sessions; never delete a confirmed fact unless the user contradicts it. \
No length limit — record every confirmed detail.
     • For all other categories: write in present tense, third person, plain prose. \
Include ALL relevant observations — specific words, phrases, patterns, examples, context. \
There is no sentence or length limit. The richer and more detailed the content, the better. \
Accumulate and enrich across sessions — never discard relevant information.
   - "updated_at": The ISO 8601 UTC timestamp "{now_iso}" — use this exact value if content changed, keep the old timestamp if the category was not updated.
6. If a session reveals nothing new for a category, keep the existing content and timestamp completely unchanged.
7. If the current profile is empty ({{}}) this is the first session — populate all 6 predefined categories with whatever the session reveals. Set content to "" for categories with no evidence yet.
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

        # Enforce max 8 keys: keep 6 required + up to 2 custom (alphabetical if >2)
        custom_keys = [k for k in updated if k not in REQUIRED_CATEGORIES]
        if len(custom_keys) > 2:
            for k in sorted(custom_keys)[2:]:
                del updated[k]

        return updated

    except Exception:
        return current_profile
