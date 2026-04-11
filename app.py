# SpeakPals — entry point
# Streamlit Cloud is configured to run this file.
# All page routing is defined here; each page is exec'd by pg.run().
import streamlit as st
from scene_images import preload_all_images

# Warm the image cache on first server start so home page loads instantly
preload_all_images()

pages = [
    st.Page("pages/home.py",         title="Home",         default=True),
    st.Page("pages/login.py",        title="Login",        visibility="hidden"),
    st.Page("pages/account.py",      title="Account",      visibility="hidden"),
    st.Page("pages/scene_select.py", title="Scene Select", visibility="hidden"),
    st.Page("pages/lesson.py",       title="Lesson",       visibility="hidden"),
    st.Page("pages/feedback.py",     title="Feedback",     visibility="hidden"),
]
pg = st.navigation(pages, position="hidden")
pg.run()
