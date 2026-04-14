"""Password reset page — Supabase redirects here after the reset email link is clicked."""
import streamlit as st
import streamlit.components.v1 as _cv1
from db import exchange_code_for_session, verify_recovery_token, update_password, session_from_tokens

st.set_page_config(page_title="Reset Password — SpeakPals", page_icon="🔑",
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
  .stButton button,.stFormSubmitButton button{
    border-radius:10px!important;font-weight:600!important;font-size:14px!important;
    border:1px solid rgba(13,148,136,.3)!important;
    background:rgba(13,148,136,.1)!important;color:#0d9488!important;
    transition:background .2s}
  .stButton button:hover,.stFormSubmitButton button:hover{
    background:rgba(13,148,136,.2)!important}
  div[data-testid="stVerticalBlock"]{gap:0.4rem!important}
</style>""", unsafe_allow_html=True)

st.markdown("""
<div style='text-align:center;padding:32px 0 28px'>
  <div style='font:800 28px/1 Inter,sans-serif;color:#111827;letter-spacing:-.5px;margin-bottom:8px'>
    SpeakPals
  </div>
  <div style='font:700 16px Inter;color:#111827;margin-bottom:4px'>Set a new password</div>
  <div style='font:400 13px Inter;color:rgba(17,24,39,.5)'>
    Enter a new password for your account.
  </div>
</div>""", unsafe_allow_html=True)

# ── Handle Supabase implicit-flow hash fragments ──────────────────────────────
# Supabase implicit flow puts tokens in the URL hash (#access_token=…&type=recovery).
# Python cannot read hash fragments, so this JS (in a component iframe) detects them
# and reloads the page with those values as regular query params instead.
#
# CRITICAL: if Python-readable params (code / token_hash / access_token) are already
# in the query string, the script exits immediately — it MUST NOT replace the URL
# while Python is in the middle of handling a successful token exchange.
_cv1.html("""<script>
(function () {
  try {
    var par = window.parent;
    var sp  = new URLSearchParams(par.location.search);
    // Useful params already present — Python will handle them; don't touch the URL
    if (sp.get('code') || sp.get('token_hash') || sp.get('access_token')) return;
    // Check the hash for implicit-flow tokens
    var h = par.location.hash;
    if (h && h.length > 1) {
      var hp = new URLSearchParams(h.substring(1));
      if (hp.get('access_token') || hp.get('token_hash')) {
        par.location.replace(par.location.pathname + '?' + h.substring(1));
      }
    }
    // No hash tokens found — do nothing; Python will show the error
  } catch (e) {}
})();
</script>""", height=0)

# ── Exchange the recovery code/token for a session (once) ────────────────────
# app.py may have stashed the code in session_state before switching pages
# (st.switch_page drops query params from the URL).
if "reset_session" not in st.session_state:
    _qp           = st.query_params
    _code         = _qp.get("code") or st.session_state.pop("_reset_code", None)
    _token_hash   = _qp.get("token_hash") or st.session_state.pop("_reset_token_hash", None)
    _type         = _qp.get("type") or ("recovery" if _token_hash else "")
    _access_token = _qp.get("access_token")   # implicit flow: moved from hash by JS above
    _refresh_tok  = _qp.get("refresh_token") or ""

    if _code:
        with st.spinner("Verifying reset link…"):
            _sess, _err = exchange_code_for_session(_code)
    elif _token_hash and _type == "recovery":
        with st.spinner("Verifying reset link…"):
            _sess, _err = verify_recovery_token(_token_hash)
    elif _access_token:
        # Tokens arrived via URL hash (implicit flow), moved to query params by JS
        with st.spinner("Verifying reset link…"):
            _sess, _err = session_from_tokens(_access_token, _refresh_tok)
    else:
        _sess, _err = None, "No reset token found."

    if _sess:
        st.session_state["reset_session"] = _sess
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"This reset link is invalid or has expired. {_err or ''}")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Request a new reset link", use_container_width=True):
            st.switch_page("pages/login.py")
        st.stop()

# ── Set new password form ─────────────────────────────────────────────────────
with st.form("reset_pw_form"):
    new_pw     = st.text_input("New password", type="password",
                               placeholder="At least 6 characters")
    confirm_pw = st.text_input("Confirm new password", type="password",
                               placeholder="••••••••")
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    submitted  = st.form_submit_button("Set new password", use_container_width=True)

if submitted:
    if len(new_pw) < 6:
        st.error("Password must be at least 6 characters.")
    elif new_pw != confirm_pw:
        st.error("Passwords don't match.")
    else:
        _s   = st.session_state["reset_session"]
        _err = update_password(_s["access_token"], new_pw, _s.get("refresh_token", ""))
        if _err:
            st.error(f"Could not update password: {_err}")
        else:
            st.session_state.sb_access_token  = _s["access_token"]
            st.session_state.sb_refresh_token = _s["refresh_token"]
            st.session_state.sb_user_id       = _s["user_id"]
            st.session_state.sb_email         = _s["email"]
            st.session_state.pop("reset_session", None)
            st.success("Password updated!")
            st.switch_page("pages/home.py")
