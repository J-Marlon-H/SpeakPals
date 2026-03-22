import base64, pathlib


def _b64_image(url_or_path: str) -> str:
    """Return a data: URI for local files, or pass through http(s) URLs."""
    p = pathlib.Path(url_or_path)
    if p.exists():
        data = p.read_bytes()
        mime = "image/png" if url_or_path.lower().endswith(".png") else "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return url_or_path


_SVG_FACE = """\
<svg class="head" width="100" height="100" viewBox="0 0 400 400">
  <ellipse cx="200" cy="138" rx="136" ry="132" fill="#c8956c"/>
  <rect x="168" y="346" width="64" height="48" rx="20" fill="#FECBA1"/>
  <ellipse cx="200" cy="415" rx="168" ry="78" fill="#818cf8"/>
  <ellipse cx="200" cy="208" rx="128" ry="146" fill="#FECBA1"/>
  <ellipse cx="128" cy="256" rx="30" ry="18" fill="#ffb3a7" opacity=".38"/>
  <ellipse cx="272" cy="256" rx="30" ry="18" fill="#ffb3a7" opacity=".38"/>
  <ellipse cx="200" cy="88" rx="136" ry="70" fill="#c8956c"/>
  <ellipse cx="88" cy="168" rx="27" ry="70" fill="#c8956c"/>
  <ellipse cx="312" cy="168" rx="27" ry="70" fill="#c8956c"/>
  <ellipse cx="144" cy="80" rx="54" ry="42" fill="#c8956c"/>
  <ellipse cx="256" cy="80" rx="54" ry="42" fill="#c8956c"/>
  <g class="eyes">
    <ellipse cx="152" cy="178" rx="31" ry="27" fill="white"/>
    <circle cx="152" cy="180" r="18" fill="#5b8dd9"/>
    <circle cx="152" cy="180" r="10" fill="#1a1a2e"/>
    <circle cx="158" cy="173" r="5.5" fill="white"/>
    <circle cx="145" cy="184" r="2.5" fill="white" opacity=".6"/>
    <path d="M120 162 Q152 148 184 162" stroke="#a0522d" stroke-width="5" fill="none" stroke-linecap="round"/>
    <ellipse cx="248" cy="178" rx="31" ry="27" fill="white"/>
    <circle cx="248" cy="180" r="18" fill="#5b8dd9"/>
    <circle cx="248" cy="180" r="10" fill="#1a1a2e"/>
    <circle cx="254" cy="173" r="5.5" fill="white"/>
    <circle cx="241" cy="184" r="2.5" fill="white" opacity=".6"/>
    <path d="M216 162 Q248 148 280 162" stroke="#a0522d" stroke-width="5" fill="none" stroke-linecap="round"/>
  </g>
  <ellipse cx="200" cy="234" rx="9" ry="6" fill="#e8a87c" opacity=".45"/>
  <g class="mouth" id="mouth">
    <path d="M 165 292 Q 200 300 235 292 Q 200 316 165 292 Z" fill="#e05c6a"/>
    <path d="M 165 292 Q 200 286 235 292" fill="#f28b82"/>
    <path d="M 174 293 Q 200 306 226 293" stroke="#c0404e" stroke-width="1.5" fill="none"/>
  </g>
</svg>"""


_AVATAR_CSS = """\
.blob{position:absolute;width:110px;height:110px;border-radius:60% 40% 55% 45%/50% 55% 45% 50%;
  background:linear-gradient(135deg,#e0e9ff,#f5e6ff);animation:blobmorph 6s ease-in-out infinite;z-index:0}
@keyframes blobmorph{0%,100%{border-radius:60% 40% 55% 45%/50% 55% 45% 50%}
  33%{border-radius:45% 55% 40% 60%/55% 40% 60% 45%}
  66%{border-radius:55% 45% 60% 40%/40% 60% 50% 55%}}
svg{position:relative;z-index:1}
@keyframes breathe{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
.head{animation:breathe 3.5s ease-in-out infinite}
@keyframes blink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(0.05)}}
.eyes{animation:blink 5s ease-in-out infinite;transform-origin:center 178px}
@keyframes talk{0%,100%{d:path("M 165 292 Q 200 300 235 292 Q 200 316 165 292 Z")}
  40%{d:path("M 167 287 Q 200 274 233 287 Q 200 323 167 287 Z")}}
.mouth.on{animation:talk 0.2s ease-in-out infinite}
@keyframes dot{0%,80%,100%{opacity:.2;transform:translateY(0)}40%{opacity:1;transform:translateY(-5px)}}"""


_AVATAR_JS = """\
const mouth=document.getElementById('mouth'),lbl=document.getElementById('lbl');
function speak(){mouth.classList.add('on');lbl.textContent='Speaking...';lbl.className='lbl s'}
function idle(){mouth.classList.remove('on');lbl.textContent='';lbl.className='lbl'}"""


