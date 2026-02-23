"""Q&A page – Chat-style RAG question answering with source citations."""

import streamlit as st

import api_client

# ── State ───────────────────────────────────────────────
st.session_state.setdefault("messages", [])

# ── Sidebar: scope selection ────────────────────────────
with st.sidebar:
    st.subheader("Q&A Settings")
    # Load documents for scope selector
    doc_data = api_client.list_documents(status="ready", limit=100)
    all_docs = doc_data.get("documents", []) if isinstance(doc_data, dict) else doc_data

    doc_options = {str(d["id"]): d["original_filename"] for d in all_docs}

    selected_ids = st.multiselect(
        "Limit to documents",
        options=list(doc_options.keys()),
        format_func=lambda x: doc_options[x],
        help="Leave empty to search all documents",
    )

    top_k = st.slider("Sources to retrieve", min_value=1, max_value=20, value=5)

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Chat history ────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"Sources ({len(msg['sources'])})"):
                for src in msg["sources"]:
                    pg = f"p.{src['page_start']}"
                    if src["page_end"] != src["page_start"]:
                        pg += f"-{src['page_end']}"
                    doc_name = src.get("document_name", "Unknown")
                    section = src.get("section_title") or ""
                    score = src.get("relevance_score", 0)
                    st.markdown(
                        f"**{doc_name}** ({pg}) "
                        f"{'– ' + section + ' ' if section else ''}"
                        f"*relevance: {score:.2f}*"
                    )
                    if src.get("text_preview"):
                        st.caption(src["text_preview"][:300])
                    st.divider()

# ── Chat input ──────────────────────────────────────────
if prompt := st.chat_input("Ask a question about your documents..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get answer
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = api_client.ask_question(
                question=prompt,
                document_ids=selected_ids or None,
                top_k=top_k,
            )

        answer = result.get("answer", "No answer returned.")
        sources = result.get("sources", [])
        model = result.get("model", "")

        st.markdown(answer)

        if sources:
            with st.expander(f"Sources ({len(sources)})"):
                for src in sources:
                    pg = f"p.{src['page_start']}"
                    if src["page_end"] != src["page_start"]:
                        pg += f"-{src['page_end']}"
                    doc_name = src.get("document_name", "Unknown")
                    section = src.get("section_title") or ""
                    score = src.get("relevance_score", 0)
                    st.markdown(
                        f"**{doc_name}** ({pg}) "
                        f"{'– ' + section + ' ' if section else ''}"
                        f"*relevance: {score:.2f}*"
                    )
                    if src.get("text_preview"):
                        st.caption(src["text_preview"][:300])
                    st.divider()

        if model:
            st.caption(f"Model: {model}")

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
