import streamlit as st

pages = [
    st.Page("pages/home.py",        title="Home",         default=True),
    st.Page("pages/login.py",       title="Login",        visibility="hidden"),
    st.Page("pages/account.py",     title="Account",      visibility="hidden"),
    st.Page("pages/scene_select.py",title="Scene Select", visibility="hidden"),
    st.Page("app.py",               title="Lesson",       visibility="hidden"),
    st.Page("pages/feedback.py",    title="Feedback",     visibility="hidden"),
]

pg = st.navigation(pages, position="hidden")
pg.run()
