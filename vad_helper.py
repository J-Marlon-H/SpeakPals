"""Declares the VAD custom component once as a regular importable module.

components.declare_component() uses inspect.getmodule() to find the calling
module in sys.modules. When a page is run via st.navigation pg.run(), the
script is exec'd in a temporary module that is never registered in sys.modules,
causing inspect.getmodule() to return None and raising a RuntimeError.
Declaring the component here (a normal import) avoids that issue entirely.
"""
import pathlib
import streamlit.components.v1 as components

_vad_dir = pathlib.Path(__file__).parent / "vad_component"
mic = components.declare_component("vad_mic", path=str(_vad_dir))
