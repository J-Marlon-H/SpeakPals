"""Declares the minimal STT mic component as an importable module."""
import pathlib
import streamlit.components.v1 as components

_dir = pathlib.Path(__file__).parent / "stt_component"
stt_mic = components.declare_component("stt_mic", path=str(_dir))
