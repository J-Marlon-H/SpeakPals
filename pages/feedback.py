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

# ── Background-language tips ───────────────────────────────────────────────────
BG_LANG_TIPS = {
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
_level       = st.session_state.get("s_level",   SETTINGS_DEFAULTS["s_level"])
_bg_lang     = st.session_state.get("s_bg_lang", SETTINGS_DEFAULTS["s_bg_lang"])
correct_log  = st.session_state.get("correct_log",  [])
coaching_log = st.session_state.get("coaching_log", [])

if (correct_log or coaching_log) and not st.session_state.get("current_session_id"):
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

    st.session_state["current_session_id"] = _ts
    st.session_state["session_history"].insert(0, {
        "id":           _ts,
        "date":         datetime.datetime.now().strftime("%b %d, %Y"),
        "scene_key":    _sk,
        "scene_title":  _scene_by_key.get(_sk, {}).get("title", "Lesson"),
        "level":        _level,
        "bg_lang":      _bg_lang,
        "score_ok":     answered,
        "score_total":  total,
        "coaching_log": coaching_log,
        "correct_log":  correct_log,
        "lang_tip":     lang_tip,
        "vocab":        vocab,
    })

history = st.session_state["session_history"]


# ── Score ring SVG ─────────────────────────────────────────────────────────────
def _score_ring(ok: int, total: int) -> str:
    pct   = ok / total if total else 0
    color = "#818cf8" if pct < 1 else "#34d399"
    r, cx, cy, sw = 26, 34, 34, 6
    circ  = 2 * 3.14159 * r
    dash  = circ * pct
    return (
        f"<svg width='68' height='68' viewBox='0 0 68 68'>"
        f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' "
        f"  stroke='rgba(255,255,255,.07)' stroke-width='{sw}'/>"
        f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' "
        f"  stroke='{color}' stroke-width='{sw}' stroke-linecap='round' "
        f"  stroke-dasharray='{dash:.1f} {circ:.1f}' "
        f"  transform='rotate(-90 {cx} {cy})'/>"
        f"<text x='{cx}' y='{cy+1}' text-anchor='middle' dominant-baseline='middle' "
        f"  font-family='Segoe UI' font-size='13' font-weight='700' fill='{color}'>"
        f"{ok}/{total}</text>"
        f"</svg>"
    )


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
    cols = st.columns(2)
    for i, item in enumerate(vocab):
        word      = item.get("word", "")
        trans     = item.get("translation", "")
        example   = item.get("example", "")
        audio_b64 = item.get("audio_b64")
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
            if audio_b64:
                if st.button("▶ Hear it", key=f"play_{sid}_{i}"):
                    st.session_state[f"_aud_{sid}_{i}"] = True
                if st.session_state.pop(f"_aud_{sid}_{i}", False):
                    components.html(
                        f'<audio autoplay>'
                        f'<source src="data:audio/mpeg;base64,{audio_b64}" type="audio/mpeg">'
                        f'</audio>',
                        height=0,
                    )
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
    perfect   = len(errors) == 0 and total > 0

    # ── Session header card ────────────────────────────────────────────────────
    ring_svg  = _score_ring(ok, total)
    n_err = len(errors)
    status_tag = (
        "<span style='background:rgba(52,211,153,.12);border:1px solid rgba(52,211,153,.25);"
        "border-radius:20px;padding:2px 10px;font:600 10px Segoe UI;color:#34d399;"
        "letter-spacing:.5px;text-transform:uppercase;margin-left:10px'>A Dane understood you ✓</span>"
        if perfect else
        f"<span style='background:rgba(199,160,252,.08);border:1px solid rgba(165,180,252,.2);"
        f"border-radius:20px;padding:2px 10px;font:600 10px Segoe UI;color:#a5b4fc;"
        f"letter-spacing:.5px;text-transform:uppercase;margin-left:8px'>"
        f"{n_err} to revisit</span>"
    )

    st.markdown(
        f"<div style='background:linear-gradient(135deg,rgba(30,27,75,.9),rgba(17,24,39,.9));"
        f"border:1px solid rgba(129,140,248,.18);border-radius:20px;"
        f"padding:20px 24px;margin-bottom:28px;display:flex;align-items:center;gap:20px'>"
        f"  <div style='flex-shrink:0'>{ring_svg}</div>"
        f"  <div>"
        f"    <div style='font:700 16px/1.2 Segoe UI,sans-serif;color:#e0e7ff;margin-bottom:5px'>"
        f"      {scene_ttl}{status_tag}</div>"
        f"    <div style='font:400 12px Segoe UI;color:rgba(165,180,252,.5)'>"
        f"      Task completion &nbsp;·&nbsp; Level {s.get('level','')} &nbsp;·&nbsp; "
        f"      {s_bg} &nbsp;·&nbsp; {s.get('date','')}"
        f"    </div>"
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

# ── Momentum nav ───────────────────────────────────────────────────────────────
st.markdown(
    "<div style='height:24px'></div>"
    "<div style='font:700 10px Segoe UI;letter-spacing:2px;color:rgba(165,180,252,.35);"
    "text-transform:uppercase;margin-bottom:12px;text-align:center'>Keep going</div>",
    unsafe_allow_html=True,
)
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔁 Same scene again", use_container_width=True):
        # Keep scene selection, clear only lesson progress
        for k in LESSON_STATE_KEYS:
            if k != "selected_scene":
                st.session_state.pop(k, None)
        st.switch_page("app.py")
with col2:
    if st.button("▶ New scene", use_container_width=True):
        for k in LESSON_STATE_KEYS:
            st.session_state.pop(k, None)
        st.switch_page("pages/scene_select.py")
with col3:
    if st.button("← Back to lesson", use_container_width=True):
        st.switch_page("app.py")
