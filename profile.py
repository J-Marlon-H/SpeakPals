"""profile.py — User knowledge profile: Claude-powered post-session update.

Profile JSON structure (nested, per-language):
{
  "shared": {
    "personal_facts": {"content": "...", "updated_at": "..."}
  },
  "danish": {
    "language_level":       {"content": "...", "updated_at": "..."},
    "learning_motivation":  {"content": "...", "updated_at": "..."},
    "personal_use_context": {"content": "...", "updated_at": "..."},
    "common_errors":        {"content": "...", "updated_at": "..."},
    "conversation_history": {"content": "...", "updated_at": "..."},
    "tutor_observations":   {"content": "...", "updated_at": "..."}
  },
  "portuguese_brazilian": { ... }
}

Shared facts (personal_facts) travel to every language context.
All other categories are per-language — level, motivation, errors, and history
may be completely different between Danish and Portuguese.
"""
from __future__ import annotations
import json
import re
import datetime
from pipeline import get_session as _get_pipeline_session, LANG_PROFILE_KEY

# ── Category definitions ───────────────────────────────────────────────────────

# Keys that live inside each language section
LANG_REQUIRED = [
    "language_level",
    "learning_motivation",
    "personal_use_context",
    "common_errors",
    "conversation_history",
    "tutor_observations",
]

# Keys that live in the "shared" section (language-agnostic personal facts)
SHARED_REQUIRED = [
    "personal_facts",
]

# ── Claude prompt ──────────────────────────────────────────────────────────────

