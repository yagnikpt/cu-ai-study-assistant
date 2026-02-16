"""HTTP client for the FastAPI backend.

Thin wrapper around httpx that all Streamlit pages use to talk to the API.
"""

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"
TIMEOUT = 120.0  # generous timeout for LLM calls


def _url(path: str) -> str:
    return f"{API_BASE}/api/v1{path}"


def _handle(resp: httpx.Response) -> dict | list:
    """Raise a user-friendly error or return JSON."""
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        st.error(f"API error ({resp.status_code}): {detail}")
        st.stop()
    return resp.json()


# ── Health ──────────────────────────────────────────────


def health() -> dict:
    resp = httpx.get(f"{API_BASE}/health", timeout=10)
    return resp.json()


# ── Documents ───────────────────────────────────────────


def upload_document(
    file_bytes: bytes,
    filename: str,
    course_name: str | None = None,
    subject: str | None = None,
) -> dict:
    params: dict[str, str] = {}
    if course_name:
        params["course_name"] = course_name
    if subject:
        params["subject"] = subject
    resp = httpx.post(
        _url("/documents/"),
        files={"file": (filename, file_bytes, "application/pdf")},
        params=params,
        timeout=TIMEOUT,
    )
    return _handle(resp)


def list_documents(**filters: str | int | None) -> dict:
    params = {k: v for k, v in filters.items() if v is not None}
    resp = httpx.get(_url("/documents/"), params=params, timeout=TIMEOUT)
    return _handle(resp)


def get_document(doc_id: str) -> dict:
    resp = httpx.get(_url(f"/documents/{doc_id}"), timeout=TIMEOUT)
    return _handle(resp)


def delete_document(doc_id: str) -> None:
    resp = httpx.delete(_url(f"/documents/{doc_id}"), timeout=TIMEOUT)
    if resp.status_code >= 400:
        _handle(resp)


def get_chunks(doc_id: str, offset: int = 0, limit: int = 20) -> list:
    resp = httpx.get(
        _url(f"/documents/{doc_id}/chunks"),
        params={"offset": offset, "limit": limit},
        timeout=TIMEOUT,
    )
    return _handle(resp)


# ── Tags ────────────────────────────────────────────────


def list_tags() -> list:
    resp = httpx.get(_url("/tags/"), timeout=TIMEOUT)
    return _handle(resp)


def create_tag(name: str, color: str | None = None) -> dict:
    body: dict = {"name": name}
    if color:
        body["color"] = color
    resp = httpx.post(_url("/tags/"), json=body, timeout=TIMEOUT)
    return _handle(resp)


def add_tags_to_document(doc_id: str, tag_ids: list[str]) -> dict:
    resp = httpx.post(
        _url(f"/documents/{doc_id}/tags"),
        json={"tag_ids": tag_ids},
        timeout=TIMEOUT,
    )
    return _handle(resp)


# ── Q&A ─────────────────────────────────────────────────


def ask_question(
    question: str,
    document_ids: list[str] | None = None,
    top_k: int = 5,
) -> dict:
    body: dict = {"question": question, "top_k": top_k}
    if document_ids:
        body["document_ids"] = document_ids
    resp = httpx.post(_url("/qa/ask"), json=body, timeout=TIMEOUT)
    return _handle(resp)


def semantic_search(
    query: str,
    document_ids: list[str] | None = None,
    top_k: int = 10,
) -> dict:
    body: dict = {"query": query, "top_k": top_k}
    if document_ids:
        body["document_ids"] = document_ids
    resp = httpx.post(_url("/qa/search"), json=body, timeout=TIMEOUT)
    return _handle(resp)


# ── Summaries ───────────────────────────────────────────


def generate_summary(
    topic: str | None = None,
    document_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    detail_level: str = "standard",
) -> dict:
    body: dict = {"detail_level": detail_level}
    if topic:
        body["topic"] = topic
    if document_id:
        body["document_id"] = document_id
    if page_start is not None:
        body["page_start"] = page_start
    if page_end is not None:
        body["page_end"] = page_end
    resp = httpx.post(_url("/summaries/generate"), json=body, timeout=TIMEOUT)
    return _handle(resp)


# ── Quizzes ─────────────────────────────────────────────


def generate_quiz(
    document_id: str | None = None,
    topic: str | None = None,
    question_count: int = 5,
    question_types: list[str] | None = None,
) -> dict:
    body: dict = {"question_count": question_count}
    if document_id:
        body["document_id"] = document_id
    if topic:
        body["topic"] = topic
    if question_types:
        body["question_types"] = question_types
    resp = httpx.post(_url("/quizzes/generate"), json=body, timeout=TIMEOUT)
    return _handle(resp)


def list_quizzes(document_id: str | None = None) -> dict:
    params: dict = {}
    if document_id:
        params["document_id"] = document_id
    resp = httpx.get(_url("/quizzes/"), params=params, timeout=TIMEOUT)
    return _handle(resp)


def get_quiz(quiz_id: str) -> dict:
    resp = httpx.get(_url(f"/quizzes/{quiz_id}"), timeout=TIMEOUT)
    return _handle(resp)


def submit_attempt(quiz_id: str, answers: list[dict]) -> dict:
    resp = httpx.post(
        _url(f"/quizzes/{quiz_id}/attempt"),
        json={"answers": answers},
        timeout=TIMEOUT,
    )
    return _handle(resp)


def get_quiz_results(quiz_id: str) -> dict:
    resp = httpx.get(_url(f"/quizzes/{quiz_id}/results"), timeout=TIMEOUT)
    return _handle(resp)
