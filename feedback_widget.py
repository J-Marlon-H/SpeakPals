"""Floating feedback button — self-contained custom component.

The component injects its button + panel directly into window.parent.document.body
so it is truly viewport-fixed regardless of Streamlit's container transforms or
overflow settings.  All show/hide is pure JS (no Streamlit reruns for toggle /
cancel = no grey flash).  Only the Send action triggers one rerun to save the text.

Usage (once per page, after main content):
    from feedback_widget import render_feedback_widget
    render_feedback_widget()
"""
import streamlit as st
from feedback_helper import fb_widget


def render_feedback_widget() -> None:
    """Render the invisible component container + handle submission."""
    result = fb_widget(key="_fb_comp", default=None)

    if not (result and isinstance(result, dict) and result.get("action") == "feedback"):
        return

    text = result.get("text", "").strip()
    if not text:
        return

    # Deduplicate — Streamlit holds the last component value across reruns
    if st.session_state.get("_fb_last_saved") == text:
        return

    st.session_state["_fb_last_saved"] = text
    _persist(text)


def _persist(text: str) -> None:
    if "sb_user_id" not in st.session_state:
        return
    try:
        from db import save_feedback
        save_feedback(
            st.session_state.sb_user_id,
            st.session_state.sb_access_token,
            text,
        )
    except Exception:
        pass
