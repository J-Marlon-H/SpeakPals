from __future__ import annotations
import streamlit as st
import pathlib, base64
from pipeline import SCENE_CATALOG, LESSON_STATE_KEYS

st.set_page_config(page_title="Choose a Scene — SpeakPals", page_icon="🎭",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#0f0f1a!important}
  .block-container{padding:2.5rem 3rem!important;max-width:900px!important;margin:auto}

  /* Scene card */
  .scene-card{
    position:relative;width:100%;padding-top:62%;
    border-radius:18px;overflow:hidden;cursor:pointer;
    background:#1e1e30;
    box-shadow:0 6px 32px rgba(0,0,0,.55);
    transition:transform .22s cubic-bezier(.34,1.56,.64,1),
               box-shadow .22s ease,
               filter .22s ease}
  .scene-card:hover{
    transform:scale(1.035) translateY(-4px);
    box-shadow:0 16px 48px rgba(129,140,248,.35),0 4px 20px rgba(0,0,0,.6);
    filter:brightness(1.08)}
  .scene-card img{
    position:absolute;inset:0;width:100%;height:100%;
    object-fit:cover;object-position:top center;border-radius:18px;
    transition:transform .22s ease}
  .scene-card:hover img{transform:scale(1.05)}
  .scene-card-overlay{
    position:absolute;bottom:0;left:0;right:0;
    background:linear-gradient(to top,rgba(10,10,26,.92) 0%,rgba(10,10,26,.4) 55%,transparent 100%);
    padding:24px 22px 20px;border-radius:0 0 18px 18px}
  .scene-card-tag{
    font:700 9px/1 'Segoe UI',sans-serif;letter-spacing:2.5px;
    text-transform:uppercase;color:#a78bfa;margin-bottom:6px}
  .scene-card-title{
    font:800 20px/1.2 'Segoe UI',sans-serif;color:#fff;margin-bottom:4px}
  .scene-card-desc{
    font:400 12px 'Segoe UI',sans-serif;color:rgba(255,255,255,.6)}

  /* Placeholder gradient for missing images */
  .scene-placeholder{
    position:absolute;inset:0;border-radius:18px}

  /* Labels / buttons */
  label,.stButton button{color:#e2e8f0!important}
  .stButton button{
    margin-top:12px!important;border-radius:12px!important;
    font-weight:600!important;font-size:14px!important;
    background:rgba(129,140,248,.15)!important;
    border:1px solid rgba(129,140,248,.3)!important;
    color:#c7d2fe!important;
    transition:background .2s,border-color .2s}
  .stButton button:hover{
    background:rgba(129,140,248,.28)!important;
    border-color:rgba(129,140,248,.55)!important}
</style>""", unsafe_allow_html=True)


def _img_data_url(filename: str) -> str | None:
    path = pathlib.Path(__file__).parent.parent / "assets" / "scenes" / filename
    if not path.exists():
        return None
    data = path.read_bytes()
    mime = "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


level       = st.session_state.get("s_level",    "A1")
target_lang = st.session_state.get("s_language", "Danish")

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown(f"""
<div style='text-align:center;margin-bottom:36px'>
  <div style='font:800 28px Segoe UI,sans-serif;color:#e0e7ff;letter-spacing:-.5px'>
    Choose your next scene
  </div>
  <div style='font:400 14px Segoe UI;color:rgba(129,140,248,.75);margin-top:6px'>
    Pick where you want to practice {target_lang} next
  </div>
</div>
""", unsafe_allow_html=True)

# ── Scene cards — show scenes matching the user's level ────────────────────────

scenes = [s for s in SCENE_CATALOG if s["level"] == level]
if not scenes:
    scenes = SCENE_CATALOG  # fallback: show all if level has no scenes

cols = st.columns(min(len(scenes), 3), gap="large")

for col, scene in zip(cols, scenes):
    with col:
        img_url = _img_data_url(scene["file"])
        if img_url:
            img_html = f"<img src='{img_url}' alt='{scene['title']}'>"
        else:
            gradient = scene["gradient"]
            img_html = f"<div class='scene-placeholder' style='background:{gradient}'></div>"

        st.markdown(f"""
<div class='scene-card'>
  {img_html}
  <div class='scene-card-overlay'>
    <div class='scene-card-tag'>{scene['level']}</div>
    <div class='scene-card-title'>{scene['title']}</div>
    <div class='scene-card-desc'>{scene['desc']}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        if st.button(f"Choose — {scene['title']}", key=scene["key"], use_container_width=True):
            st.session_state["selected_scene"] = scene["key"]
            for k in LESSON_STATE_KEYS:
                st.session_state.pop(k, None)
            st.switch_page("app.py")

# ── Bottom links ───────────────────────────────────────────────────────────────

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    if st.button("← Back to lesson", use_container_width=True):
        st.switch_page("app.py")
with c2:
    if st.button("🏠 All scenes", use_container_width=True):
        st.switch_page("pages/home.py")
