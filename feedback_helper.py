"""Declares the feedback custom component once as a normal importable module.
Same pattern as vad_helper.py — avoids the inspect.getmodule() RuntimeError
when pages are exec'd via st.navigation pg.run()."""
import pathlib
import streamlit.components.v1 as components

_fb_dir = pathlib.Path(__file__).parent / "feedback_component"
fb_widget = components.declare_component("feedback_widget", path=str(_fb_dir))
