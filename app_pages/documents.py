"""Documents page – Upload, list, inspect, and tag PDF documents."""

import streamlit as st

import api_client

# ── Upload section ──────────────────────────────────────
st.subheader("Upload a PDF")

with st.form("upload_form", clear_on_submit=True):
    uploaded = st.file_uploader("Choose a PDF file", type=["pdf"])
    col1, col2 = st.columns(2)
    with col1:
        course = st.text_input("Course name (optional)")
    with col2:
        subject = st.text_input("Subject (optional)")
    submitted = st.form_submit_button("Upload", type="primary")

if submitted and uploaded is not None:
    with st.spinner("Uploading and processing..."):
        result = api_client.upload_document(
            file_bytes=uploaded.getvalue(),
            filename=uploaded.name,
            course_name=course or None,
            subject=subject or None,
        )
    st.success(
        f"Uploaded **{result['original_filename']}** (status: {result['status']})"
    )
    st.session_state.documents_cache = None  # bust cache

# ── Document list ───────────────────────────────────────
st.subheader("Your Documents")

# Filters
with st.expander("Filters", icon=":material/filter_list:"):
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        f_course = st.text_input("Filter by course", key="doc_filter_course")
    with fc2:
        f_subject = st.text_input("Filter by subject", key="doc_filter_subject")
    with fc3:
        f_status = st.selectbox(
            "Status",
            ["all", "processing", "ready", "failed"],
            key="doc_filter_status",
        )

filters: dict[str, str | int] = {}
if f_course:
    filters["course_name"] = f_course
if f_subject:
    filters["subject"] = f_subject
if f_status != "all":
    filters["status"] = f_status

data = api_client.list_documents(**filters)
docs = data.get("documents", []) if isinstance(data, dict) else data
total = data.get("total", len(docs)) if isinstance(data, dict) else len(docs)

st.caption(f"Showing {len(docs)} of {total} documents")

if not docs:
    st.info("No documents yet. Upload a PDF above to get started.")
else:
    for doc in docs:
        status_icon = {
            "ready": ":material/check_circle:",
            "processing": ":material/sync:",
            "failed": ":material/error:",
        }.get(doc["status"], ":material/help:")

        with st.expander(f"{status_icon} {doc['original_filename']}", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.metric("Pages", doc.get("page_count", "?"))
            c2.metric("Chunks", doc.get("chunk_count", 0))
            size_kb = doc.get("file_size_bytes", 0) / 1024
            c3.metric("Size", f"{size_kb:.1f} KB")

            st.text(f"Status: {doc['status']}")
            if doc.get("course_name"):
                st.text(f"Course: {doc['course_name']}")
            if doc.get("subject"):
                st.text(f"Subject: {doc['subject']}")
            if doc.get("error_message"):
                st.error(doc["error_message"])

            # Tags
            tags = doc.get("tags", [])
            if tags:
                tag_labels = [f":blue-background[{t['name']}]" for t in tags]
                st.markdown("Tags: " + "  ".join(tag_labels))

            # Actions
            btn_col1, btn_col2 = st.columns(2)
            doc_id = str(doc["id"])

            with btn_col1:
                if st.button("View chunks", key=f"chunks_{doc_id}"):
                    st.session_state[f"show_chunks_{doc_id}"] = True

            with btn_col2:
                if st.button("Delete", key=f"del_{doc_id}", type="secondary"):
                    api_client.delete_document(doc_id)
                    st.session_state.documents_cache = None
                    st.rerun()

            # Show chunks if requested
            if st.session_state.get(f"show_chunks_{doc_id}"):
                chunks = api_client.get_chunks(doc_id)
                if not chunks:
                    st.info("No chunks available (document may still be processing).")
                else:
                    for chunk in chunks:
                        pg = f"p.{chunk['page_start']}"
                        if chunk["page_end"] != chunk["page_start"]:
                            pg += f"-{chunk['page_end']}"
                        title = chunk.get("section_title") or ""
                        header = f"Chunk {chunk['chunk_index']} ({pg})"
                        if title:
                            header += f" – {title}"
                        st.markdown(f"**{header}**")
                        st.text(
                            chunk["content"][:500]
                            + ("..." if len(chunk["content"]) > 500 else "")
                        )
                        st.divider()

# ── Tag management ──────────────────────────────────────
st.subheader("Tags")

col_tags, col_create = st.columns([2, 1])

with col_create:
    with st.form("create_tag", clear_on_submit=True):
        tag_name = st.text_input("New tag name")
        tag_color = st.color_picker("Color", value="#4A90D9")
        if st.form_submit_button("Create tag"):
            if tag_name:
                api_client.create_tag(tag_name, tag_color)
                st.rerun()

with col_tags:
    tags = api_client.list_tags()
    if tags:
        for tag in tags:
            color = tag.get("color") or "#888"
            st.markdown(
                f'<span style="background:{color};color:white;padding:2px 10px;'
                f'border-radius:12px;font-size:0.85em;">{tag["name"]}</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No tags yet.")
