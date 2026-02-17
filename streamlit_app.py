"""CU Study Assistant – Streamlit entry point.

Run with: uv run streamlit run streamlit_app.py
"""

import streamlit as st

st.set_page_config(
    page_title="CU Study Assistant",
    page_icon=":material/school:",
    layout="wide",
)

# ── Global state ────────────────────────────────────────
st.session_state.setdefault("messages", [])
st.session_state.setdefault("documents_cache", None)

# ── Navigation ──────────────────────────────────────────
page = st.navigation(
    [
        st.Page(
            "app_pages/documents.py", title="Documents", icon=":material/description:"
        ),
        st.Page("app_pages/qa.py", title="Q&A", icon=":material/forum:"),
        st.Page(
            "app_pages/summaries.py", title="Summaries", icon=":material/summarize:"
        ),
        st.Page("app_pages/quizzes.py", title="Quizzes", icon=":material/quiz:"),
    ],
    position="sidebar",
)

# ── Shared sidebar ──────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    # Backend health indicator
    try:
        import api_client

        h = api_client.health()
        db_ok = h.get("database") == "connected"
        gemini_ok = h.get("gemini_configured") is True
        if db_ok and gemini_ok:
            st.success("Backend: connected", icon=":material/check_circle:")
        else:
            parts = []
            if not db_ok:
                parts.append("DB")
            if not gemini_ok:
                parts.append("Gemini")
            st.warning(
                f"Backend: {', '.join(parts)} unhealthy", icon=":material/warning:"
            )
    except Exception:
        st.error("Backend: unreachable", icon=":material/error:")

# ── Title ───────────────────────────────────────────────
st.title(f"{page.title}")

page.run()