def scene_with_avatar_html(image_src: str, scene_caption: str = "",
                            chunks=None, thinking=False) -> str:
    """Scene image filling the frame with avatar overlaid in bottom-right corner."""
    clips = chunks or []
    audio_tags = "\n".join(
        f'<audio id="c{i}" src="data:audio/mpeg;base64,{b}" preload="auto"></audio>'
        for i, b in enumerate(clips))

    chain_js = ""
    if clips:
        chain_js = f"""
const clips = Array.from({{length:{len(clips)}}}, (_,i) => document.getElementById('c'+i));
function playNext(i) {{
  if (i >= clips.length) {{ idle(); return; }}
  speak();
  clips[i].play().catch(e => playNext(i+1));
  clips[i].onended = () => playNext(i+1);
}}
setTimeout(() => playNext(0), 100);"""

    dot_d  = "flex" if thinking else "none"
    label  = "Thinking..." if thinking else ""
    src    = _b64_image(image_src)
    caption_html = (
        f'<div class="caption">{scene_caption}</div>' if scene_caption else ""
    )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100%;height:100%;background:#1a1a2e;overflow:hidden}}
.wrap{{position:relative;width:100%;height:100%}}
.scene-img{{width:100%;height:100%;object-fit:contain;display:block;border-radius:0}}
.caption{{position:absolute;bottom:0;left:0;right:0;
  background:linear-gradient(transparent,rgba(0,0,0,.45));
  color:white;font:13px/1.4 'Inter',sans-serif;padding:28px 16px 10px;
  pointer-events:none}}
.avatar-panel{{
  position:absolute;bottom:14px;right:14px;
  width:148px;
  background:rgba(255,255,255,0.92);
  backdrop-filter:blur(8px);
  border-radius:16px;
  padding:10px 8px 7px;
  display:flex;flex-direction:column;align-items:center;gap:4px;
  box-shadow:0 4px 20px rgba(0,0,0,0.25)}}
