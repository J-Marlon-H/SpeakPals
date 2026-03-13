import pathlib, base64
import streamlit as st
from pipeline import SCENE_CATALOG


@st.cache_resource
def img_b64(filename: str) -> str | None:
    path = pathlib.Path(__file__).parent / "assets" / "scenes" / filename
    if not path.exists():
        return None
    data = path.read_bytes()
    mime = "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def preload_all_images() -> None:
    """Warm the @st.cache_resource cache for all scene images."""
    for s in SCENE_CATALOG:
        img_b64(s["file"])
