import streamlit as st
import pathlib, base64
import streamlit.components.v1 as components
from pipeline import SCENE_CATALOG, LESSON_STATE_KEYS

st.set_page_config(page_title="SpeakPals", page_icon="🇩🇰",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  [data-testid="stHeader"],header,.stAppHeader{display:none!important}
  [data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarNav"]{display:none!important}
  [data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#0b0b1a!important}
  .block-container{padding:2.5rem 3rem!important;max-width:960px!important;margin:auto}

  /* Scene card */
  .scene-card{
    position:relative;width:100%;padding-top:60%;
    border-radius:18px;overflow:hidden;cursor:pointer;
    background:#1e1e30;
    box-shadow:0 6px 32px rgba(0,0,0,.55);
    transition:transform .22s cubic-bezier(.34,1.56,.64,1),
               box-shadow .22s ease,filter .22s ease}
  .scene-card:hover{
    transform:scale(1.035) translateY(-4px);
    box-shadow:0 16px 48px rgba(129,140,248,.35),0 4px 20px rgba(0,0,0,.6);
    filter:brightness(1.08)}
  .scene-card img{
    position:absolute;inset:0;width:100%;height:100%;
    object-fit:cover;object-position:top center;
    border-radius:18px;transition:transform .22s ease}
  .scene-card:hover img{transform:scale(1.05)}
  .scene-placeholder{position:absolute;inset:0;border-radius:18px}
  .scene-card-overlay{
    position:absolute;bottom:0;left:0;right:0;
    background:linear-gradient(to top,rgba(10,10,26,.92) 0%,rgba(10,10,26,.4) 55%,transparent 100%);
    padding:20px 18px 16px;border-radius:0 0 18px 18px}
  .scene-card-title{font:800 18px/1.2 'Segoe UI',sans-serif;color:#fff;margin-bottom:4px}
  .scene-card-desc{font:400 12px 'Segoe UI',sans-serif;color:rgba(255,255,255,.6)}

  /* Level badge */
  .lvl-badge{
    display:inline-block;padding:3px 9px;border-radius:20px;
    font:700 10px/1 'Segoe UI',sans-serif;letter-spacing:1.2px;
    text-transform:uppercase;margin-bottom:8px}
  .lvl-A1{background:rgba(52,211,153,.18);color:#34d399;border:1px solid rgba(52,211,153,.3)}
  .lvl-A2{background:rgba(251,191,36,.18);color:#fbbf24;border:1px solid rgba(251,191,36,.3)}
  .lvl-B1{background:rgba(129,140,248,.2);color:#a5b4fc;border:1px solid rgba(129,140,248,.35)}
  .lvl-B2{background:rgba(248,113,113,.18);color:#fca5a5;border:1px solid rgba(248,113,113,.3)}

  /* Section heading */
  .section-head{
    font:700 11px/1 'Segoe UI',sans-serif;letter-spacing:2px;
    text-transform:uppercase;color:rgba(255,255,255,.35);
    margin:32px 0 16px;padding-bottom:8px;
    border-bottom:1px solid rgba(255,255,255,.07)}
  .section-head.current{color:rgba(129,140,248,.75);
    border-bottom-color:rgba(129,140,248,.25)}

  /* Buttons */
  label,.stButton button{color:#e2e8f0!important}
  .stButton button{
    margin-top:10px!important;border-radius:12px!important;
    font-weight:600!important;font-size:13px!important;
    background:rgba(129,140,248,.15)!important;
    border:1px solid rgba(129,140,248,.3)!important;color:#c7d2fe!important;
    transition:background .2s,border-color .2s}
  .stButton button:hover{
    background:rgba(129,140,248,.28)!important;
    border-color:rgba(129,140,248,.55)!important}
</style>""", unsafe_allow_html=True)

# ── Settings ───────────────────────────────────────────────────────────────────

name  = st.session_state.get("s_name",  "there")
level = st.session_state.get("s_level", "A1")

LEVEL_LABELS = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper Intermediate"}

# ── Header ─────────────────────────────────────────────────────────────────────

col_hdr, col_acct = st.columns([5, 1])
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
with col_acct:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("⚙ Settings", use_container_width=True):
        st.switch_page("pages/account.py")
    st.markdown("</div>", unsafe_allow_html=True)


# ── Image helper ───────────────────────────────────────────────────────────────

@st.cache_data
def _img_data_url(filename: str) -> str | None:
    path = pathlib.Path(__file__).parent.parent / "assets" / "scenes" / filename
    if not path.exists():
        return None
    data = path.read_bytes()
    mime = "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


# ── Scene cards, grouped by level ──────────────────────────────────────────────

LEVEL_ORDER = ["A1", "A2", "B1", "B2"]

# Gather all levels that actually have scenes
levels_with_scenes = [lvl for lvl in LEVEL_ORDER
                      if any(s["level"] == lvl for s in SCENE_CATALOG)]

for lvl in levels_with_scenes:
    scenes = [s for s in SCENE_CATALOG if s["level"] == lvl]
    is_current = lvl == level

    label_suffix = " — Your level" if is_current else ""
    st.markdown(
        f"<div class='section-head{'current' if is_current else ''}'>"
        f"{lvl} · {LEVEL_LABELS.get(lvl, lvl)}{label_suffix}</div>",
        unsafe_allow_html=True,
    )

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
    <div class='lvl-badge lvl-{scene["level"]}'>{scene["level"]}</div>
    <div class='scene-card-title'>{scene["title"]}</div>
    <div class='scene-card-desc'>{scene["desc"]}</div>
  </div>
</div>""", unsafe_allow_html=True)

            if st.button(f"Start — {scene['title']}", key=scene["key"],
                         use_container_width=True):
                st.session_state["selected_scene"] = scene["key"]
                for k in LESSON_STATE_KEYS:
                    st.session_state.pop(k, None)
                st.switch_page("app.py")

# Wire scene cards so clicking the image/card triggers the Start button
components.html("""<script>
(function wire() {
  var doc = window.parent.document;
  var cards = doc.querySelectorAll('.scene-card:not([data-wired])');
  cards.forEach(function(card) {
    card.setAttribute('data-wired','1');
    card.addEventListener('click', function() {
      var col = card.closest('[data-testid="column"]');
      if (col) { var btn = col.querySelector('button'); if (btn) btn.click(); }
    });
  });
  if (doc.querySelectorAll('.scene-card:not([data-wired])').length > 0)
    setTimeout(wire, 300);
})();
</script>""", height=0)
