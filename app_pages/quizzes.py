"""Quizzes page – Generate, take, and review graded quizzes."""

import streamlit as st

import api_client

# ── State ───────────────────────────────────────────────
st.session_state.setdefault("quiz_view", "list")  # list | take | results
st.session_state.setdefault("active_quiz", None)
st.session_state.setdefault("attempt_result", None)

# ── Helper ──────────────────────────────────────────────


def go_to(view: str, quiz: dict | None = None) -> None:
    st.session_state.quiz_view = view
    if quiz is not None:
        st.session_state.active_quiz = quiz
    if view != "results":
        st.session_state.attempt_result = None


# ── Generate quiz section ──────────────────────────────
with st.expander("Generate a new quiz", icon=":material/add:", expanded=False):
    doc_data = api_client.list_documents(status="ready", limit=100)
    all_docs = doc_data.get("documents", []) if isinstance(doc_data, dict) else doc_data
    doc_options = {"": "(all documents)"} | {
        str(d["id"]): d["original_filename"] for d in all_docs
    }

    with st.form("quiz_generate"):
        gen_doc = st.selectbox(
            "Document",
            options=list(doc_options.keys()),
            format_func=lambda x: doc_options[x],
        )
        gen_topic = st.text_input("Topic (optional)")
        gc1, gc2 = st.columns(2)
        with gc1:
            gen_count = st.slider("Number of questions", 1, 20, 5)
        with gc2:
            gen_types = st.multiselect(
                "Question types",
                ["mcq", "short_answer"],
                default=["mcq"],
            )
        if st.form_submit_button("Generate quiz", type="primary"):
            with st.spinner("Generating quiz..."):
                quiz = api_client.generate_quiz(
                    document_id=gen_doc or None,
                    topic=gen_topic or None,
                    question_count=gen_count,
                    question_types=gen_types or None,
                )
            st.success(f"Quiz created: **{quiz.get('title', 'Untitled')}**")
            go_to("take", quiz)
            st.rerun()

# ── View router ─────────────────────────────────────────
view = st.session_state.quiz_view

# ================================================================
#  LIST VIEW
# ================================================================
if view == "list":
    st.subheader("Your Quizzes")
    quiz_data = api_client.list_quizzes()
    quizzes = quiz_data.get("quizzes", []) if isinstance(quiz_data, dict) else quiz_data

    if not quizzes:
        st.info("No quizzes yet. Generate one above.")
    else:
        for q in quizzes:
            qid = str(q["id"])
            title = q.get("title", "Untitled")
            n = q.get("question_count", "?")
            topic = q.get("topic") or ""

            col_title, col_actions = st.columns([3, 1])
            with col_title:
                label = f"**{title}** – {n} questions"
                if topic:
                    label += f" ({topic})"
                st.markdown(label)
            with col_actions:
                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("Take", key=f"take_{qid}"):
                        full_quiz = api_client.get_quiz(qid)
                        go_to("take", full_quiz)
                        st.rerun()
                with bc2:
                    if st.button("Results", key=f"res_{qid}"):
                        st.session_state["results_quiz_id"] = qid
                        go_to("results")
                        st.rerun()
            st.divider()

