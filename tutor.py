"""tutor.py — Tutor dataclass: single source of truth for voice, language, and user context.

The Tutor encapsulates everything that is *consistent* about the tutor regardless of
which screen they appear on (onboarding, free conversation, lesson hints).

    General (class-level invariants): voice_id, tl_lang_code, model_id, knowledge context.
    Contextual (mode-specific):       the system prompt — built separately by each page
                                       and passed into stream(). This keeps the Tutor
                                       unaware of scene details, scene history, etc.

Usage
-----
    from tutor import Tutor

    # Once per page render — all voice/model config derived from session state:
    tutor = Tutor.from_session(st.session_state)

    # Build your mode-specific system prompt (scene / free_conv / onboarding):
    system = build_system_prompt(tutor.name, level, tutor.bg_lang, ...)

    # Execute — voice and pronunciation are correct for all tutor modes:
    for raw, chunk_b64, speaker in tutor.stream(system, user_input, history, CLAUDE_KEY, ELEVEN_KEY):
        ...
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Tutor:
    """Persistent tutor identity across onboarding, free conversation, and lessons.

    Centralises the three things that were previously re-derived independently in
    every page: voice_id, tl_lang_code, and model_id. By construction via
    from_session() these are always consistent, so the tutor sounds and behaves
    the same whether the student is onboarding, chatting freely, or mid-lesson.
    """

    # ── User & language identity ───────────────────────────────────────────────
    name:        str
    level:       str     # may be overridden per-scene in lesson.py
    bg_lang:     str
    target_lang: str

    # ── Voice — identical across all tutor contexts ────────────────────────────
    voice_id:     str    # ElevenLabs voice ID for the tutor
    tl_lang_code: str    # target language TTS code ("da", "pt") — used by
                         # tts_tutor_mixed to pronounce embedded phrases correctly

    # ── Model ─────────────────────────────────────────────────────────────────
    model_id: str

    # ── Persistent user knowledge ──────────────────────────────────────────────
    knowledge_profile: dict = field(default_factory=dict)
    calendar_events:   list = field(default_factory=list)

    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_session(cls, state: dict) -> "Tutor":
        """Build a Tutor from Streamlit session_state.

        This is the single place where voice and model config is derived from user
        settings. All pages should call this instead of manually reading
        s_voice_label / s_language / s_model_label from session state.
        """
        from pipeline import (VOICES_BY_LANG, VOICES, TTS_LANG_CODE,
                              MODELS, SETTINGS_DEFAULTS)

        target_lang = state.get("s_language",    SETTINGS_DEFAULTS["s_language"])
        voice_label = state.get("s_voice_label", SETTINGS_DEFAULTS["s_voice_label"])
        model_label = state.get("s_model_label", SETTINGS_DEFAULTS["s_model_label"])
        lang_voices = VOICES_BY_LANG.get(target_lang, VOICES)
        voice_id    = (lang_voices[voice_label]
                       if voice_label in lang_voices
                       else next(iter(lang_voices.values())))

        return cls(
            name        = state.get("s_name",    SETTINGS_DEFAULTS["s_name"]),
            level       = state.get("s_level",   SETTINGS_DEFAULTS["s_level"]),
            bg_lang     = state.get("s_bg_lang", SETTINGS_DEFAULTS["s_bg_lang"]),
            target_lang = target_lang,
            voice_id    = voice_id,
            tl_lang_code= TTS_LANG_CODE.get(target_lang, "da"),
            model_id    = MODELS[model_label],
            knowledge_profile = state.get("knowledge_profile") or {},
            calendar_events   = state.get("calendar_events") or [],
        )

    def stream(self,
               system: str,
               user_input: str,
               history: list,
               claude_key: str,
               eleven_key: str,
               use_structured: bool = True,
               char_voice_id: str | None = None):
        """Stream a tutor response. Yields (raw_claude_text, chunk_b64, speaker).

        Delegates to run_pipeline_stream with this Tutor's voice, model, and language
        config. The caller only needs to provide the system prompt (mode-specific)
        and the conversation inputs — voice and pronunciation are handled here.

        use_structured=False  →  onboarding (plain text, always tutor speaker)
        use_structured=True   →  lessons and free conversation (JSON verdict schema)
        char_voice_id         →  scene character voice (lesson.py derives this from
                                  scene gender data; leave None elsewhere)
        """
        from pipeline import run_pipeline_stream
        return run_pipeline_stream(
            system, user_input, history,
            self.voice_id, claude_key, eleven_key,
            model        = self.model_id,
            use_structured = use_structured,
            lang_code    = self.tl_lang_code,
            char_voice_id= char_voice_id,
            tl_lang_code = self.tl_lang_code,
        )
