import streamlit as st
from db import sign_in
from pipeline import SETTINGS_DEFAULTS

st.set_page_config(page_title="Login — SpeakPals", page_icon="🔑",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html,body{font-family:'Inter',sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#ffffff!important}
  .block-container{padding:3rem 2rem!important;max-width:420px!important;margin:auto}

  .stTextInput input{
    background:#f9fafb!important;border:1px solid #e5e5e5!important;
    border-radius:10px!important;font-size:15px!important;color:#111827!important;
    -webkit-text-fill-color:#111827!important}
  .stTextInput input:focus{
    border-color:#0d9488!important;
    box-shadow:0 0 0 3px rgba(13,148,136,.1)!important}

  .stButton button{
    border-radius:10px!important;font-weight:600!important;font-size:14px!important;
    border:1px solid rgba(13,148,136,.3)!important;
    background:rgba(13,148,136,.1)!important;color:#0d9488!important;
    transition:background .2s}
  .stButton button:hover{background:rgba(13,148,136,.2)!important}
  div[data-testid="stVerticalBlock"]{gap:0.4rem!important}
</style>""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:32px 0 28px'>
  <div style='font:800 28px/1 Inter,sans-serif;color:#111827;letter-spacing:-.5px;margin-bottom:8px'>
    SpeakPals
  </div>
  <div style='font:400 14px Inter;color:rgba(17,24,39,.5)'>
    Sign in to continue your language journey
  </div>
</div>""", unsafe_allow_html=True)

# ── Sign in form ──────────────────────────────────────────────────────────────
email_in    = st.text_input("Email", key="login_email", placeholder="you@example.com")
password_in = st.text_input("Password", key="login_pw", type="password", placeholder="••••••••")
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
if st.button("Sign in", use_container_width=True, key="btn_login"):
    if not email_in or not password_in:
        st.error("Please enter your email and password.")
    else:
        session, err = sign_in(email_in.strip(), password_in)
        if err:
            st.error(err)
        else:
            st.session_state.sb_access_token  = session["access_token"]
            st.session_state.sb_refresh_token = session["refresh_token"]
            st.session_state.sb_user_id       = session["user_id"]
            st.session_state.sb_email         = session["email"]
            st.switch_page("pages/home.py")
