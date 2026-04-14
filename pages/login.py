import streamlit as st
from db import sign_in, sign_up, send_reset_email, verify_recovery_token, update_password
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

  .stButton button, .stFormSubmitButton button{
    border-radius:10px!important;font-weight:600!important;font-size:14px!important;
    border:1px solid rgba(13,148,136,.3)!important;
    background:rgba(13,148,136,.1)!important;color:#0d9488!important;
    transition:background .2s}
  .stButton button:hover, .stFormSubmitButton button:hover{background:rgba(13,148,136,.2)!important}
  div[data-testid="stVerticalBlock"]{gap:0.4rem!important}

  /* Tab styling */
  .stTabs [data-baseweb="tab-list"]{
    gap:0;border-bottom:1px solid #e5e5e5!important;background:transparent!important}
  .stTabs [data-baseweb="tab"]{
    font:600 14px Inter,sans-serif!important;color:rgba(17,24,39,.45)!important;
    border:none!important;background:transparent!important;
    padding:10px 24px!important;border-radius:0!important}
  .stTabs [aria-selected="true"]{
    color:#0d9488!important;
    border-bottom:2px solid #0d9488!important}
  .stTabs [data-baseweb="tab-panel"]{padding-top:20px!important}
</style>""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:32px 0 28px'>
  <div style='font:800 28px/1 Inter,sans-serif;color:#111827;letter-spacing:-.5px;margin-bottom:8px'>
    SpeakPals
  </div>
  <div style='font:400 14px Inter;color:rgba(17,24,39,.5)'>
    Your AI language tutor
  </div>
</div>""", unsafe_allow_html=True)

# ── Password-reset recovery (Supabase redirects here with ?token_hash=&type=recovery) ─
_qp             = st.query_params
_recovery_token = _qp.get("token_hash")
_recovery_type  = _qp.get("type")

if _recovery_token and _recovery_type == "recovery":
    st.markdown("""
    <div style='text-align:center;padding-bottom:20px'>
      <div style='font:700 18px Inter,sans-serif;color:#111827'>Set a new password</div>
      <div style='font:400 13px Inter;color:rgba(17,24,39,.5);margin-top:4px'>
        Enter a new password for your account.
      </div>
    </div>""", unsafe_allow_html=True)

    # Exchange recovery token for a session once per recovery flow
    if "recovery_session" not in st.session_state:
        with st.spinner("Verifying reset link…"):
            _sess, _err = verify_recovery_token(_recovery_token)
        if _sess:
            st.session_state["recovery_session"] = _sess
        else:
            st.error(f"This reset link is invalid or has expired. {_err or ''}")
            if st.button("Request a new reset link"):
                st.query_params.clear()
                st.rerun()
            st.stop()

    with st.form("reset_pw_form"):
        new_pw      = st.text_input("New password", type="password", placeholder="At least 6 characters")
        confirm_pw  = st.text_input("Confirm new password", type="password", placeholder="••••••••")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        pw_submitted = st.form_submit_button("Set new password", use_container_width=True)

    if pw_submitted:
        if len(new_pw) < 6:
            st.error("Password must be at least 6 characters.")
        elif new_pw != confirm_pw:
            st.error("Passwords don't match.")
        else:
            _access = st.session_state["recovery_session"]["access_token"]
            _err = update_password(_access, new_pw)
            if _err:
                st.error(f"Could not update password: {_err}")
            else:
                # Log the user in with the recovery session and clear recovery state
                _sess = st.session_state.pop("recovery_session")
                st.session_state.sb_access_token  = _sess["access_token"]
                st.session_state.sb_refresh_token = _sess["refresh_token"]
                st.session_state.sb_user_id       = _sess["user_id"]
                st.session_state.sb_email         = _sess["email"]
                st.query_params.clear()
                st.success("Password updated! Redirecting…")
                st.switch_page("pages/home.py")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_login, tab_register, tab_forgot = st.tabs(["Sign in", "Create account", "Forgot password"])

# ── Sign in ───────────────────────────────────────────────────────────────────
with tab_login:
    with st.form("login_form"):
        email_in    = st.text_input("Email", key="login_email", placeholder="you@example.com")
        password_in = st.text_input("Password", key="login_pw", type="password", placeholder="••••••••")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
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

# ── Create account ────────────────────────────────────────────────────────────
_BG_LANGS   = ["English", "German", "Spanish", "French", "Dutch", "Swedish", "Other"]
_CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

with tab_register:
    # Note: intentionally NOT using st.form here — forms batch widget interactions,
    # which prevents the conditional "Other" language field from appearing reactively.
    reg_name     = st.text_input("First name *", key="reg_name")
    reg_email    = st.text_input("Email *", key="reg_email", placeholder="you@example.com")
    reg_password = st.text_input("Password *", key="reg_pw", type="password",
                                 placeholder="At least 6 characters")
    reg_confirm  = st.text_input("Confirm password *", key="reg_confirm", type="password",
                                 placeholder="••••••••")
    reg_bg_sel   = st.selectbox(
        "Main language background *",
        _BG_LANGS,
        help=(
            "The language you speak best — your native tongue or the language you are "
            "most fluent in. Your tutor uses this to explain concepts in a way that "
            "makes sense for someone with your background, and to spot typical mistakes "
            "speakers of your language tend to make."
        ),
        key="reg_bg_sel",
    )
    if reg_bg_sel == "Other":
        reg_bg_other = st.text_input(
            "Specify your language *",
            key="reg_bg_other",
            placeholder="e.g. Turkish, Arabic, Hindi…",
        )
    else:
        reg_bg_other = ""
    reg_level    = st.selectbox(
        "Estimated language level (CEFR) *",
        _CEFR_LEVELS,
        help=(
            "Your current level in the language you want to learn, on the Common "
            "European Framework of Reference scale.\n\n"
            "A1 — complete beginner\n"
            "A2 — basic phrases\n"
            "B1 — can handle simple conversations\n"
            "B2 — comfortable in most situations\n"
            "C1 — advanced, near-fluent\n"
            "C2 — mastery, near-native\n\n"
            "An educated guess is fine — your tutor will adapt."
        ),
        key="reg_level",
    )
    st.markdown(
        "<div style='font:400 11px Inter;color:rgba(17,24,39,.4);margin-top:2px;"
        "margin-bottom:12px'>* Required field</div>",
        unsafe_allow_html=True,
    )
    reg_submitted = st.button("Create account", use_container_width=True, key="btn_register")

    if reg_submitted:
        _bg_lang_val = reg_bg_other.strip() if reg_bg_sel == "Other" else reg_bg_sel
        if not reg_name.strip():
            st.error("First name is required.")
        elif not reg_email.strip():
            st.error("Email is required.")
        elif not reg_password:
            st.error("Password is required.")
        elif not reg_confirm:
            st.error("Please confirm your password.")
        elif reg_bg_sel == "Other" and not reg_bg_other.strip():
            st.error("Please specify your language in the field above.")
        elif len(reg_password) < 6:
            st.error("Password must be at least 6 characters.")
        elif reg_password != reg_confirm:
            st.error("Passwords don't match.")
        else:
            user, err = sign_up(reg_email.strip(), reg_password)
            if err:
                st.error(err)
            else:
                # Try to auto-login immediately (works when email confirmation is disabled)
                session, login_err = sign_in(reg_email.strip(), reg_password)
                if session:
                    from db import upsert_profile
                    st.session_state.sb_access_token  = session["access_token"]
                    st.session_state.sb_refresh_token = session["refresh_token"]
                    st.session_state.sb_user_id       = session["user_id"]
                    st.session_state.sb_email         = session["email"]
                    st.session_state["s_name"]        = reg_name.strip()
                    st.session_state["s_bg_lang"]     = _bg_lang_val
                    st.session_state["s_level"]       = reg_level
                    st.session_state["is_new_user"]   = True
                    # Persist to DB so tutors and settings see these values immediately
                    upsert_profile(session["user_id"], session["access_token"], {
                        "s_name":    reg_name.strip(),
                        "s_bg_lang": _bg_lang_val,
                        "s_level":   reg_level,
                    })
                    st.switch_page("pages/onboarding.py")
                else:
                    st.success(
                        "Account created! Check your email for a confirmation link, "
                        "then sign in."
                    )

# ── Forgot password ───────────────────────────────────────────────────────────
with tab_forgot:
    st.markdown(
        "<div style='font:400 13px Inter;color:rgba(17,24,39,.55);margin-bottom:16px'>"
        "We'll send a reset link to your email address.</div>",
        unsafe_allow_html=True,
    )
    with st.form("forgot_form"):
        forgot_email = st.text_input("Email", key="forgot_email", placeholder="you@example.com")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        forgot_submitted = st.form_submit_button("Send reset link", use_container_width=True)

    if forgot_submitted:
        if not forgot_email.strip():
            st.error("Please enter your email address.")
        else:
            _err = send_reset_email(forgot_email.strip())
            if _err:
                st.error(f"Could not send reset email: {_err}")
            else:
                st.success("Check your inbox — a reset link is on its way.")
