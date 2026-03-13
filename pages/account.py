import streamlit as st
from pipeline import VOICES, MODELS, LESSON_STATE_KEYS, SCENE_CATALOG

st.set_page_config(page_title="Account — SpeakPals", page_icon="⚙", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#0b0b1a!important}
  .block-container{padding:3rem 2rem!important;max-width:520px!important;margin:auto}

  /* Labels */
  label,.stSelectbox label,.stTextInput label{
    color:rgba(165,180,252,.7)!important;font-size:12px!important;
    font-weight:600!important;letter-spacing:.5px!important}

  /* Text inputs */
  .stTextInput input{
    background:rgba(255,255,255,.05)!important;color:#e2e8f0!important;
    border:1px solid rgba(129,140,248,.25)!important;border-radius:10px!important;
    font-size:15px!important}
  .stTextInput input:focus{
    border-color:rgba(129,140,248,.6)!important;
    box-shadow:0 0 0 3px rgba(129,140,248,.12)!important}

  /* Selectboxes */
  .stSelectbox > div > div{
    background:rgba(255,255,255,.05)!important;color:#e2e8f0!important;
    border:1px solid rgba(129,140,248,.25)!important;border-radius:10px!important}

  /* Buttons */
  .stButton button{
    border-radius:10px!important;font-weight:600!important;font-size:13px!important;
    background:rgba(129,140,248,.12)!important;
    border:1px solid rgba(129,140,248,.28)!important;
    color:#c7d2fe!important;
    transition:background .2s,border-color .2s}
  .stButton button:hover{
    background:rgba(129,140,248,.22)!important;
    border-color:rgba(129,140,248,.5)!important}

  div[data-testid="stVerticalBlock"]{gap:0.5rem!important}

  /* Section divider */
  .sec-div{height:1px;background:rgba(129,140,248,.12);margin:22px 0 18px}
  .sec-label{font:700 10px 'Segoe UI',sans-serif;letter-spacing:2px;
    color:rgba(165,180,252,.45);text-transform:uppercase;margin:0 0 10px}
</style>""", unsafe_allow_html=True)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:4px 0 28px'>
  <div style='font:800 26px/1 Segoe UI,sans-serif;color:#e0e7ff;letter-spacing:-.5px;
              margin-bottom:6px'>⚙ Settings</div>
  <div style='font:400 13px Segoe UI;color:rgba(129,140,248,.6)'>
    Personalise your SpeakPals experience
  </div>
</div>""", unsafe_allow_html=True)

# ── Student profile ────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Student Profile</div>", unsafe_allow_html=True)

name     = st.text_input("Name", value=st.session_state.get("s_name", "Marlon"))
level    = st.selectbox("Level", ["A1", "A2", "B1", "B2"],
                        index=["A1", "A2", "B1", "B2"].index(
                            st.session_state.get("s_level", "A1")))
bg_langs = ["English", "German", "Spanish", "French", "Dutch", "Swedish"]
bg_lang  = st.selectbox("Your language background", bg_langs,
                        index=bg_langs.index(
                            st.session_state.get("s_bg_lang", "German")
                            if st.session_state.get("s_bg_lang", "German") in bg_langs
                            else "German"))

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Voice & model ──────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Preferences</div>", unsafe_allow_html=True)

voice_keys  = list(VOICES.keys())
voice_label = st.selectbox(
    "Tutor voice",
    voice_keys,
    index=voice_keys.index(st.session_state.get("s_voice_label", voice_keys[0]))
)

# Which scenes would normally use this voice as their primary character voice
SCENE_PRIMARY_VOICE = {
    "meet_a_friend": "Casper — male, calm",
    "cafe":          "Camilla — female",
    "supermarket":   "Camilla — female",
    "flower_store":  "Casper — male, calm",
    "bakery":        "Camilla — female",
    "restaurant":    "Mathias — male baritone",
}
affected = [
    s["title"] for s in SCENE_CATALOG
    if SCENE_PRIMARY_VOICE.get(s["key"]) == voice_label
]
if affected:
    st.markdown(
        f"<div style='background:rgba(129,140,248,.07);border:1px solid rgba(129,140,248,.18);"
        f"border-radius:10px;padding:10px 14px;margin-top:4px;font:400 12px Segoe UI;"
        f"color:rgba(165,180,252,.65)'>"
        f"Auto-swap: <span style='color:#a5b4fc'>{', '.join(affected)}</span> "
        f"will use a different character voice to avoid your tutor voice."
        f"</div>",
        unsafe_allow_html=True
    )

model_keys  = list(MODELS.keys())
model_label = st.selectbox(
    "AI model",
    model_keys,
    index=model_keys.index(
        st.session_state.get("s_model_label", "Haiku 4.5 — fastest"))
)

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Save & navigate ────────────────────────────────────────────────────────────
def _save():
    st.session_state["s_name"]        = name
    st.session_state["s_level"]       = level
    st.session_state["s_bg_lang"]     = bg_lang
    st.session_state["s_voice_label"] = voice_label
    st.session_state["s_model_label"] = model_label

col_save, col_home, col_back = st.columns(3)
with col_save:
    if st.button("Save", use_container_width=True):
        _save()
        st.success("Saved!")
with col_home:
    if st.button("🏠 Home", use_container_width=True):
        _save()
        st.switch_page("pages/home.py")
with col_back:
    if st.button("← Lesson", use_container_width=True):
        _save()
        st.switch_page("app.py")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Session ────────────────────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Session</div>", unsafe_allow_html=True)

if st.button("🔄 Clear lesson & restart", use_container_width=True):
    for k in LESSON_STATE_KEYS:
        st.session_state.pop(k, None)
    st.switch_page("app.py")