_UPDATE_PROMPT = """\
You are a language learning analyst. Update a learner's knowledge profile after a completed session.

The profile has TWO sections:
- "shared"   — personal facts about the student that apply to ALL languages they learn
- "language" — learning data specific to {target_lang} only

## Current SHARED profile
{shared_json}

## Current {target_lang} profile
{lang_json}

## Session data

Student: {name}  |  Level: {level}  |  Target language: {target_lang}  |  Native language: {bg_lang}

### Conversation log
{conversation_text}

### Error log (mistakes noted during this session)
{error_text}

## Your task

Return a JSON object with exactly two top-level keys: "shared" and "language".

**Tone: concise, human-readable, like notes a good tutor would write.**
Use bullet points where listing multiple items. Short prose for single observations.
No padding, no filler. Every word should be signal.

─────────────────────────────────────────────────────
RULES FOR "shared"
─────────────────────────────────────────────────────
Allowed key: personal_facts only. No other keys.

personal_facts rules:
- Markdown bullet list, one confirmed fact per line.
  E.g. "- Lives in Copenhagen", "- Partner is Danish", "- Works at Tryg as an engineer".
- Only include what the student explicitly stated. Never infer.
- Accumulate across sessions — never delete existing facts.
- If nothing new was shared, keep existing content and timestamp unchanged.

─────────────────────────────────────────────────────
RULES FOR "language" — {target_lang}-specific section
─────────────────────────────────────────────────────
Required keys (exactly these 6, no more):
  language_level, learning_motivation, personal_use_context,
  common_errors, conversation_history, tutor_observations

Style rules per key:

conversation_history — Markdown bullet list, one entry per session, date prefix REQUIRED.
  Format: "- YYYY-MM-DD: what was covered, practised, or discussed (be specific)."
  Today's date is {today_date}. Use it for this session's entry.
  IMPORTANT: Keep ALL prior dated entries — never delete any. Sort newest first. Max 1–2 lines per entry.

personal_use_context — 1–3 sentences or bullets. Specific real-life situations where
  the student will use {target_lang}. E.g. workplace, partner's family, travel.

common_errors — Short bullets listing specific patterns.
  E.g. "- Drops definite articles (-en/-et)", "- Reverts to English under pressure".
  Update with new patterns; keep all prior entries that are still relevant.

language_level — 2–4 sentences or short bullets. State level, what they can do,
  what they struggle with. Be specific (e.g. "knows 'hej', 'tak', 'undskyld'" not just "A1").

learning_motivation — 1–3 sentences. Capture the personal 'why' for THIS language specifically.

tutor_observations — Markdown bullet list, one observation per line.
  Include meaningful patterns: learning style, confidence, pacing, breakthroughs,
  cultural curiosity, frustration points, pronunciation notes — anything a good tutor
  would want to remember for {target_lang} sessions. Skip generic/obvious items.

─────────────────────────────────────────────────────
GENERAL RULES
─────────────────────────────────────────────────────
- Each value must be: {{"content": "<text>", "updated_at": "{now_iso}"}}
  Use "{now_iso}" if content changed; keep the old timestamp if content is unchanged.
- First session (empty sections): populate all keys; use "" for categories with no evidence yet.
- Reply with ONLY the JSON object — no markdown, no explanation, no text outside {{ }}.

Required output shape:
{{
  "shared": {{
    "personal_facts": {{"content": "...", "updated_at": "..."}}
  }},
  "language": {{
    "language_level":       {{"content": "...", "updated_at": "..."}},
    "learning_motivation":  {{"content": "...", "updated_at": "..."}},
    "personal_use_context": {{"content": "...", "updated_at": "..."}},
    "common_errors":        {{"content": "...", "updated_at": "..."}},
    "conversation_history": {{"content": "...", "updated_at": "..."}},
    "tutor_observations":   {{"content": "...", "updated_at": "..."}}
  }}
}}
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


def _merge_conversation_history(old_content: str, new_content: str) -> str:
    """Ensure no prior dated history entries are lost if Claude drops them."""
    if not old_content or not old_content.strip():
        return new_content
    _date_re = re.compile(r'^-\s*\d{4}-\d{2}-\d{2}:')
    old_entries = [l.strip() for l in old_content.splitlines() if _date_re.match(l.strip())]
    new_entries = [l.strip() for l in new_content.splitlines() if _date_re.match(l.strip())]
    missing = [e for e in old_entries if not any(e[:30] in n for n in new_entries)]
    if missing:
        return (new_content.strip() + "\n" + "\n".join(missing)).strip()
    return new_content


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
    """Call Claude to update the knowledge profile for `target_lang`.

    Reads the language-specific section and the shared section from
    `current_profile`, sends both to Claude, then merges the result back
    into the full profile and returns it.

    Returns the unchanged `current_profile` on any error — data is never lost.
    """
    lang_key   = LANG_PROFILE_KEY.get(target_lang,
                                      target_lang.lower().replace(" ", "_")
                                                          .replace("(", "")
                                                          .replace(")", ""))
    now_iso    = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    today_date = datetime.date.today().isoformat()

    current_shared = current_profile.get("shared", {})
    current_lang   = current_profile.get(lang_key, {})

    prompt = _UPDATE_PROMPT.format(
        shared_json=json.dumps(current_shared, ensure_ascii=False, indent=2),
        lang_json=json.dumps(current_lang, ensure_ascii=False, indent=2),
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
        raw = re.sub(r"^```[a-z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        updated = json.loads(raw)
        if not isinstance(updated, dict):
            return current_profile

        # ── Validate and fill missing keys ─────────────────────────────────────
        updated_shared = updated.get("shared", {})
        updated_lang   = updated.get("language", {})

        if not isinstance(updated_shared, dict):
            updated_shared = {}
        if not isinstance(updated_lang, dict):
            updated_lang = {}

        for key in SHARED_REQUIRED:
            if key not in updated_shared:
                updated_shared[key] = current_shared.get(key, {"content": "", "updated_at": now_iso})

        for key in LANG_REQUIRED:
            if key not in updated_lang:
                updated_lang[key] = current_lang.get(key, {"content": "", "updated_at": now_iso})

        # Remove any extra keys Claude may have added
        updated_shared = {k: v for k, v in updated_shared.items() if k in SHARED_REQUIRED}
        updated_lang   = {k: v for k, v in updated_lang.items()   if k in LANG_REQUIRED}

        # ── Protect conversation_history from accidental truncation ────────────
        _old_hist = (current_lang.get("conversation_history") or {}).get("content", "")
        _new_hist = (updated_lang.get("conversation_history") or {}).get("content", "")
        merged_hist = _merge_conversation_history(_old_hist, _new_hist)
        if merged_hist != _new_hist:
            updated_lang["conversation_history"]["content"] = merged_hist

        # ── Merge back into the full profile ───────────────────────────────────
        result = dict(current_profile)   # preserve any other language sections
        result["shared"]  = updated_shared
        result[lang_key]  = updated_lang
        return result

    except Exception as _err:
        update_knowledge_profile.last_error = str(_err)
        return current_profile
