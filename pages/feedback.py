import streamlit as st

st.set_page_config(page_title="Lesson Complete — SpeakPals", page_icon="🎓", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"]{display:none!important}
  [data-testid="stSidebarCollapseButton"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f8fafc!important}
  .block-container{padding:3rem 2rem!important;max-width:600px!important;margin:auto}
  .stButton button{border-radius:10px!important;font-weight:600!important;font-size:14px!important}
</style>""", unsafe_allow_html=True)

st.markdown("""
<div style='background:linear-gradient(135deg,#818cf8,#a78bfa);border-radius:20px;
  padding:36px 28px;margin-bottom:28px;text-align:center'>
  <div style='font-size:56px;margin-bottom:12px'>🎓</div>
  <div style='font:800 28px Segoe UI,sans-serif;color:#fff;margin-bottom:6px'>Lesson Complete!</div>
  <div style='font:400 15px Segoe UI;color:rgba(255,255,255,.8)'>Great work — you made it through the full lesson.</div>
</div>
""", unsafe_allow_html=True)

# Show conversation log if available
log = st.session_state.get("correct_log", [])
if log:
    st.markdown("<p style='font:700 11px Segoe UI;letter-spacing:1.5px;color:#64748b;text-transform:uppercase;margin:0 0 12px'>Your conversation</p>", unsafe_allow_html=True)
    parts = []
    for entry in log:
        txt = entry["text"].replace("<", "&lt;").replace(">", "&gt;")
        if entry["who"] == "character":
            parts.append(
                f"<div style='background:#fff;border:1px solid #e2e8f0;border-radius:12px 12px 12px 3px;"
                f"padding:10px 14px;margin:0 0 6px;font-size:14px;color:#334155;line-height:1.5'>"
                f"<span style='font:600 10px Segoe UI;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:3px'>Cashier</span>"
                f"<em>{txt}</em></div>"
            )
        else:
            parts.append(
                f"<div style='background:#ede9fe;border-radius:12px 12px 3px 12px;"
                f"padding:10px 14px;margin:0 0 10px;font-size:14px;color:#4c1d95;line-height:1.5'>"
                f"<span style='font:600 10px Segoe UI;color:#7c3aed;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:3px'>You ✓</span>"
                f"{txt}</div>"
            )
    st.markdown("".join(parts), unsafe_allow_html=True)
    st.markdown("<div style='height:1px;background:#e2e8f0;margin:20px 0'></div>", unsafe_allow_html=True)
else:
    st.info("Detailed feedback coming in a future update.")

col1, col2 = st.columns(2)
with col1:
    if st.button("← Back to lesson", use_container_width=True):
        st.switch_page("app.py")
with col2:
    if st.button("🔄 New lesson", type="primary", use_container_width=True):
        from pipeline import LESSON_STATE_KEYS
        for k in LESSON_STATE_KEYS:
            st.session_state.pop(k, None)
        st.switch_page("app.py")
