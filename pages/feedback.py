import streamlit as st
import datetime
from pipeline import SCENE_CATALOG

st.set_page_config(page_title="Feedback — SpeakPals", page_icon="📋",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#0b0b1a!important}
  .block-container{padding:2.5rem 2rem!important;max-width:700px!important;margin:auto}
  .stButton button{border-radius:10px!important;font-weight:600!important;font-size:13px!important}
  label,p,div{color:#e2e8f0}
  .stTabs [data-baseweb="tab-list"]{background:transparent!important;
    border-bottom:1px solid rgba(129,140,248,.2)!important;gap:4px}
  .stTabs [data-baseweb="tab"]{color:rgba(165,180,252,.6)!important;
    border-radius:8px 8px 0 0!important;padding:8px 18px!important}
  .stTabs [aria-selected="true"]{color:#e0e7ff!important;
    border-bottom:2px solid #818cf8!important;background:rgba(129,140,248,.08)!important}
  .stTabs [data-baseweb="tab-panel"]{padding-top:20px!important}
  details summary{color:#a5b4fc!important;font-size:13px!important}
</style>""", unsafe_allow_html=True)

# ── Scene lookup ───────────────────────────────────────────────────────────────
_scene_by_key = {s["key"]: s for s in SCENE_CATALOG}

# ── Background-language tips ───────────────────────────────────────────────────
BG_LANG_TIPS = {
    "German":  "🇩🇪 German speakers: Danish has only two genders (en/et vs. der/die/das). "
               "Word order is similar — V2 rule applies — but subclauses don't push the verb to the end. "
               "Numbers 50–90 use a base-20 system (halvtreds=50, tres=60) — very different from German!",
    "English": "🇬🇧 English speakers: Danish V2 rule inverts subject and verb after a fronted element "
               "('I go' → 'Går jeg' when inverted). Articles are suffixes: hunden = the dog, huset = the house. "
               "Pronunciation is the hardest part — many letters are silent.",
    "Spanish": "🇪🇸 Spanish speakers: Danish articles are suffixes added to the noun end (hund-en = the dog). "
               "There's no verb conjugation for person — same form for jeg/du/han. Pronunciation will feel unusual at first.",
    "French":  "🇫🇷 French speakers: Like French, Danish has grammatical gender but only two (en/et). "
               "No verb agreement with subject. Nasal vowels in Danish sound different from French nasals.",
    "Dutch":   "🇳🇱 Dutch speakers: Danish and Dutch are closely related. Many words are similar. "
               "Main differences: Danish spelling is less phonetic, and stød (glottal stop) has no Dutch equivalent.",
}

# ── Sample sessions (pre-fill until real data exists) ─────────────────────────
SAMPLE_SESSIONS = [
    {
        "id": "sample_2",
        "date": "Mar 12, 2026",
        "scene_key": "meet_a_friend",
        "scene_title": "Meet a Friend",
        "level": "A1",
        "bg_lang": "German",
        "score": "2 / 3",
        "coaching_log": [
            {
                "question":   "Hvor gammel er du?",
                "attempt":    "Ich bin 25",
                "correction": "Du sagde det på tysk! På dansk siger man 'Jeg er 25 år gammel' — eller bare '25 år'.",
                "bg_lang":    "German",
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
        "score": "3 / 3",
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

# ── Initialise persistent history (with sample data on first load) ─────────────
if "session_history" not in st.session_state:
    st.session_state["session_history"] = list(SAMPLE_SESSIONS)

# ── Save current session (once per lesson completion) ─────────────────────────
_sk       = st.session_state.get("selected_scene", "")
_level    = st.session_state.get("s_level",   "A1")
_bg_lang  = st.session_state.get("s_bg_lang", "English")
correct_log  = st.session_state.get("correct_log",  [])
coaching_log = st.session_state.get("coaching_log", [])

if (correct_log or coaching_log) and not st.session_state.get("current_session_id"):
    _ts = str(int(datetime.datetime.now().timestamp()))
    st.session_state["current_session_id"] = _ts
    answered = sum(1 for e in correct_log if e["who"] == "student")
    total    = answered + len(coaching_log)
    st.session_state["session_history"].insert(0, {
        "id":          _ts,
        "date":        datetime.datetime.now().strftime("%b %d, %Y"),
        "scene_key":   _sk,
        "scene_title": _scene_by_key.get(_sk, {}).get("title", "Lesson"),
        "level":       _level,
        "bg_lang":     _bg_lang,
        "score":       f"{answered} / {total}" if total else "—",
        "coaching_log": coaching_log,
        "correct_log":  correct_log,
    })

history = st.session_state["session_history"]

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:20px;
  padding:28px;margin-bottom:24px;text-align:center'>
  <div style='font-size:44px;margin-bottom:8px'>📋</div>
  <div style='font:800 24px Segoe UI,sans-serif;color:#e0e7ff;margin-bottom:4px'>Session Feedback</div>
  <div style='font:400 13px Segoe UI;color:rgba(165,180,252,.7)'>Review mistakes, track progress</div>
</div>""", unsafe_allow_html=True)

# ── Shared render function ─────────────────────────────────────────────────────
def render_session(s):
    errors    = s.get("coaching_log", [])
    conv      = s.get("correct_log",  [])
    s_level   = s.get("level",  "")
    s_bg      = s.get("bg_lang","")
    s_score   = s.get("score",  "—")
    char_lbl  = _scene_by_key.get(s.get("scene_key",""), {}).get("char_name", "Character")

    # ── Meta badges ───────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px'>"
        f"<span style='background:rgba(129,140,248,.15);border:1px solid rgba(129,140,248,.3);"
        f"border-radius:8px;padding:5px 11px;font:600 12px Segoe UI;color:#a5b4fc'>📚 {s.get('scene_title','')}</span>"
        f"<span style='background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.25);"
        f"border-radius:8px;padding:5px 11px;font:600 12px Segoe UI;color:#34d399'>Level {s_level}</span>"
        f"<span style='background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.2);"
        f"border-radius:8px;padding:5px 11px;font:600 12px Segoe UI;color:#fbbf24'>🌐 {s_bg}</span>"
        f"<span style='background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);"
        f"border-radius:8px;padding:5px 11px;font:600 12px Segoe UI;color:rgba(255,255,255,.5)'>📅 {s.get('date','')}</span>"
        f"<span style='background:rgba(129,140,248,.2);border:1px solid rgba(129,140,248,.4);"
        f"border-radius:8px;padding:5px 11px;font:700 12px Segoe UI;color:#c7d2fe'>✓ {s_score}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Error cards ───────────────────────────────────────────────────────────
    if errors:
        st.markdown(
            "<div style='font:700 10px Segoe UI;letter-spacing:1.5px;color:#f87171;"
            "text-transform:uppercase;margin-bottom:10px'>Mistakes to review</div>",
            unsafe_allow_html=True
        )
        for err in errors:
            q   = err.get("question","").replace("<","&lt;").replace(">","&gt;")
            att = err.get("attempt","").replace("<","&lt;").replace(">","&gt;")
            cor = err.get("correction","").replace("<","&lt;").replace(">","&gt;")
            st.markdown(
                f"<div style='background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.18);"
                f"border-radius:14px;padding:16px 18px;margin-bottom:12px'>"
                f"<div style='font:600 9px Segoe UI;color:#94a3b8;letter-spacing:.8px;"
                f"text-transform:uppercase;margin-bottom:6px'>Question asked</div>"
                f"<div style='font:500 14px/1.4 Segoe UI;color:#e2e8f0;font-style:italic;"
                f"margin-bottom:14px'>\"{q}\"</div>"
                f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px'>"
                f"  <div style='background:rgba(248,113,113,.1);border-radius:10px;padding:10px 12px'>"
                f"    <div style='font:600 9px Segoe UI;color:#fca5a5;letter-spacing:.8px;"
                f"text-transform:uppercase;margin-bottom:5px'>You said</div>"
                f"    <div style='font:400 13px Segoe UI;color:#fecaca'>{att}</div>"
                f"  </div>"
                f"  <div style='background:rgba(52,211,153,.07);border-radius:10px;padding:10px 12px'>"
                f"    <div style='font:600 9px Segoe UI;color:#6ee7b7;letter-spacing:.8px;"
                f"text-transform:uppercase;margin-bottom:5px'>Question (for reference)</div>"
                f"    <div style='font:400 13px/1.4 Segoe UI;color:#a7f3d0;font-style:italic'>{q}</div>"
                f"  </div>"
                f"</div>"
                f"<div style='background:rgba(129,140,248,.08);border-radius:10px;padding:10px 12px'>"
                f"  <div style='font:600 9px Segoe UI;color:#a78bfa;letter-spacing:.8px;"
                f"text-transform:uppercase;margin-bottom:5px'>💡 Lars explained</div>"
                f"  <div style='font:400 13px/1.5 Segoe UI;color:#c4b5fd'>{cor}</div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<div style='background:rgba(52,211,153,.07);border:1px solid rgba(52,211,153,.2);"
            "border-radius:12px;padding:16px;margin-bottom:16px;text-align:center'>"
            "<div style='font-size:26px;margin-bottom:5px'>🎉</div>"
            "<div style='font:600 14px Segoe UI;color:#34d399'>No mistakes — perfect session!</div>"
            "</div>",
            unsafe_allow_html=True
        )

    # ── Background language tip ────────────────────────────────────────────────
    tip = BG_LANG_TIPS.get(s_bg)
    if tip:
        st.markdown(
            f"<div style='background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.18);"
            f"border-radius:12px;padding:12px 16px;margin-bottom:16px'>"
            f"<div style='font:600 9px Segoe UI;color:#fbbf24;letter-spacing:.8px;"
            f"text-transform:uppercase;margin-bottom:5px'>Language tip for {s_bg} speakers</div>"
            f"<div style='font:400 12px/1.6 Segoe UI;color:rgba(251,191,36,.85)'>{tip}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── Full conversation (collapsed) ─────────────────────────────────────────
    if conv:
        with st.expander("💬 Full conversation"):
            parts = []
            for entry in conv:
                txt = entry["text"].replace("<","&lt;").replace(">","&gt;")
                if entry["who"] == "character":
                    parts.append(
                        f"<div style='background:rgba(255,255,255,.06);border-radius:10px 10px 10px 3px;"
                        f"padding:8px 12px;margin:5px 0;font-size:13px;color:#e2e8f0'>"
                        f"<span style='font:600 9px Segoe UI;color:#94a3b8;text-transform:uppercase;"
                        f"letter-spacing:.5px;display:block;margin-bottom:3px'>{char_lbl}</span>"
                        f"<em>{txt}</em></div>"
                    )
                else:
                    parts.append(
                        f"<div style='background:rgba(129,140,248,.14);border-radius:10px 10px 3px 10px;"
                        f"padding:8px 12px;margin:5px 0 5px 18%;font-size:13px;color:#c7d2fe'>"
                        f"<span style='font:600 9px Segoe UI;color:#818cf8;text-transform:uppercase;"
                        f"letter-spacing:.5px;display:block;margin-bottom:3px'>You ✓</span>"
                        f"{txt}</div>"
                    )
            st.markdown("".join(parts), unsafe_allow_html=True)

# ── Tabs: latest + history ─────────────────────────────────────────────────────
hist_label = f"History ({len(history) - 1})" if len(history) > 1 else "History"
tab_latest, tab_hist = st.tabs(["Latest Session", hist_label])

with tab_latest:
    if history:
        render_session(history[0])
    else:
        st.markdown(
            "<div style='color:rgba(255,255,255,.4);font-size:13px;padding:24px 0;text-align:center'>"
            "No session yet — complete a lesson to see feedback here.</div>",
            unsafe_allow_html=True
        )

with tab_hist:
    past = history[1:]
    if not past:
        st.markdown(
            "<div style='color:rgba(255,255,255,.4);font-size:13px;padding:24px 0;text-align:center'>"
            "Complete more lessons to build your history.</div>",
            unsafe_allow_html=True
        )
    else:
        for s in past:
            errors = s.get("coaching_log", [])
            icon   = "✅" if not errors else f"⚠️ {len(errors)} mistake{'s' if len(errors)>1 else ''}"
            with st.expander(f"**{s.get('scene_title','')}** · {s.get('date','')} · {icon}"):
                render_session(s)

# ── Navigation ─────────────────────────────────────────────────────────────────
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("pages/home.py")
with col2:
    if st.button("← Back to lesson", use_container_width=True):
        st.switch_page("app.py")
with col3:
    if st.button("🔄 New lesson", type="primary", use_container_width=True):
        from pipeline import LESSON_STATE_KEYS
        for k in LESSON_STATE_KEYS:
            st.session_state.pop(k, None)
        st.switch_page("pages/home.py")
