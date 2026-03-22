import streamlit as st
from pipeline import SCENE_CATALOG, LESSON_STATE_KEYS
from scene_images import img_b64 as _img_b64

st.set_page_config(page_title="SpeakPals", page_icon="🇩🇰",
                   layout="wide", initial_sidebar_state="collapsed")

# ── Build CSS selectors ────────────────────────────────────────────────────────
_sel  = ", ".join(f".st-key-{s['key']} button" for s in SCENE_CATALOG)
_selH = ", ".join(f".st-key-{s['key']} button:hover" for s in SCENE_CATALOG)
_selP = ", ".join(
    f".st-key-{s['key']} button [data-testid='stMarkdownContainer'],"
    f" .st-key-{s['key']} button p"
    for s in SCENE_CATALOG
)
_selP2 = ", ".join(f".st-key-{s['key']} button p" for s in SCENE_CATALOG)

# Per-scene height based on column count — avoids cropping at different widths.
# 1 col (~900px wide): 380px  2 cols (~450px): 260px  3 cols (~290px): 200px
_HEIGHT_BY_COLS = {1: "380px", 2: "260px", 3: "200px"}

def _height_css() -> str:
    parts = []
    for s in SCENE_CATALOG:
        scenes_in_level = [x for x in SCENE_CATALOG if x["level"] == s["level"]]
        n_cols = min(len(scenes_in_level), 3)
        h = _HEIGHT_BY_COLS[n_cols]
        parts.append(f".st-key-{s['key']} button{{height:{h}!important}}")
    return " ".join(parts)

# Build background CSS per scene — use image if cached, fall back to gradient.
def _bg_css() -> str:
    parts = []
    for s in SCENE_CATALOG:
        img = _img_b64(s["file"])
        if img:
            rule = (f"background-image:url('{img}')!important;"
                    f"background-size:cover!important;"
                    f"background-position:top center!important")
        else:
            rule = f"background:{s['gradient']}!important"
        key = s["key"]
        parts.append(f".st-key-{key} button,.st-key-{key} button:hover{{{rule}}}")
    return " ".join(parts)

st.markdown(f"""<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html,body{{font-family:'Inter',sans-serif!important}}
  #MainMenu,footer,[data-testid="stToolbar"]{{visibility:hidden}}
  [data-testid="stHeader"],header,.stAppHeader{{display:none!important}}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{{display:none!important}}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:#ffffff!important}}
  .block-container{{padding:2.5rem 3rem!important;max-width:960px!important;margin:auto}}

  .section-head{{
    font:700 11px/1 'Inter',sans-serif;letter-spacing:2px;
    text-transform:uppercase;color:rgba(17,24,39,.4);
    margin:32px 0 14px;padding-bottom:8px;
    border-bottom:1px solid rgba(17,24,39,.1)}}
  .section-head.current{{color:#0d9488;
    border-bottom-color:rgba(13,148,136,.3)}}

  /* Header nav buttons — two-line layout, equal size */
  .st-key-nav_feedback button,.st-key-nav_settings button{{
    white-space:pre-wrap!important;text-align:center!important;
    height:70px!important;flex-direction:column!important}}

  /* Header buttons */
  label,.stButton button{{color:#111827!important}}
  .stButton button{{
    border-radius:12px!important;font-weight:600!important;font-size:13px!important;
    background:rgba(13,148,136,.12)!important;
    border:1px solid rgba(13,148,136,.3)!important;color:#0d9488!important;
    transition:background .2s,border-color .2s}}
  .stButton button:hover{{
    background:rgba(13,148,136,.22)!important;
    border-color:rgba(13,148,136,.5)!important}}

  /* ── Scene card buttons ─────────────────────────────────────────────────── */
  {_sel} {{
    display:block!important;width:100%!important;
    height:200px!important;
    padding:0!important;margin:0!important;
    border-radius:18px!important;overflow:hidden!important;border:none!important;
    background-size:cover!important;background-position:top center!important;
    box-shadow:0 4px 20px rgba(17,24,39,.18)!important;
    cursor:pointer!important;position:relative!important;
    transition:transform .22s cubic-bezier(.34,1.56,.64,1),
               box-shadow .22s ease,filter .22s ease!important}}
  {_selH} {{
    transform:scale(1.035) translateY(-4px)!important;
    box-shadow:0 16px 40px rgba(13,148,136,.3),0 4px 16px rgba(17,24,39,.15)!important;
    filter:brightness(1.05)!important}}

  /* Title text pinned to bottom */
  {_selP} {{
    position:absolute!important;
    bottom:0!important;left:0!important;right:0!important;top:auto!important;
    padding:28px 16px 14px!important;
    background:linear-gradient(to top,rgba(10,10,20,.88) 0%,
               rgba(10,10,20,.35) 55%,transparent 100%)!important;
    border-radius:0 0 18px 18px!important;
    text-align:left!important;pointer-events:none!important;margin:0!important}}
  {_selP2} {{
    font:800 17px/1.2 'Inter',sans-serif!important;
    color:#fff!important;text-align:left!important;margin:0!important}}

  .scene-desc{{
    font:400 12px 'Inter',sans-serif;color:rgba(17,24,39,.5);
    margin-top:7px;padding:0 2px;line-height:1.5}}

  /* Per-scene background images (or gradient fallback if not yet cached) */
  {_bg_css()}

  /* Per-scene heights — scaled to column count so nothing gets cropped */
  {_height_css()}
</style>""", unsafe_allow_html=True)


