"""Summaries page – Generate topic-based or page-range summaries."""

import streamlit as st

import api_client

# ── Load documents for selectors ────────────────────────
doc_data = api_client.list_documents(status="ready", limit=100)
all_docs = doc_data.get("documents", []) if isinstance(doc_data, dict) else doc_data
doc_options = {"": "(none – topic-only search)"} | {
    str(d["id"]): d["original_filename"] for d in all_docs
}

# ── Form ────────────────────────────────────────────────
st.subheader("Generate a Summary")

with st.form("summary_form"):
    topic = st.text_input(
        "Topic",
        placeholder="e.g. Photosynthesis, Chapter 3, Sorting algorithms...",
    )

    selected_doc = st.selectbox(
        "Document (optional)",
        options=list(doc_options.keys()),
        format_func=lambda x: doc_options[x],
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        detail_level = st.selectbox("Detail level", ["brief", "standard", "detailed"])
    with col2:
        page_start = st.number_input(
            "Start page (optional)", min_value=0, value=0, step=1
        )
    with col3:
        page_end = st.number_input("End page (optional)", min_value=0, value=0, step=1)

    generate = st.form_submit_button("Generate summary", type="primary")

# ── Generate ────────────────────────────────────────────
if generate:
    if not topic and not selected_doc:
        st.warning("Provide a topic, a document, or both.")
        st.stop()

    with st.spinner("Generating summary... this may take a moment."):
        result = api_client.generate_summary(
            topic=topic or None,
            document_id=selected_doc or None,
            page_start=page_start if page_start > 0 else None,
            page_end=page_end if page_end > 0 else None,
            detail_level=detail_level,
        )

    # Store result in session for persistence across reruns
    st.session_state["last_summary"] = result

# ── Display result ──────────────────────────────────────
result = st.session_state.get("last_summary")
if result:
    st.divider()
    st.subheader(f"Summary: {result.get('topic', 'N/A')}")
    st.markdown(result.get("summary", ""))

    sources = result.get("sources", [])
    if sources:
        with st.expander(f"Sources ({len(sources)})"):
            for src in sources:
                st.markdown(
                    f"**{src.get('document_name', '?')}** – pages {src.get('pages', '?')}"
                )

    model = result.get("model")
    if model:
        st.caption(f"Model: {model}")
