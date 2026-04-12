"""
Telegram & Calendar settings page for SpeakPals.
"""
import time
import streamlit as st
from db import require_auth
import gcal

require_auth()

st.set_page_config(page_title="Telegram — SpeakPals", page_icon="✈",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html,body{font-family:'Inter',sans-serif!important}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#ffffff!important}
  .block-container{padding:3rem 2rem!important;max-width:520px!important;margin:auto}

  label,.stSelectbox label,.stTextInput label{
    color:rgba(17,24,39,.65)!important;font-size:12px!important;
    font-weight:600!important;letter-spacing:.5px!important}

  .stTextInput input{
    background:#ffffff!important;color:#111827!important;
    -webkit-text-fill-color:#111827!important;
    border:1px solid #e5e5e5!important;border-radius:10px!important;
    font-size:15px!important}

  .stButton button{
    border-radius:10px!important;font-weight:600!important;font-size:13px!important;
    background:rgba(13,148,136,.1)!important;
    border:1px solid rgba(13,148,136,.28)!important;
    color:#0d9488!important;
    transition:background .2s,border-color .2s}
  .stButton button:hover{
    background:rgba(13,148,136,.2)!important;
    border-color:rgba(13,148,136,.5)!important}

  div[data-testid="stVerticalBlock"]{gap:0.5rem!important}
  .sec-div{height:1px;background:rgba(17,24,39,.1);margin:22px 0 18px}
  .sec-label{font:700 10px 'Inter',sans-serif;letter-spacing:2px;
    color:rgba(17,24,39,.4);text-transform:uppercase;margin:0 0 10px}

  .status-badge{
    display:inline-flex;align-items:center;gap:6px;
    padding:5px 12px;border-radius:20px;font-size:13px;font-weight:600}
  .status-on{background:rgba(16,185,129,.12);color:#059669}
  .status-off{background:rgba(107,114,128,.1);color:#6b7280}
  .status-pending{background:rgba(245,158,11,.12);color:#d97706}

  .info-box{
    background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
    padding:16px 18px;font-size:13px;color:#374151;line-height:1.6}
  .info-box code{
    background:#e2e8f0;border-radius:4px;padding:1px 5px;
    font-size:12px;color:#1e293b}
  .code-block{
    background:#111827;color:#f9fafb;border-radius:10px;
    padding:14px 18px;font-family:monospace;font-size:15px;
    letter-spacing:2px;text-align:center;margin:10px 0}
</style>""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:4px 0 28px'>
  <div style='font:800 26px/1 Inter,sans-serif;color:#111827;letter-spacing:-.5px;
              margin-bottom:6px'>✈ Telegram & Calendar</div>
  <div style='font:400 13px Inter;color:rgba(17,24,39,.55)'>
    Connect the SpeakPals Telegram bot and your Google Calendar
  </div>
</div>""", unsafe_allow_html=True)

# ── Telegram bot section ───────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Telegram Bot</div>", unsafe_allow_html=True)



st.markdown("<br>", unsafe_allow_html=True)

st.markdown("""<div class='info-box'>
  <b>How to use the bot</b><br><br>
  1. Open the bot: <a href='https://t.me/SpeakPalsBot' target='_blank'
     style='color:#0d9488;font-weight:600'>t.me/SpeakPalsBot</a><br>
  2. Send <code>/start</code> to begin onboarding<br>
  3. Pick a scene with <code>/scene</code> and start speaking<br><br>
  <b>Commands</b><br>
  <code>/start</code> — welcome &amp; profile setup<br>
  <code>/scene</code> — pick a roleplay scene<br>
  <code>/level</code> — change your level (A1 → B1)<br>
  <code>/stop</code> — end lesson &amp; see corrections<br>
  <code>/calendar</code> — connect Google Calendar<br>
  <code>/reset</code> — start over with a new profile<br><br>
  <b>Tips</b><br>
  • Send a <b>voice note</b> to practise speaking — it's transcribed automatically<br>
  • Send <b>text</b> if you prefer typing<br>
  • Use <code>/stop</code> after a scene to see what to remember
</div>""", unsafe_allow_html=True)

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Google Calendar section ────────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Google Calendar</div>", unsafe_allow_html=True)

# user_key for web app: "web_{sb_user_id}"
sb_user_id = st.session_state.get("sb_user_id")
user_key   = f"web_{sb_user_id}" if sb_user_id else None

cal_connected = gcal.is_connected(user_key) if user_key else False

if cal_connected:
    st.markdown("<div class='status-badge status-on'>● Calendar connected</div>",
                unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    events = gcal.get_upcoming_events(user_key)
    if events:
        st.markdown("**Upcoming events (next 7 days)**")
        for e in events:
            st.markdown(f"- {e}")
    else:
        st.caption("No events in the next 7 days.")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Disconnect Google Calendar"):
        gcal.revoke_token(user_key)
        st.rerun()

elif "gcal_flow" in st.session_state:
    # ── Pending: polling for approval ─────────────────────────────────────────
    flow     = st.session_state.gcal_flow
    deadline = flow["deadline"]
    remaining = int(deadline - time.time())

    if remaining <= 0:
        del st.session_state.gcal_flow
        st.error("The code expired. Please try again.")
        st.rerun()

    st.markdown("<div class='status-badge status-pending'>⏳ Waiting for approval…</div>",
                unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""<div class='info-box'>
      <b>1.</b> Open this link on your phone or computer:<br>
      <a href='{flow["verification_url"]}' target='_blank'
         style='color:#0d9488;font-weight:600'>{flow["verification_url"]}</a><br><br>
      <b>2.</b> Enter this code:
      <div class='code-block'>{flow["user_code"]}</div>
      <b>3.</b> Sign in with Google and click <b>Allow</b><br><br>
      <span style='color:#6b7280;font-size:12px'>Code expires in {remaining // 60}m {remaining % 60}s</span>
    </div>""", unsafe_allow_html=True)

    # Poll once per rerun
    try:
        token = gcal.try_poll_once(flow["device_code"])
        if token:
            gcal.save_token(user_key, token)
            del st.session_state.gcal_flow
            st.success("✅ Google Calendar connected!")
            st.rerun()
        else:
            # Sleep the poll interval then rerun to check again
            time.sleep(flow["interval"])
            st.rerun()
    except PermissionError:
        del st.session_state.gcal_flow
        st.error("❌ Access denied. Please try again.")
    except ValueError:
        del st.session_state.gcal_flow
        st.error("⏰ Code expired. Please try again.")

else:
    # ── Not connected ──────────────────────────────────────────────────────────
    st.markdown("<div class='status-badge status-off'>○ Not connected</div>",
                unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""<div class='info-box'>
      Connect your Google Calendar so your tutor can use upcoming events
      as conversation topics — practise vocabulary for a meeting, a trip,
      or anything on your schedule.
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if not user_key:
        st.warning("Sign in to connect your calendar.")
    elif st.button("Connect Google Calendar"):
        try:
            flow = gcal.start_device_flow()
            st.session_state.gcal_flow = {
                "device_code":      flow["device_code"],
                "user_code":        flow["user_code"],
                "verification_url": flow["verification_url"],
                "interval":         int(flow.get("interval", 5)),
                "deadline":         time.time() + int(flow.get("expires_in", 1800)),
            }
            st.rerun()
        except FileNotFoundError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Could not start calendar login: {e}")

st.markdown("<div class='sec-div'></div>", unsafe_allow_html=True)

# ── Navigation ────────────────────────────────────────────────────────────────
_col1, _col2 = st.columns(2)
with _col1:
    if st.button("← Back to Settings", use_container_width=True):
        st.switch_page("pages/account.py")
with _col2:
    if st.button("🏠 Start Learning", use_container_width=True, type="primary"):
        st.switch_page("pages/home.py")