.head-wrap{{position:relative;width:110px;height:110px;display:flex;align-items:center;justify-content:center}}
{_AVATAR_CSS}
.dots{{display:{dot_d};gap:4px;align-items:center}}
.dots span{{width:5px;height:5px;border-radius:50%;background:#a78bfa;animation:dot 1.1s ease-in-out infinite}}
.dots span:nth-child(2){{animation-delay:.18s}}.dots span:nth-child(3){{animation-delay:.36s}}
.lbl{{font:11px/1 'Inter',sans-serif;color:#94a3b8;letter-spacing:.3px;min-height:14px}}
.lbl.s{{color:#818cf8}}
</style></head><body>
{audio_tags}
<div class="wrap">
  <img class="scene-img" src="{src}">
  {caption_html}
  <div class="avatar-panel">
    <div class="head-wrap">
      <div class="blob"></div>
      {_SVG_FACE}
    </div>
    <div class="dots"><span></span><span></span><span></span></div>
    <div class="lbl" id="lbl">{label}</div>
  </div>
</div>
<script>
{_AVATAR_JS}
{chain_js}
</script></body></html>"""


# ── Legacy standalone avatar (kept for backwards-compat) ──────────────────────

def avatar_html(chunks=None, thinking=False):
    clips = chunks or []
    audio_tags = "\n".join(
        f'<audio id="c{i}" src="data:audio/mpeg;base64,{b}" preload="auto"></audio>'
        for i, b in enumerate(clips))

    chain_js = ""
    if clips:
        chain_js = f"""
const clips = Array.from({{length:{len(clips)}}}, (_,i) => document.getElementById('c'+i));
function playNext(i) {{
  if (i >= clips.length) {{ idle(); return; }}
  speak();
  clips[i].play().catch(e => playNext(i+1));
  clips[i].onended = () => playNext(i+1);
}}
setTimeout(() => playNext(0), 100);"""

    dot_d = "flex" if thinking else "none"
    label = "Thinking..." if thinking else "Ready"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:transparent;display:flex;justify-content:center;align-items:center;height:100vh;overflow:hidden}}
.scene{{display:flex;flex-direction:column;align-items:center;gap:10px}}
.blob{{position:absolute;width:240px;height:240px;border-radius:60% 40% 55% 45%/50% 55% 45% 50%;
  background:linear-gradient(135deg,#e0e9ff,#f5e6ff);animation:blobmorph 6s ease-in-out infinite;z-index:0}}
@keyframes blobmorph{{0%,100%{{border-radius:60% 40% 55% 45%/50% 55% 45% 50%}}
  33%{{border-radius:45% 55% 40% 60%/55% 40% 60% 45%}}
  66%{{border-radius:55% 45% 60% 40%/40% 60% 50% 55%}}}}
svg{{position:relative;z-index:1}}
@keyframes breathe{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
.head{{animation:breathe 3.5s ease-in-out infinite}}
@keyframes blink{{0%,92%,100%{{transform:scaleY(1)}}96%{{transform:scaleY(0.05)}}}}
.eyes{{animation:blink 5s ease-in-out infinite;transform-origin:center 178px}}
@keyframes talk{{0%,100%{{d:path("M 165 292 Q 200 300 235 292 Q 200 316 165 292 Z")}}
  40%{{d:path("M 167 287 Q 200 274 233 287 Q 200 323 167 287 Z")}}}}
.mouth.on{{animation:talk 0.2s ease-in-out infinite}}
@keyframes dot{{0%,80%,100%{{opacity:.2;transform:translateY(0)}}40%{{opacity:1;transform:translateY(-5px)}}}}
.dots{{display:{dot_d};gap:6px;align-items:center}}
.dots span{{width:7px;height:7px;border-radius:50%;background:#a78bfa;animation:dot 1.1s ease-in-out infinite}}
.dots span:nth-child(2){{animation-delay:.18s}}.dots span:nth-child(3){{animation-delay:.36s}}
.lbl{{font:13px/1 'Inter',sans-serif;color:#94a3b8;letter-spacing:.4px}}
.lbl.s{{color:#818cf8}}
</style></head><body>
{audio_tags}
<div class="scene">
  <div style="position:relative;width:240px;height:240px;display:flex;align-items:center;justify-content:center">
    <div class="blob"></div>
    <svg class="head" width="210" height="210" viewBox="0 0 400 400">
      <ellipse cx="200" cy="138" rx="136" ry="132" fill="#c8956c"/>
      <rect x="168" y="346" width="64" height="48" rx="20" fill="#FECBA1"/>
      <ellipse cx="200" cy="415" rx="168" ry="78" fill="#818cf8"/>
      <ellipse cx="200" cy="208" rx="128" ry="146" fill="#FECBA1"/>
      <ellipse cx="128" cy="256" rx="30" ry="18" fill="#ffb3a7" opacity=".38"/>
      <ellipse cx="272" cy="256" rx="30" ry="18" fill="#ffb3a7" opacity=".38"/>
      <ellipse cx="200" cy="88" rx="136" ry="70" fill="#c8956c"/>
      <ellipse cx="88" cy="168" rx="27" ry="70" fill="#c8956c"/>
      <ellipse cx="312" cy="168" rx="27" ry="70" fill="#c8956c"/>
      <ellipse cx="144" cy="80" rx="54" ry="42" fill="#c8956c"/>
      <ellipse cx="256" cy="80" rx="54" ry="42" fill="#c8956c"/>
      <g class="eyes">
        <ellipse cx="152" cy="178" rx="31" ry="27" fill="white"/>
        <circle cx="152" cy="180" r="18" fill="#5b8dd9"/>
        <circle cx="152" cy="180" r="10" fill="#1a1a2e"/>
        <circle cx="158" cy="173" r="5.5" fill="white"/>
        <circle cx="145" cy="184" r="2.5" fill="white" opacity=".6"/>
        <path d="M120 162 Q152 148 184 162" stroke="#a0522d" stroke-width="5" fill="none" stroke-linecap="round"/>
        <ellipse cx="248" cy="178" rx="31" ry="27" fill="white"/>
        <circle cx="248" cy="180" r="18" fill="#5b8dd9"/>
        <circle cx="248" cy="180" r="10" fill="#1a1a2e"/>
        <circle cx="254" cy="173" r="5.5" fill="white"/>
        <circle cx="241" cy="184" r="2.5" fill="white" opacity=".6"/>
        <path d="M216 162 Q248 148 280 162" stroke="#a0522d" stroke-width="5" fill="none" stroke-linecap="round"/>
      </g>
      <ellipse cx="200" cy="234" rx="9" ry="6" fill="#e8a87c" opacity=".45"/>
      <g class="mouth" id="mouth">
        <path d="M 165 292 Q 200 300 235 292 Q 200 316 165 292 Z" fill="#e05c6a"/>
        <path d="M 165 292 Q 200 286 235 292" fill="#f28b82"/>
        <path d="M 174 293 Q 200 306 226 293" stroke="#c0404e" stroke-width="1.5" fill="none"/>
      </g>
    </svg>
  </div>
  <div class="dots"><span></span><span></span><span></span></div>
  <div class="lbl" id="lbl">{label}</div>
</div>
<script>
const mouth=document.getElementById('mouth'),lbl=document.getElementById('lbl');
function speak(){{mouth.classList.add('on');lbl.textContent='Speaking...';lbl.className='lbl s'}}
function idle(){{mouth.classList.remove('on');lbl.textContent='Ready';lbl.className='lbl'}}
{chain_js}
</script></body></html>"""