# ── Settings ───────────────────────────────────────────────────────────────────
name  = st.session_state.get("s_name",  "there")
level = st.session_state.get("s_level", "A1")
language = st.session_state.get("s_language", "Danish")
LEVEL_LABELS = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate"}
# Inline SVG flag images — no external files, crisp at any size
_FLAG_SVG = {
    "Danish": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 37 28">'
        '<rect width="37" height="28" fill="#C60C30"/>'
        '<rect x="12" y="0" width="5" height="28" fill="#fff"/>'
        '<rect x="0" y="11.5" width="37" height="5" fill="#fff"/>'
        '</svg>'
    ),
    "Portuguese (Brazilian)": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 28">'
        '<rect width="40" height="28" fill="#009B3A"/>'
        '<polygon points="20,2 38,14 20,26 2,14" fill="#FEDF00"/>'
        '<circle cx="20" cy="14" r="7.5" fill="#002776"/>'
        '<path d="M12.8,11.2 A8.5,8.5 0 0 1 27.2,11.2" stroke="#fff" stroke-width="1.6" fill="none"/>'
        '<rect x="12.5" y="13.2" width="15" height="1.6" fill="#fff"/>'
        '</svg>'
    ),
}

def _flag_img(lang: str, height: int = 32) -> str:
    import base64
    svg = _FLAG_SVG.get(lang, "")
    if not svg:
        return ""
    b64 = base64.b64encode(svg.encode()).decode()
    return (f"<img src='data:image/svg+xml;base64,{b64}' "
            f"height='{height}' style='vertical-align:middle;border-radius:4px;"
            f"box-shadow:0 2px 8px rgba(0,0,0,.2);margin-left:10px'>")

flag_img = _flag_img(language, height=30)

# ── Header ─────────────────────────────────────────────────────────────────────
col_hdr, col_fb, col_acct = st.columns([5, 1, 1])
with col_hdr:
    st.markdown(f"""
<div style='padding:8px 0 4px'>
  <div style='font:800 30px/1.1 Inter,sans-serif;color:#111827;letter-spacing:-.5px;display:flex;align-items:center;gap:0'>
    Hej, {name}! 👋{flag_img}
  </div>
  <div style='font:400 14px Inter;color:rgba(17,24,39,.6);margin-top:6px'>
    Your level: <span style='color:#0d9488;font-weight:600'>{level} — {LEVEL_LABELS.get(level,"")}</span>
    &nbsp;·&nbsp; Choose a scene to practise {language}
  </div>
</div>""", unsafe_allow_html=True)
with col_fb:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("📋\nFeedback", key="nav_feedback", use_container_width=True):
        st.switch_page("pages/feedback.py")
    st.markdown("</div>", unsafe_allow_html=True)
with col_acct:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("⚙️\nSettings", key="nav_settings", use_container_width=True):
        st.switch_page("pages/account.py")
    st.markdown("</div>", unsafe_allow_html=True)


# ── Scene cards ────────────────────────────────────────────────────────────────
LEVEL_ORDER = ["A1", "A2", "B1", "B2"]
levels_with_scenes = [lvl for lvl in LEVEL_ORDER
                      if any(s["level"] == lvl for s in SCENE_CATALOG)]

for lvl in levels_with_scenes:
    scenes = [s for s in SCENE_CATALOG if s["level"] == lvl]
    is_cur = lvl == level
    st.markdown(
        f"<div class='section-head{'current' if is_cur else ''}'>"
        f"{lvl} · {LEVEL_LABELS.get(lvl, lvl)}{' — Your level' if is_cur else ''}</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(min(len(scenes), 3), gap="large")
    for col, scene in zip(cols, scenes):
        with col:
            if st.button(scene["title"], key=scene["key"], use_container_width=True):
                st.session_state["selected_scene"] = scene["key"]
                for k in LESSON_STATE_KEYS:
                    st.session_state.pop(k, None)
                st.switch_page("app.py")
            st.markdown(
                f"<div class='scene-desc'>{scene['desc']}</div>",
                unsafe_allow_html=True,
            )

