import streamlit as st
from pipeline import VOICES, MODELS, LESSON_STATE_KEYS

st.set_page_config(page_title="Account — SpeakPals", page_icon="⚙", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"]{display:none!important}
  [data-testid="stSidebarCollapseButton"]{display:none!important}
  /* Bright readable page */
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f8fafc!important}
  .block-container{padding:3rem 2rem!important;max-width:520px!important;margin:auto}
  /* Labels */
  label,.stSelectbox label,.stTextInput label{
    color:#1e293b!important;font-size:13px!important;font-weight:600!important}
  /* Inputs */
  .stTextInput input{
    background:#fff!important;color:#1e293b!important;
    border:1px solid #cbd5e1!important;border-radius:8px!important;
    font-size:15px!important}
  .stSelectbox > div > div{
    background:#fff!important;color:#1e293b!important;
    border:1px solid #cbd5e1!important;border-radius:8px!important}
  /* Buttons */
  .stButton button{border-radius:10px!important;font-weight:600!important;font-size:14px!important}
  div[data-testid="stVerticalBlock"]{gap:0.5rem!important}
</style>""", unsafe_allow_html=True)

st.markdown("""
<div style='background:linear-gradient(135deg,#818cf8,#a78bfa);border-radius:16px;
  padding:28px 24px 20px;margin-bottom:28px'>
  <div style='font:800 24px Segoe UI,sans-serif;color:#fff;margin-bottom:4px'>Account Settings</div>
  <div style='font:400 14px Segoe UI;color:rgba(255,255,255,.75)'>Personalise your SpeakPals lesson</div>
</div>
""", unsafe_allow_html=True)

# ── Student profile ────────────────────────────────────────────────────────────

st.markdown("<p style='font:700 11px Segoe UI;letter-spacing:1.5px;color:#64748b;text-transform:uppercase;margin:0 0 8px'>Student Profile</p>", unsafe_allow_html=True)

name = st.text_input("Name", value=st.session_state.get("s_name", "Marlon"))
level = st.selectbox("Level", ["A1", "A2", "B1"],
                     index=["A1", "A2", "B1"].index(st.session_state.get("s_level", "A1")))
bg_lang = st.selectbox("Your language background", ["English", "German", "Swedish"],
                       index=["English", "German", "Swedish"].index(
                           st.session_state.get("s_bg_lang", "German")))

st.markdown("<div style='height:1px;background:#e2e8f0;margin:20px 0 16px'></div>", unsafe_allow_html=True)

# ── Voice & model ──────────────────────────────────────────────────────────────

st.markdown("<p style='font:700 11px Segoe UI;letter-spacing:1.5px;color:#64748b;text-transform:uppercase;margin:0 0 8px'>Preferences</p>", unsafe_allow_html=True)

voice_keys = list(VOICES.keys())
voice_label = st.selectbox("Tutor voice", voice_keys,
                           index=voice_keys.index(
                               st.session_state.get("s_voice_label", voice_keys[0])))

model_keys = list(MODELS.keys())
model_label = st.selectbox("AI model", model_keys,
                           index=model_keys.index(
                               st.session_state.get("s_model_label", "Sonnet 4.6 — best quality")))

st.markdown("<div style='height:1px;background:#e2e8f0;margin:20px 0 16px'></div>", unsafe_allow_html=True)

# ── Save & navigate ────────────────────────────────────────────────────────────

col_save, col_back = st.columns(2)

with col_save:
    if st.button("Save settings", type="primary", use_container_width=True):
        st.session_state["s_name"]        = name
        st.session_state["s_level"]       = level
        st.session_state["s_bg_lang"]     = bg_lang
        st.session_state["s_voice_label"] = voice_label
        st.session_state["s_model_label"] = model_label
        st.success("Saved!")

with col_back:
    if st.button("← Back to lesson", use_container_width=True):
        st.session_state["s_name"]        = name
        st.session_state["s_level"]       = level
        st.session_state["s_bg_lang"]     = bg_lang
        st.session_state["s_voice_label"] = voice_label
        st.session_state["s_model_label"] = model_label
        st.switch_page("app.py")

st.markdown("<div style='height:1px;background:#e2e8f0;margin:20px 0 16px'></div>", unsafe_allow_html=True)

# ── Danger zone ────────────────────────────────────────────────────────────────

st.markdown("<p style='font:700 11px Segoe UI;letter-spacing:1.5px;color:#64748b;text-transform:uppercase;margin:0 0 8px'>Session</p>", unsafe_allow_html=True)

if st.button("🔄 Clear lesson & restart", use_container_width=True):
    for k in LESSON_STATE_KEYS:
        st.session_state.pop(k, None)
    st.switch_page("app.py")
