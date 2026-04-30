"""Declares the video player custom component as an importable module."""
import pathlib
import streamlit.components.v1 as components

_dir = pathlib.Path(__file__).parent / "video_player_component"
video_player = components.declare_component("video_player", path=str(_dir))
