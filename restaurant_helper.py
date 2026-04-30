"""Declares the unified restaurant video+mic component."""
import pathlib
import streamlit.components.v1 as components

_dir = pathlib.Path(__file__).parent / "restaurant_component"
restaurant_player = components.declare_component("restaurant_player", path=str(_dir))
