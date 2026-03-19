import streamlit as st
import streamlit.components.v1 as components
import datetime
import base64
import os
import pathlib
from dotenv import load_dotenv
from pipeline import (SCENE_CATALOG, LESSON_STATE_KEYS, VOICES, SETTINGS_DEFAULTS,
                      generate_language_tip, extract_vocabulary, tts_chunk)
import json as _json
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv("keys.env")

def _secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)

CLAUDE_KEY  = _secret("CLAUDE_API_KEY")
ELEVEN_KEY  = _secret("ELEVENLABS_API_KEY")
_DEFAULT_VOICE = list(VOICES.values())[0]  # Mathias

st.set_page_config(page_title="Feedback — SpeakPals", page_icon="📋",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#080812!important}
  .block-container{padding:2.5rem 3rem!important;max-width:860px!important;margin:auto}

  /* Tabs */
  .stTabs [data-baseweb="tab-list"]{background:transparent!important;
    border-bottom:1px solid rgba(129,140,248,.18)!important;gap:4px}
  .stTabs [data-baseweb="tab"]{color:rgba(165,180,252,.45)!important;
    border-radius:8px 8px 0 0!important;padding:8px 22px!important;font-size:13px!important;
    font-weight:500!important}
  .stTabs [aria-selected="true"]{color:#e0e7ff!important;
    border-bottom:2px solid #818cf8!important;background:rgba(129,140,248,.07)!important}
  .stTabs [data-baseweb="tab-panel"]{padding-top:24px!important}

  /* Expander */
  [data-testid="stExpander"]{
    background:rgba(255,255,255,.02)!important;
    border:1px solid rgba(255,255,255,.07)!important;
    border-radius:12px!important;margin-bottom:10px!important}
  [data-testid="stExpander"] summary{color:rgba(165,180,252,.6)!important;font-size:13px!important}

  /* Buttons */
  .stButton button{
    border-radius:10px!important;font-weight:600!important;font-size:13px!important;
    background:rgba(129,140,248,.1)!important;
    border:1px solid rgba(129,140,248,.25)!important;
    color:#c7d2fe!important;
    transition:background .2s,border-color .2s}
  .stButton button:hover{
    background:rgba(129,140,248,.2)!important;
    border-color:rgba(129,140,248,.48)!important}
</style>""", unsafe_allow_html=True)

# ── Scene lookup ───────────────────────────────────────────────────────────────
_scene_by_key = {s["key"]: s for s in SCENE_CATALOG}

# ── Background-language tips — per target language ─────────────────────────────
BG_LANG_TIPS = {
    "Danish": {
        "German":  ("🇩🇪", "Danish has only two genders (en/et) vs. German's three. The V2 rule looks "
                    "similar, but subclauses don't push the verb to the end. Numbers 50–90 use a "
                    "base-20 system — halvtreds = 50, tres = 60 — very different from German."),
        "English": ("🇬🇧", "The V2 rule inverts subject + verb after a fronted element ('I go' → 'Går jeg'). "
                    "Articles are suffixes: hunden = the dog, huset = the house. "
                    "Many letters are silent — pronunciation is the biggest hurdle."),
        "Spanish": ("🇪🇸", "Articles are suffixes added to the noun (hund-en = the dog). "
                    "The same verb form is used for jeg/du/han — no conjugation for person. "
                    "Pronunciation will feel unfamiliar at first."),
        "French":  ("🇫🇷", "Like French, Danish has grammatical gender but only two (en/et). "
                    "No verb agreement with subject. Danish nasal vowels differ from French nasals."),
        "Dutch":   ("🇳🇱", "Danish and Dutch are closely related — many words look similar. "
                    "Key differences: Danish spelling is less phonetic, and the stød (glottal stop) "
                    "has no Dutch equivalent."),
    },
    "Portuguese (Brazilian)": {
        "German":  ("🇩🇪", "Portuguese has two genders (masculine/feminine) like German, but no neuter. "
                    "Verbs conjugate for person — 'eu falo', 'você fala', 'ele fala'. "
                    "Watch out for 'ser' vs 'estar' — both mean 'to be' but are used differently."),
        "English": ("🇬🇧", "Portuguese verbs conjugate for person and tense — no need for subject "
                    "pronouns, the ending shows who is speaking. Master the nasal vowels "
                    "(ã, em, om) and the difference between ser and estar."),
        "Spanish": ("🇪🇸", "Brazilian Portuguese and Spanish share most vocabulary but sound very "
                    "different. Key differences: 'você' replaces 'tú/usted', nasal vowels are "
                    "prominent, and 'ter' is used instead of 'tener' for possession."),
        "French":  ("🇫🇷", "Like French, Portuguese has nasal vowels and rich verb conjugations. "
                    "Brazilian Portuguese dropped many silent letters — pronunciation is more "
                    "direct. Focus on the difference between ser and estar."),
        "Dutch":   ("🇳🇱", "Portuguese and Dutch are structurally very different. Focus on mastering "
                    "the 14+ verb tenses, nasal vowels (ã, em), and the ser vs estar distinction "
                    "— Dutch has no equivalent to this two-verb 'to be' system."),
    },
}

# ── Sample sessions ────────────────────────────────────────────────────────────
SAMPLE_SESSIONS = [
    {
        "id": "sample_2",
        "date": "Mar 12, 2026",
        "scene_key": "meet_a_friend",
        "scene_title": "Meet a Friend",
        "level": "A1",
        "bg_lang": "German",
        "score_ok": 2, "score_total": 3,
        "coaching_log": [
            {
                "question":   "Hvor gammel er du?",
                "attempt":    "Ich bin 25",
                "correction": "Du sagde det på tysk! På dansk siger man 'Jeg er 25 år gammel' — eller bare '25 år'.",
            }
        ],
        "correct_log": [
            {"who": "character", "text": "Hej! Hvad hedder du?"},
            {"who": "student",   "text": "Jeg hedder Marlon"},
            {"who": "character", "text": "Hvor gammel er du?"},
            {"who": "character", "text": "Hvor bor du?"},
            {"who": "student",   "text": "Jeg bor i København"},
        ],
        "vocab": [
            {"word": "hedder",    "translation": "am called / is called", "example": "Hvad hedder din ven?"},
            {"word": "gammel",    "translation": "old / years old",        "example": "Jeg er tyve år gammel."},
            {"word": "bor",       "translation": "live / lives",           "example": "Hun bor i Aarhus."},
            {"word": "København", "translation": "Copenhagen",             "example": "København er Danmarks hovedstad."},
        ],
    },
    {
        "id": "sample_1",
        "date": "Mar 10, 2026",
        "scene_key": "supermarket",
        "scene_title": "Supermarket Checkout",
        "level": "A1",
        "bg_lang": "German",
        "score_ok": 3, "score_total": 3,
        "coaching_log": [],
        "correct_log": [
            {"who": "character", "text": "Vil du betale med kort eller kontanter?"},
            {"who": "student",   "text": "Kort, tak"},
            {"who": "character", "text": "Vil du have en kvittering?"},
            {"who": "student",   "text": "Nej tak"},
            {"who": "character", "text": "Hav en god dag!"},
            {"who": "student",   "text": "Tak, i lige måde!"},
        ],
        "vocab": [
            {"word": "betale",      "translation": "to pay",     "example": "Jeg vil gerne betale nu."},
            {"word": "kort",        "translation": "card",       "example": "Har du et kreditkort?"},
            {"word": "kontanter",   "translation": "cash",       "example": "Jeg har ingen kontanter med."},
            {"word": "kvittering",  "translation": "receipt",    "example": "Kan jeg få en kvittering?"},
            {"word": "i lige måde", "translation": "likewise / same to you", "example": "God aften! — Tak, i lige måde!"},
        ],
    },
]

# ── Session state init ─────────────────────────────────────────────────────────
_saved = SETTINGS_DEFAULTS.copy()
try:
    _saved.update(_json.loads((pathlib.Path(__file__).parent.parent / "user_settings.json").read_text(encoding="utf-8")))
except Exception:
    pass
for _k, _v in _saved.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v
if "session_history" not in st.session_state:
    st.session_state["session_history"] = list(SAMPLE_SESSIONS)

_sk          = st.session_state.get("selected_scene", "")
_level       = st.session_state.get("s_level",    SETTINGS_DEFAULTS["s_level"])
_bg_lang     = st.session_state.get("s_bg_lang",  SETTINGS_DEFAULTS["s_bg_lang"])
_target_lang = st.session_state.get("s_language", SETTINGS_DEFAULTS["s_language"])
correct_log  = st.session_state.get("correct_log",  [])
coaching_log = st.session_state.get("coaching_log", [])

_loading_slot = st.empty()

if (correct_log or coaching_log) and not st.session_state.get("current_session_id"):
    _loading_slot.markdown("""
    <style>
      @keyframes _sp_spin  { to { transform: rotate(360deg); } }
      @keyframes _sp_pulse { 0%,100%{opacity:.35} 50%{opacity:.9} }
      .sp-overlay {
        position:fixed;top:0;left:0;width:100%;height:100%;
        background:#080812;
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        z-index:9999;
      }
      .sp-ring {
        width:52px;height:52px;border-radius:50%;
        border:4px solid rgba(129,140,248,.15);
        border-top-color:#818cf8;
        animation:_sp_spin .85s linear infinite;
        margin-bottom:28px;
      }
      .sp-label {
        font:600 15px/1 Segoe UI,sans-serif;
        color:rgba(165,180,252,.75);
        letter-spacing:.4px;
        animation:_sp_pulse 1.8s ease-in-out infinite;
        margin-bottom:10px;
      }
      .sp-sub {
        font:400 12px Segoe UI;
        color:rgba(165,180,252,.32);
        letter-spacing:.2px;
      }
    </style>
    <div class="sp-overlay">
      <div class="sp-ring"></div>
      <div class="sp-label">Analysing your lesson</div>
      <div class="sp-sub">Extracting vocabulary · Generating tip</div>
    </div>
    """, unsafe_allow_html=True)

    _ts      = str(int(datetime.datetime.now().timestamp()))
    answered = sum(1 for e in correct_log if e["who"] == "student")
    total    = answered + len(coaching_log)

    all_lines = correct_log + [
        {"who": "student", "text": e.get("attempt", "")} for e in coaching_log if e.get("attempt")
    ]

    lang_tip = None
    vocab    = []
    if all_lines and CLAUDE_KEY:
        voice_label = st.session_state.get("s_voice_label", "")
        voice_id    = VOICES.get(voice_label, _DEFAULT_VOICE)

        # Run tip + vocab extraction in parallel
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_tip   = ex.submit(generate_language_tip, all_lines, _bg_lang, CLAUDE_KEY)
            fut_vocab = ex.submit(extract_vocabulary, all_lines, _bg_lang, _level, CLAUDE_KEY)
            try:
                lang_tip = fut_tip.result()
            except Exception:
                pass
            try:
                items = fut_vocab.result()
            except Exception:
                items = []

        # Run all TTS calls in parallel
        if items and ELEVEN_KEY:
            def _tts(item):
                try:
                    audio = tts_chunk(item["example"], voice_id, ELEVEN_KEY)
                    item["audio_b64"] = base64.b64encode(audio).decode()
                except Exception:
                    pass
                return item

            with ThreadPoolExecutor(max_workers=len(items)) as ex:
                items = list(ex.map(_tts, items))

        vocab = items

    _loading_slot.empty()
    st.session_state["current_session_id"] = _ts
    st.session_state["session_history"].insert(0, {
        "id":           _ts,
        "date":         datetime.datetime.now().strftime("%b %d, %Y"),
        "scene_key":    _sk,
        "scene_title":  _scene_by_key.get(_sk, {}).get("title", "Lesson"),
        "level":        _level,
        "bg_lang":      _bg_lang,
        "target_lang":  _target_lang,
        "score_ok":     answered,
        "score_total":  total,
        "coaching_log": coaching_log,
        "correct_log":  correct_log,
        "lang_tip":     lang_tip,
        "vocab":        vocab,
    })

history = st.session_state["session_history"]


# ── Intelligibility verdict ─────────────────────────────────────────────────────
def _intelligibility(ok: int, total: int) -> tuple[str, str, str, str, str]:
    """Returns (verdict, sub_text, color, bg, border)."""
    if total == 0:
        return ("—", "Complete a lesson to see your result.",
                "#818cf8", "rgba(129,140,248,.05)", "rgba(129,140,248,.12)")
    pct = ok / total
    if pct >= 1.0:
        return (
            "Yes, absolutely!",
            "Perfect accuracy — every answer landed. A native speaker would follow you without hesitation.",
            "#34d399", "rgba(52,211,153,.07)", "rgba(52,211,153,.18)",
        )
    elif pct >= 0.67:
        return (
            "Mostly yes",
            f"You got {ok} of {total} answers across — a native speaker would follow you, even if a few needed a second try.",
            "#818cf8", "rgba(129,140,248,.07)", "rgba(129,140,248,.18)",
        )
    else:
        return (
            "Not yet — keep at it",
            f"{ok} of {total} answers landed clearly. Each session builds your confidence faster than you think.",
            "#f59e0b", "rgba(245,158,11,.07)", "rgba(245,158,11,.18)",
        )


# ── Next scene helper ───────────────────────────────────────────────────────────
def _next_scene(current_key: str) -> dict | None:
    """Return the next scene dict in SCENE_CATALOG after current_key, or None."""
    keys = [sc["key"] for sc in SCENE_CATALOG]
    try:
        idx = keys.index(current_key)
        if idx + 1 < len(SCENE_CATALOG):
            return SCENE_CATALOG[idx + 1]
    except ValueError:
        pass
    return None


# ── Vocabulary section ─────────────────────────────────────────────────────────
def _render_vocab(s):
    vocab = s.get("vocab", [])
    if not vocab:
        return
    sid = s["id"]
    st.markdown(
        "<div style='font:700 10px Segoe UI;letter-spacing:2px;color:rgba(165,180,252,.4);"
        "text-transform:uppercase;margin-bottom:14px'>Words from this session</div>",
        unsafe_allow_html=True,
    )
    voice_label = st.session_state.get("s_voice_label", "")
    voice_id    = VOICES.get(voice_label, _DEFAULT_VOICE)
    cols = st.columns(2)
    for i, item in enumerate(vocab):
        word      = item.get("word", "")
        trans     = item.get("translation", "")
        example   = item.get("example", "")
        _aud_key  = f"_auddata_{sid}_{i}"
        _play_key = f"_playing_{sid}_{i}"

        # Cache pre-generated audio into session state on first render
        if item.get("audio_b64") and _aud_key not in st.session_state:
            st.session_state[_aud_key] = item["audio_b64"]

        with cols[i % 2]:
            st.markdown(
                f"<div style='background:rgba(129,140,248,.05);"
                f"border:1px solid rgba(129,140,248,.14);border-radius:12px;"
                f"padding:14px 16px;margin-bottom:4px'>"
                f"  <div style='display:flex;align-items:baseline;gap:8px;margin-bottom:7px'>"
                f"    <span style='font:700 15px Segoe UI;color:#e0e7ff'>{word}</span>"
                f"    <span style='font:400 11px Segoe UI;color:rgba(165,180,252,.5)'>{trans}</span>"
                f"  </div>"
                f"  <div style='font:400 12px/1.5 Segoe UI;color:rgba(165,180,252,.72);"
                f"    font-style:italic'>{example}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.session_state.pop(_play_key, False):
                # Replace button with audio player
                aud = st.session_state.get(_aud_key, "")
                if aud:
                    st.audio(base64.b64decode(aud), format="audio/mpeg", autoplay=True)
            else:
                if st.button("▶ Hear it", key=f"play_{sid}_{i}",
                             disabled=not (_aud_key in st.session_state or ELEVEN_KEY)):
                    if _aud_key not in st.session_state and ELEVEN_KEY:
                        with st.spinner(""):
                            try:
                                audio = tts_chunk(example, voice_id, ELEVEN_KEY)
                                st.session_state[_aud_key] = base64.b64encode(audio).decode()
                            except Exception:
                                pass
                    if _aud_key in st.session_state:
                        st.session_state[_play_key] = True
                        st.rerun()
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


# ── Render function ────────────────────────────────────────────────────────────
def render_session(s):
    errors    = s.get("coaching_log", [])
    conv      = s.get("correct_log",  [])
    s_bg      = s.get("bg_lang", "")
    ok        = s.get("score_ok",    0)
    total     = s.get("score_total", 0)
    char_lbl  = _scene_by_key.get(s.get("scene_key", ""), {}).get("char_name", "Character")
    scene_ttl = s.get("scene_title", "")

    # ── Intelligibility hero card ───────────────────────────────────────────────
    n_err = len(errors)
    verdict, verdict_sub, v_color, v_bg, v_border = _intelligibility(ok, total)

    correct_chip = (
        f"<span style='background:rgba(52,211,153,.12);border:1px solid rgba(52,211,153,.22);"
        f"border-radius:20px;padding:3px 12px;font:600 11px Segoe UI;color:#34d399;"
        f"letter-spacing:.3px'>{ok}/{total} answered correctly</span>"
    )
    mistake_chip = (
        "<span style='background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.15);"
        "border-radius:20px;padding:3px 12px;font:600 11px Segoe UI;color:#6ee7b7;"
        "letter-spacing:.3px'>No mistakes</span>"
        if n_err == 0 else
        f"<span style='background:rgba(129,140,248,.1);border:1px solid rgba(165,180,252,.2);"
        f"border-radius:20px;padding:3px 12px;font:600 11px Segoe UI;color:#a5b4fc;"
        f"letter-spacing:.3px'>{n_err} mistake{'s' if n_err != 1 else ''} to review</span>"
    )

    st.markdown(
        f"<div style='background:{v_bg};border:1px solid {v_border};border-radius:20px;"
        f"padding:24px 28px;margin-bottom:20px'>"
        f"  <div style='font:600 10px Segoe UI;color:{v_color};letter-spacing:2px;"
        f"text-transform:uppercase;margin-bottom:10px'>Would a native speaker understand you?</div>"
        f"  <div style='font:800 26px/1.1 Segoe UI,sans-serif;color:{v_color};"
        f"letter-spacing:-.3px;margin-bottom:8px'>{verdict}</div>"
        f"  <div style='font:400 13px/1.6 Segoe UI;color:rgba(200,210,255,.65);"
        f"margin-bottom:16px'>{verdict_sub}</div>"
        f"  <div style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>"
        f"    {correct_chip}{mistake_chip}"
        f"    <span style='font:400 12px Segoe UI;color:rgba(165,180,252,.4)'>"
        f"      &nbsp;·&nbsp; {scene_ttl} &nbsp;·&nbsp; Level {s.get('level','')} &nbsp;·&nbsp; {s.get('date','')}"
        f"    </span>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Mistakes section ───────────────────────────────────────────────────────
    if errors:
        st.markdown(
            "<div style='font:700 10px Segoe UI;letter-spacing:2px;color:rgba(165,180,252,.4);"
            "text-transform:uppercase;margin-bottom:14px'>Mistakes to review</div>",
            unsafe_allow_html=True
        )
        for i, err in enumerate(errors):
            q   = err.get("question","").replace("<","&lt;").replace(">","&gt;")
            att = err.get("attempt","").replace("<","&lt;").replace(">","&gt;")
            cor = err.get("correction","").replace("<","&lt;").replace(">","&gt;")
            n   = i + 1
            st.markdown(
                # Card with left accent bar
                f"<div style='border-left:3px solid rgba(129,140,248,.4);"
                f"background:rgba(129,140,248,.04);border-radius:0 14px 14px 0;"
                f"padding:18px 20px;margin-bottom:14px'>"
                # Number + question
                f"<div style='display:flex;align-items:baseline;gap:10px;margin-bottom:14px'>"
                f"  <span style='font:700 11px Segoe UI;color:rgba(129,140,248,.5)'>{n:02d}</span>"
                f"  <span style='font:500 14px/1.4 Segoe UI;color:#e2e8f0'>{q}</span>"
                f"</div>"
                # Two columns: You said / Correction
                f"<div style='display:grid;grid-template-columns:1fr 1.5fr;gap:12px'>"
                # You said
                f"  <div>"
                f"    <div style='font:600 9px Segoe UI;color:rgba(165,180,252,.4);letter-spacing:.8px;"
                f"text-transform:uppercase;margin-bottom:6px'>You said</div>"
                f"    <div style='font:400 13px Segoe UI;color:rgba(220,220,240,.55);"
                f"padding:8px 12px;background:rgba(255,255,255,.03);border-radius:8px;"
                f"border:1px solid rgba(255,255,255,.06)'>{att}</div>"
                f"  </div>"
                # Correction
                f"  <div>"
                f"    <div style='font:600 9px Segoe UI;color:rgba(165,180,252,.4);letter-spacing:.8px;"
                f"text-transform:uppercase;margin-bottom:6px'>Correction</div>"
                f"    <div style='font:400 13px/1.5 Segoe UI;color:#c7d2fe;"
                f"padding:8px 12px;background:rgba(129,140,248,.08);border-radius:8px;"
                f"border:1px solid rgba(129,140,248,.12)'>{cor}</div>"
                f"  </div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:16px;"
            "background:rgba(52,211,153,.05);border:1px solid rgba(52,211,153,.15);"
            "border-radius:14px;padding:20px 24px;margin-bottom:20px'>"
            "<div style='font-size:32px;line-height:1'>🎉</div>"
            "<div>"
            "  <div style='font:600 15px Segoe UI;color:#6ee7b7;margin-bottom:3px'>Clean session</div>"
            "  <div style='font:400 12px Segoe UI;color:rgba(110,231,183,.55)'>No mistakes this time — great work!</div>"
            "</div></div>",
            unsafe_allow_html=True
        )

    # ── Language tip ───────────────────────────────────────────────────────────
    dynamic_tip = s.get("lang_tip")
    static_tip  = BG_LANG_TIPS.get(s_bg)
    if dynamic_tip or static_tip:
        flag      = static_tip[0] if static_tip else "💡"
        tip_text  = dynamic_tip if dynamic_tip else static_tip[1]
        st.markdown(
            f"<div style='background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);"
            f"border-radius:14px;padding:16px 20px;margin-bottom:20px'>"
            f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
            f"  <span style='font-size:18px'>{flag}</span>"
            f"  <span style='font:600 10px Segoe UI;color:rgba(165,180,252,.5);letter-spacing:1.5px;"
            f"text-transform:uppercase'>Tip for {s_bg} speakers</span>"
            f"</div>"
            f"<div style='font:400 12px/1.7 Segoe UI;color:rgba(165,180,252,.65)'>{tip_text}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── Vocabulary ─────────────────────────────────────────────────────────────
    _render_vocab(s)

    # ── Full conversation ──────────────────────────────────────────────────────
    if conv:
        with st.expander("Full conversation"):
            parts = []
            for entry in conv:
                txt = entry["text"].replace("<","&lt;").replace(">","&gt;")
                if entry["who"] == "character":
                    parts.append(
                        f"<div style='background:rgba(255,255,255,.04);border-radius:4px 14px 14px 14px;"
                        f"padding:10px 14px;margin:6px 0;max-width:78%'>"
                        f"<span style='font:600 9px Segoe UI;color:rgba(165,180,252,.45);text-transform:uppercase;"
                        f"letter-spacing:.5px;display:block;margin-bottom:4px'>{char_lbl}</span>"
                        f"<span style='font:400 13px/1.4 Segoe UI;color:#e2e8f0'><em>{txt}</em></span></div>"
                    )
                else:
                    parts.append(
                        f"<div style='background:rgba(129,140,248,.14);border-radius:14px 4px 14px 14px;"
                        f"padding:10px 14px;margin:6px 0 6px auto;max-width:78%;text-align:right'>"
                        f"<span style='font:600 9px Segoe UI;color:rgba(165,180,252,.5);text-transform:uppercase;"
                        f"letter-spacing:.5px;display:block;margin-bottom:4px'>You</span>"
                        f"<span style='font:400 13px/1.4 Segoe UI;color:#c7d2fe'>{txt}</span></div>"
                    )
            st.markdown(
                f"<div style='display:flex;flex-direction:column'>{''.join(parts)}</div>",
                unsafe_allow_html=True
            )


# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style='margin-bottom:32px;padding:28px 32px;
  background:linear-gradient(135deg,rgba(49,46,129,.55) 0%,rgba(17,24,39,.2) 100%);
  border:1px solid rgba(129,140,248,.2);border-radius:24px'>
  <div style='font:800 28px/1 Segoe UI,sans-serif;color:#e0e7ff;letter-spacing:-.5px;
              margin-bottom:8px'>📋 Your Progress</div>
  <div style='font:400 13px Segoe UI;color:rgba(165,180,252,.6)'>
    Review mistakes, track corrections, and see how far you've come
  </div>
</div>""", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
hist_label = f"History  ({len(history) - 1})" if len(history) > 1 else "History"
tab_latest, tab_hist = st.tabs(["Latest Session", hist_label])

with tab_latest:
    if history:
        render_session(history[0])

        # ── Keep the momentum ──────────────────────────────────────────────────
        _s0       = history[0]
        _sk0      = _s0.get("scene_key", "")
        _n_err0   = len(_s0.get("coaching_log", []))
        _next_sc  = _next_scene(_sk0)

        st.markdown(
            "<div style='background:linear-gradient(135deg,rgba(49,46,129,.35) 0%,rgba(17,24,39,.2) 100%);"
            "border:1px solid rgba(129,140,248,.2);border-radius:20px;"
            "padding:24px 28px;margin-top:8px;margin-bottom:20px'>"
            "<div style='font:700 16px Segoe UI,sans-serif;color:#e0e7ff;margin-bottom:6px'>"
            "Keep the momentum going</div>"
            f"<div style='font:400 13px Segoe UI;color:rgba(165,180,252,.55)'>"
            f"{'Try again for a clean run — you can do it.' if _n_err0 > 0 else 'Perfect run! Ready for the next challenge?'}"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        _col_a, _col_b = st.columns(2)
        with _col_a:
            _replay_lbl = "↺ Try again — aim for no mistakes" if _n_err0 > 0 else f"↺ Replay {_s0.get('scene_title','')}"
            if st.button(_replay_lbl, use_container_width=True, key="momentum_replay"):
                for k in LESSON_STATE_KEYS:
                    st.session_state.pop(k, None)
                st.session_state["selected_scene"] = _sk0
                st.switch_page("app.py")
        with _col_b:
            _next_lbl = f"Next: {_next_sc['title']} →" if _next_sc else "Browse scenes →"
            if st.button(_next_lbl, use_container_width=True, key="momentum_next"):
                for k in LESSON_STATE_KEYS:
                    st.session_state.pop(k, None)
                if _next_sc:
                    st.session_state["selected_scene"] = _next_sc["key"]
                    st.switch_page("app.py")
                else:
                    st.switch_page("pages/scene_select.py")
    else:
        st.markdown(
            "<div style='color:rgba(255,255,255,.3);font-size:13px;padding:40px 0;text-align:center'>"
            "No session yet — complete a lesson to see feedback here.</div>",
            unsafe_allow_html=True
        )

with tab_hist:
    past = history[1:]
    if not past:
        st.markdown(
            "<div style='color:rgba(255,255,255,.3);font-size:13px;padding:40px 0;text-align:center'>"
            "Complete more lessons to build your history.</div>",
            unsafe_allow_html=True
        )
    else:
        for s in past:
            n_err   = len(s.get("coaching_log", []))
            ok      = s.get("score_ok", 0)
            total   = s.get("score_total", 0)
            suffix  = "Understood ✓" if not n_err else f"{n_err} to revisit"
            label   = f"{s.get('scene_title','')}  ·  {s.get('date','')}  ·  {ok}/{total}  ·  {suffix}"
            with st.expander(label):
                render_session(s)

# ── Navigation ─────────────────────────────────────────────────────────────────
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
_nav1, _nav2 = st.columns(2)
with _nav1:
    if st.button("← Back to lesson", use_container_width=True):
        st.switch_page("app.py")
with _nav2:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("pages/home.py")
