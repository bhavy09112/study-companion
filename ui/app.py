"""Streamlit frontend for Study Companion AI.

Tabs: Study, Quiz, Flashcards, Progress, Settings.
Sidebar: document uploader, indexed sources, topic filter.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests
import streamlit as st

# API configuration
API_URL = "http://localhost:8000"

# ── Page Config ─────────────────────────────────────────

st.set_page_config(
    page_title="Study Companion AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session State Init ──────────────────────────────────

if "api_url" not in st.session_state:
    st.session_state.api_url = API_URL
if "top_k" not in st.session_state:
    st.session_state.top_k = 5
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7
if "quiz_session" not in st.session_state:
    st.session_state.quiz_session = None
if "flashcard_index" not in st.session_state:
    st.session_state.flashcard_index = 0
if "show_answer" not in st.session_state:
    st.session_state.show_answer = False


def api_call(method: str, endpoint: str, **kwargs) -> dict | None:
    """Make an API call with error handling."""
    url = f"{st.session_state.api_url}{endpoint}"
    try:
        resp = getattr(requests, method)(url, timeout=120, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure the server is running: `uvicorn api.main:app --port 8000`")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.status_code} — {e.response.text[:200]}")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


# ── Sidebar ─────────────────────────────────────────────

with st.sidebar:
    st.title("📚 Study Companion")
    st.caption("Local-first AI study assistant")

    st.divider()

    # Document uploader
    st.subheader("📄 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload study materials",
        type=["pdf", "docx", "txt", "md", "png", "jpg"],
        accept_multiple_files=True,
        key="file_uploader",
    )

    url_input = st.text_input("Or paste a URL:", placeholder="https://...")

    if st.button("📥 Ingest", type="primary", use_container_width=True):
        if uploaded_files or url_input:
            with st.spinner("Processing documents..."):
                files = []
                for f in uploaded_files:
                    files.append(("files", (f.name, f.getvalue(), f.type or "application/octet-stream")))

                params = {}
                if url_input:
                    params["urls"] = url_input

                result = api_call("post", "/ingest", files=files if files else None, params=params)
                if result:
                    st.success(f"Added {result['chunks_added']} chunks from {len(result['sources'])} sources")
        else:
            st.warning("Upload files or enter a URL first")

    st.divider()

    # Health status
    st.subheader("🔧 System Status")
    health = api_call("get", "/health")
    if health:
        col1, col2 = st.columns(2)
        with col1:
            status_emoji = "🟢" if health["model_loaded"] else "🔴"
            st.metric("Model", f"{status_emoji} {'Ready' if health['model_loaded'] else 'Down'}")
        with col2:
            st.metric("Index", f"{health['index_size']} chunks")

        st.caption(f"Model: {health.get('model_name', 'N/A')} | Cards: {health['db_cards']}")


# ── Main Tabs ───────────────────────────────────────────

tab_study, tab_quiz, tab_flashcards, tab_progress, tab_settings = st.tabs(
    ["📖 Study", "📝 Quiz", "🃏 Flashcards", "📊 Progress", "⚙️ Settings"]
)


# ── Study Tab ───────────────────────────────────────────

with tab_study:
    st.header("Study a Topic")

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input(
            "What do you want to study?",
            placeholder="e.g., photosynthesis, Newton's laws, SQL joins...",
            key="study_topic",
        )
    with col2:
        mode = st.selectbox(
            "Output mode",
            [
                "simple_explanation",
                "key_concepts",
                "exam_critical",
                "detailed_explanation",
                "common_mistakes",
                "practice_questions",
                "revision_sheet",
                "mnemonics",
                "concept_map",
            ],
            format_func=lambda x: x.replace("_", " ").title(),
            key="study_mode",
        )

    if st.button("🔍 Generate", type="primary", disabled=not topic):
        with st.spinner("Generating study material..."):
            result = api_call("post", "/generate", json={
                "topic": topic,
                "mode": mode,
                "top_k": st.session_state.top_k,
                "temperature": st.session_state.temperature,
            })

        if result:
            # Warnings
            if result.get("uncertain"):
                st.warning("⚠ Topic may not be well-covered by your uploaded materials.")
            for w in result.get("warnings", []):
                st.info(w)

            # Output
            st.markdown(result["output"])

            # Sources
            if result.get("sources"):
                with st.expander("📚 Sources"):
                    for src in result["sources"]:
                        st.caption(f"• {src['source']} (p. {src['page']}, score: {src['score']:.2f})")

    # [BONUS FEATURE] Quick mode buttons for rapid switching
    st.divider()
    st.caption("Quick modes:")
    quick_cols = st.columns(5)
    quick_modes = [
        ("📖 Simple", "simple_explanation"),
        ("🔑 Key Points", "key_concepts"),
        ("⚡ Exam", "exam_critical"),
        ("🧠 Mnemonics", "mnemonics"),
        ("🗺️ Map", "concept_map"),
    ]
    for col, (label, qmode) in zip(quick_cols, quick_modes):
        with col:
            if st.button(label, use_container_width=True, key=f"quick_{qmode}"):
                if topic:
                    st.session_state.study_mode = qmode
                    st.rerun()


# ── Quiz Tab ────────────────────────────────────────────

with tab_quiz:
    st.header("Quiz Mode")

    if st.session_state.quiz_session is None:
        # Start new quiz
        quiz_topic = st.text_input("Quiz topics (comma-separated):", placeholder="photosynthesis, cellular respiration")
        col1, col2 = st.columns(2)
        with col1:
            n_questions = st.slider("Number of questions", 1, 20, 5)
        with col2:
            time_limit = st.slider("Time limit (seconds)", 60, 600, 300, step=30)

        if st.button("🚀 Start Quiz", type="primary", disabled=not quiz_topic):
            topics = [t.strip() for t in quiz_topic.split(",") if t.strip()]
            with st.spinner("Generating quiz..."):
                result = api_call("post", "/quiz/start", json={
                    "topics": topics,
                    "n_questions": n_questions,
                    "time_limit_seconds": time_limit,
                })
            if result:
                st.session_state.quiz_session = result
                st.session_state.quiz_answers = {}
                st.rerun()
    else:
        # Active quiz
        session = st.session_state.quiz_session
        st.info(f"⏱️ Time limit: {session['time_limit_seconds']}s | Questions: {len(session['questions'])}")

        for i, q in enumerate(session["questions"]):
            st.subheader(f"Q{i+1}: {q['text']}")
            if q.get("options"):
                answer = st.radio(
                    "Select your answer:",
                    q["options"],
                    key=f"quiz_q_{q['id']}",
                    index=None,
                )
                if answer:
                    st.session_state.quiz_answers[q["id"]] = answer
            else:
                answer = st.text_input("Your answer:", key=f"quiz_q_{q['id']}")
                if answer:
                    st.session_state.quiz_answers[q["id"]] = answer

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Submit Quiz", type="primary"):
                answers = [
                    {"question_id": qid, "answer": ans}
                    for qid, ans in st.session_state.quiz_answers.items()
                ]
                result = api_call("post", "/quiz/submit", json={
                    "session_id": session["session_id"],
                    "answers": answers,
                })
                if result:
                    st.success(f"Score: {result['score']*100:.0f}%")
                    if result.get("weak_topics"):
                        st.warning(f"Weak topics: {', '.join(result['weak_topics'])}")
                    st.session_state.quiz_session = None
        with col2:
            if st.button("🔄 New Quiz"):
                st.session_state.quiz_session = None
                st.rerun()


# ── Flashcards Tab ──────────────────────────────────────

with tab_flashcards:
    st.header("Flashcard Review (Spaced Repetition)")

    result = api_call("get", "/flashcards/due")
    if result and result["count"] > 0:
        cards = result["cards"]
        idx = st.session_state.flashcard_index % len(cards)
        card = cards[idx]

        st.metric("Due cards", result["count"])
        st.divider()

        # Card display
        st.subheader(f"Card {idx + 1} / {len(cards)}")
        if card.get("topic"):
            st.caption(f"Topic: {card['topic']}")

        st.markdown(f"### {card['front']}")

        if st.session_state.show_answer:
            st.markdown(f"**Answer:** {card['back']}")

            # Rating buttons
            st.caption("How well did you remember? (0 = forgot, 5 = perfect)")
            rating_cols = st.columns(6)
            for i, col in enumerate(rating_cols):
                labels = ["🚫 0", "😰 1", "😕 2", "🤔 3", "😊 4", "🌟 5"]
                with col:
                    if st.button(labels[i], key=f"rate_{i}", use_container_width=True):
                        api_call("post", "/flashcards/review", json={
                            "card_id": card["id"],
                            "quality": i,
                        })
                        st.session_state.flashcard_index += 1
                        st.session_state.show_answer = False
                        st.rerun()
        else:
            if st.button("👁️ Show Answer", type="primary", use_container_width=True):
                st.session_state.show_answer = True
                st.rerun()
    else:
        st.info("🎉 No cards due for review! Upload some documents and generate study materials to create flashcards.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export to Anki"):
            try:
                resp = requests.get(f"{st.session_state.api_url}/export/anki", timeout=30)
                if resp.status_code == 200:
                    st.download_button(
                        "⬇️ Download .apkg",
                        data=resp.content,
                        file_name="study_companion.apkg",
                        mime="application/octet-stream",
                    )
                else:
                    st.warning("No cards to export yet.")
            except Exception as e:
                st.error(f"Export failed: {e}")


# ── Progress Tab ────────────────────────────────────────

with tab_progress:
    st.header("Study Progress")

    progress = api_call("get", "/progress")
    if progress:
        # Overall mastery
        st.metric("Overall Mastery", f"{progress['overall_mastery']*100:.0f}%")
        st.metric("Total Flashcards", progress["total_cards"])

        st.divider()

        # Per-topic breakdown
        if progress["topics"]:
            st.subheader("Topic Breakdown")
            for topic in progress["topics"]:
                col1, col2, col3 = st.columns([2, 3, 1])
                with col1:
                    st.write(f"**{topic['name']}**")
                with col2:
                    st.progress(min(topic["mastery_score"], 1.0))
                with col3:
                    st.write(f"{topic['mastery_score']*100:.0f}%")
        else:
            st.info("No topics tracked yet. Start studying to see progress!")

        # [BONUS FEATURE] Study streak tracker
        st.divider()
        st.subheader("📅 Study Streak")
        st.caption("Keep studying daily to build your streak!")
        # Simple visual streak using the current date
        import datetime
        today = datetime.date.today()
        cols = st.columns(7)
        for i, col in enumerate(cols):
            day = today - datetime.timedelta(days=6 - i)
            with col:
                is_today = day == today
                st.markdown(
                    f"**{'📗' if is_today else '📕'}** {day.strftime('%a')}"
                )


# ── Settings Tab ────────────────────────────────────────

with tab_settings:
    st.header("Settings")

    st.subheader("API Configuration")
    st.session_state.api_url = st.text_input("API URL", value=st.session_state.api_url)

    st.divider()

    st.subheader("Generation Settings")
    st.session_state.top_k = st.slider(
        "Top-K chunks for retrieval", 1, 20, st.session_state.top_k,
        help="Number of context chunks to retrieve from your documents",
    )
    st.session_state.temperature = st.slider(
        "Temperature", 0.0, 2.0, st.session_state.temperature, 0.1,
        help="Higher = more creative, Lower = more focused",
    )

    st.divider()

    st.subheader("Model Info")
    health = api_call("get", "/health")
    if health:
        st.json(health)

    st.divider()

    st.subheader("About")
    st.markdown("""
    **Study Companion AI** v1.0.0

    A local-first, RAG-augmented study assistant with:
    - Multi-format document ingestion
    - Hybrid retrieval (dense + sparse)
    - Domain-aware output formatting
    - SM-2 spaced repetition
    - Anki export

    Built with Mistral-7B + Ollama + FAISS + FastAPI + Streamlit.
    """)