# ================================================================
#  TAKE QUIZ VIEW
# ================================================================
elif view == "take":
    quiz = st.session_state.active_quiz
    if not quiz:
        st.warning("No quiz selected.")
        go_to("list")
        st.rerun()

    st.subheader(quiz.get("title", "Quiz"))
    if quiz.get("topic"):
        st.caption(f"Topic: {quiz['topic']}")

    questions = quiz.get("questions", [])
    if not questions:
        st.warning("This quiz has no questions.")
        if st.button("Back to list"):
            go_to("list")
            st.rerun()
    else:
        with st.form("quiz_attempt"):
            answers: dict[str, str] = {}
            for i, q in enumerate(questions):
                qid = str(q["id"])
                q_type = q.get("question_type", "mcq")
                st.markdown(f"**Q{i + 1}.** {q['question_text']}")

                if q.get("source_pages"):
                    st.caption(f"Source: pages {q['source_pages']}")

                if q_type == "mcq" and q.get("options"):
                    opts = q["options"]
                    choice = st.radio(
                        f"Select answer for Q{i + 1}",
                        options=[o["label"] for o in opts],
                        format_func=lambda lbl, opts=opts: next(
                            f"{o['label']}. {o['text']}"
                            for o in opts
                            if o["label"] == lbl
                        ),
                        key=f"answer_{qid}",
                        label_visibility="collapsed",
                    )
                    answers[qid] = choice
                else:
                    # short_answer
                    ans = st.text_area(
                        f"Your answer for Q{i + 1}",
                        key=f"answer_{qid}",
                        label_visibility="collapsed",
                    )
                    answers[qid] = ans

                st.divider()

            sc1, sc2 = st.columns(2)
            with sc1:
                submitted = st.form_submit_button("Submit answers", type="primary")
            with sc2:
                back = st.form_submit_button("Back to list")

        if back:
            go_to("list")
            st.rerun()

        if submitted:
            answer_list = [
                {"question_id": qid, "answer": ans} for qid, ans in answers.items()
            ]
            with st.spinner("Grading..."):
                result = api_client.submit_attempt(str(quiz["id"]), answer_list)

            st.session_state.attempt_result = result
            st.session_state.quiz_view = "results"
            st.session_state["results_quiz_id"] = str(quiz["id"])
            st.rerun()

# ================================================================
#  RESULTS VIEW
# ================================================================
elif view == "results":
    attempt = st.session_state.attempt_result
    quiz_id = st.session_state.get("results_quiz_id")

    if attempt:
        # Show attempt feedback
        st.subheader("Quiz Results")

        total = attempt.get("total_questions", 0)
        correct = attempt.get("correct_count", 0)
        score = attempt.get("score_percentage", 0)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Score", f"{score:.0f}%")
        mc2.metric("Correct", f"{correct}/{total}")
        mc3.metric("Incorrect", f"{total - correct}")

        if score >= 80:
            st.success("Great job!")
        elif score >= 50:
            st.warning("Room for improvement.")
        else:
            st.error("You may want to review this material.")

        st.divider()

        for fb in attempt.get("feedback", []):
            icon = (
                ":material/check_circle:" if fb["is_correct"] else ":material/cancel:"
            )
            st.markdown(f"{icon} **{fb['question_text']}**")
            st.markdown(f"Your answer: `{fb['user_answer']}`")
            st.markdown(f"Correct answer: `{fb['correct_answer']}`")
            if fb.get("explanation"):
                st.info(fb["explanation"])
            if fb.get("feedback"):
                st.caption(fb["feedback"])
            if fb.get("source_pages"):
                st.caption(f"Source: pages {fb['source_pages']}")
            st.divider()

    elif quiz_id:
        # Show aggregated results
        st.subheader("Quiz Results")
        results = api_client.get_quiz_results(quiz_id)
        st.markdown(f"**{results.get('title', 'Quiz')}**")
        st.metric("Attempts", results.get("attempts_count", 0))
        st.metric("Best score", f"{results.get('best_score', 0):.0f}%")

        strengths = results.get("topic_strengths", [])
        if strengths:
            st.subheader("Topic Strengths")
            for ts in strengths:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{ts['topic']}**")
                    st.progress(ts["accuracy"])
                with col2:
                    st.metric(
                        "Accuracy",
                        f"{ts['accuracy'] * 100:.0f}%",
                        delta=None,
                    )
                    if ts.get("needs_reinforcement"):
                        st.caption(":material/warning: Needs review")

    else:
        st.info("No results to display.")

    if st.button("Back to quizzes"):
        go_to("list")
        st.rerun()
