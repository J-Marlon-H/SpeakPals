import streamlit as st
from pipeline import SCENE_CATALOG, LESSON_STATE_KEYS

st.set_page_config(page_title="SpeakPals", page_icon="🇩🇰",
                   layout="wide", initial_sidebar_state="collapsed")

# ── Build per-scene button CSS selectors ──────────────────────────────────────
_sel  = ", ".join(f".st-key-{s['key']} button" for s in SCENE_CATALOG)
_selH = ", ".join(f".st-key-{s['key']} button:hover" for s in SCENE_CATALOG)
_selP = ", ".join(
    f".st-key-{s['key']} button [data-testid='stMarkdownContainer'],"
    f" .st-key-{s['key']} button p"
    for s in SCENE_CATALOG
)
_selP2 = ", ".join(f".st-key-{s['key']} button p" for s in SCENE_CATALOG)

st.markdown(f"""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{{visibility:hidden}}
  [data-testid="stHeader"],header,.stAppHeader{{display:none!important}}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{{display:none!important}}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:#0b0b1a!important}}
  .block-container{{padding:2.5rem 3rem!important;max-width:960px!important;margin:auto}}

  /* Section heading */
  .section-head{{
    font:700 11px/1 'Segoe UI',sans-serif;letter-spacing:2px;
    text-transform:uppercase;color:rgba(255,255,255,.35);
    margin:32px 0 14px;padding-bottom:8px;
    border-bottom:1px solid rgba(255,255,255,.07)}}
  .section-head.current{{color:rgba(129,140,248,.75);
    border-bottom-color:rgba(129,140,248,.25)}}

  /* Header buttons (Feedback, Settings) */
  label,.stButton button{{color:#e2e8f0!important}}
  .stButton button{{
    border-radius:12px!important;font-weight:600!important;font-size:13px!important;
    background:rgba(129,140,248,.15)!important;
    border:1px solid rgba(129,140,248,.3)!important;color:#c7d2fe!important;
    transition:background .2s,border-color .2s}}
  .stButton button:hover{{
    background:rgba(129,140,248,.28)!important;
    border-color:rgba(129,140,248,.5)!important}}

  /* ── Scene card buttons ────────────────────────────────────────────────────
     The button IS the card.  background-image = scene photo (injected below).
     aspect-ratio keeps the card proportional at any column width.            */
  {_sel} {{
    display:block!important;
    width:100%!important;
    height:auto!important;
    aspect-ratio:5/3!important;
    max-height:320px!important;
    padding:0!important;
    margin:0!important;
    border-radius:18px!important;
    overflow:hidden!important;
    border:none!important;
    background-size:cover!important;
    background-position:top center!important;
    background-color:#1e1e30!important;
    box-shadow:0 6px 32px rgba(0,0,0,.55)!important;
    cursor:pointer!important;
    position:relative!important;
    transition:transform .22s cubic-bezier(.34,1.56,.64,1),
               box-shadow .22s ease,filter .22s ease!important}}
  {_selH} {{
    transform:scale(1.035) translateY(-4px)!important;
    box-shadow:0 16px 48px rgba(129,140,248,.35),0 4px 20px rgba(0,0,0,.6)!important;
    filter:brightness(1.08)!important}}

  /* Label text — pinned to bottom with gradient overlay */
  {_selP} {{
    position:absolute!important;
    bottom:0!important;left:0!important;right:0!important;top:auto!important;
    padding:28px 16px 14px!important;
    background:linear-gradient(to top,rgba(10,10,26,.92) 0%,
               rgba(10,10,26,.4) 55%,transparent 100%)!important;
    border-radius:0 0 18px 18px!important;
    text-align:left!important;
    pointer-events:none!important;
    margin:0!important}}
  {_selP2} {{
    font:800 17px/1.2 'Segoe UI',sans-serif!important;
    color:#fff!important;
    text-align:left!important;
    margin:0!important}}

  /* Description text below each card */
  .scene-desc{{
    font:400 12px 'Segoe UI',sans-serif;
    color:rgba(255,255,255,.4);
    margin-top:7px;padding:0 2px;line-height:1.5}}
</style>""", unsafe_allow_html=True)

# ── Per-scene background-image via static file URL (fast — no base64) ─────────
img_css = []
for s in SCENE_CATALOG:
    img_url = f"app/static/scenes/{s['file']}"
    img_css.append(
        f".st-key-{s['key']} button{{"
        f"background-image:url('{img_url}')!important}}"
    )
st.markdown(f"<style>{''.join(img_css)}</style>", unsafe_allow_html=True)


# ── Settings ───────────────────────────────────────────────────────────────────
name  = st.session_state.get("s_name",  "there")
level = st.session_state.get("s_level", "A1")
LEVEL_LABELS = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate"}

# ── Header ─────────────────────────────────────────────────────────────────────
col_hdr, col_fb, col_acct = st.columns([5, 1, 1])
with col_hdr:
    st.markdown(f"""
<div style='padding:8px 0 4px'>
  <div style='font:800 30px/1.1 Segoe UI,sans-serif;color:#e0e7ff;letter-spacing:-.5px'>
    Hej, {name}! 👋
  </div>
  <div style='font:400 14px Segoe UI;color:rgba(129,140,248,.75);margin-top:6px'>
    Your level: <span style='color:#a5b4fc;font-weight:600'>{level} — {LEVEL_LABELS.get(level,"")}</span>
    &nbsp;·&nbsp; Choose a scene to practise Danish
  </div>
</div>""", unsafe_allow_html=True)
with col_fb:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("📋 Feedback", use_container_width=True):
        st.switch_page("pages/feedback.py")
    st.markdown("</div>", unsafe_allow_html=True)
with col_acct:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("⚙ Settings", use_container_width=True):
        st.switch_page("pages/account.py")
    st.markdown("</div>", unsafe_allow_html=True)


# ── Scene cards, grouped by level ──────────────────────────────────────────────
LEVEL_ORDER = ["A1", "A2", "B1", "B2"]
levels_with_scenes = [lvl for lvl in LEVEL_ORDER
                      if any(s["level"] == lvl for s in SCENE_CATALOG)]

for lvl in levels_with_scenes:
    scenes = [s for s in SCENE_CATALOG if s["level"] == lvl]
    is_cur = lvl == level
    suffix = " — Your level" if is_cur else ""
    st.markdown(
        f"<div class='section-head{'current' if is_cur else ''}'>"
        f"{lvl} · {LEVEL_LABELS.get(lvl, lvl)}{suffix}</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(min(len(scenes), 3), gap="large")
    for col, scene in zip(cols, scenes):
        with col:
            # Button IS the card — background-image loaded from static URL
            if st.button(scene["title"], key=scene["key"], use_container_width=True):
                st.session_state["selected_scene"] = scene["key"]
                for k in LESSON_STATE_KEYS:
                    st.session_state.pop(k, None)
                st.switch_page("app.py")

            st.markdown(
                f"<div class='scene-desc'>{scene['desc']}</div>",
                unsafe_allow_html=True,
            )
