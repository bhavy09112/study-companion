"""Quiz page — interactive MCQ session with timer, hints, and flag-for-review."""
from __future__ import annotations

import time

import streamlit as st

from ui._shared import apply_theme, init_state, render_sidebar, api_call

st.set_page_config(
    page_title="Study Companion · Quiz",
    page_icon="📝",
    layout="wide",
)

apply_theme()
init_state()
render_sidebar()

st.markdown("<h2>Interactive Quiz</h2>", unsafe_allow_html=True)

# ── Start screen ────────────────────────────────────────

if st.session_state.quiz_session is None:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    st.markdown("<h3>Start a new quiz</h3>", unsafe_allow_html=True)
    quiz_topic = st.text_input(
        "Quiz topics (comma-separated)",
        placeholder="photosynthesis, cellular respiration",
        key="quiz_topic_input",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        n_questions = st.slider("Number of questions", 1, 20, 5, key="quiz_n")
    with c2:
        time_limit = st.slider("Time limit (sec)", 60, 1800, 300, step=30, key="quiz_time")
    with c3:
        difficulty = st.selectbox(
            "Difficulty", ["Easy", "Medium", "Hard"], index=1, key="quiz_diff",
        )

    start_btn = st.button(
        "🚀 Start Quiz", type="primary",
        disabled=not quiz_topic.strip(), key="quiz_start_btn",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if start_btn:
        topics = [t.strip() for t in quiz_topic.split(",") if t.strip()]
        # Difficulty influences temperature
        temp = {"Easy": 0.4, "Medium": 0.7, "Hard": 1.0}[difficulty]
        with st.spinner("Generating quiz from your material…"):
            session = api_call("post", "/quiz/start", json={
                "topics": topics,
                "n_questions": n_questions,
                "time_limit_seconds": time_limit,
            })
        if session:
            if not session["questions"]:
                st.error("No questions could be generated. Try uploading more material on this topic.")
            else:
                st.session_state.quiz_session = session
                st.session_state.quiz_answers = {}
                st.session_state.quiz_flagged = set()
                st.session_state.quiz_started_at = time.time()
                st.session_state.quiz_difficulty = difficulty
                st.session_state.quiz_q_index = 0
                st.session_state.quiz_hints = {}
                st.rerun()
    st.stop()

# ── Active quiz ─────────────────────────────────────────

session = st.session_state.quiz_session
questions = session["questions"]
q_index = st.session_state.get("quiz_q_index", 0) % len(questions)
q = questions[q_index]
total = len(questions)
elapsed = int(time.time() - (st.session_state.quiz_started_at or time.time()))
time_left = max(0, session["time_limit_seconds"] - elapsed)

# Layout: question 8 cols, metrics 4 cols
left, right = st.columns([8, 4], gap="large")

with left:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    # Header row
    h1, h2, h3 = st.columns([4, 4, 2])
    with h1:
        st.markdown(
            f"<div class='sc-metric-label'>Question {q_index+1} of {total}</div>",
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown(
            f"<div class='sc-metric-label' style='text-align:center;'>"
            f"{st.session_state.get('quiz_difficulty', 'Medium')} Difficulty</div>",
            unsafe_allow_html=True,
        )
    with h3:
        is_flagged = q["id"] in st.session_state.quiz_flagged
        flag_label = "🚩 Flagged" if is_flagged else "⚐ Flag"
        if st.button(flag_label, key=f"flag_{q['id']}", use_container_width=True):
            api_call("post", "/quiz/flag", silent=True, json={
                "session_id": session["session_id"],
                "question_id": q["id"],
                "flagged": not is_flagged,
            })
            if is_flagged:
                st.session_state.quiz_flagged.discard(q["id"])
            else:
                st.session_state.quiz_flagged.add(q["id"])
            st.rerun()

    st.progress((q_index + 1) / total)
    st.markdown(f"<h3 style='margin-top:16px;line-height:1.4;'>{q['text']}</h3>", unsafe_allow_html=True)

    selected = st.session_state.quiz_answers.get(q["id"])
    if q.get("options"):
        labels = [f"{'ABCD'[i]}) {opt}" for i, opt in enumerate(q["options"])]
        try:
            sel_idx = labels.index(selected) if selected else None
        except ValueError:
            sel_idx = None
        choice = st.radio(
            "Select your answer",
            labels,
            index=sel_idx,
            key=f"radio_{q['id']}",
            label_visibility="collapsed",
        )
        if choice:
            st.session_state.quiz_answers[q["id"]] = choice
    else:
        ans = st.text_input("Your answer", value=selected or "", key=f"txt_{q['id']}")
        if ans:
            st.session_state.quiz_answers[q["id"]] = ans

    # Hint
    if st.button("💡 Get a hint", key=f"hint_{q['id']}"):
        with st.spinner("Thinking…"):
            r = api_call("post", "/quiz/hint", json={
                "question_id": q["id"], "session_id": session["session_id"],
            })
        if r:
            st.session_state.quiz_hints[q["id"]] = r["hint"]

    hint_text = st.session_state.quiz_hints.get(q["id"])
    if hint_text:
        st.markdown(
            f"<div class='sc-hint'><strong>💡 Hint</strong><br>"
            f"<span style='color:var(--on-surface-variant);'>{hint_text}</span></div>",
            unsafe_allow_html=True,
        )

    # Nav
    st.divider()
    nav_l, nav_m, nav_r = st.columns([2, 6, 2])
    with nav_l:
        if st.button("← Prev", disabled=(q_index == 0), use_container_width=True, key="prev_q"):
            st.session_state.quiz_q_index = max(0, q_index - 1)
            st.rerun()
    with nav_m:
        if st.button("📤 Submit Quiz", type="primary", use_container_width=True, key="submit_quiz"):
            answers = [{"question_id": qid, "answer": ans} for qid, ans in st.session_state.quiz_answers.items()]
            with st.spinner("Grading…"):
                result = api_call("post", "/quiz/submit", json={
                    "session_id": session["session_id"],
                    "answers": answers,
                })
            if result:
                st.session_state.quiz_result = result
                st.session_state.quiz_session = None
                st.rerun()
    with nav_r:
        if st.button("Next →", disabled=(q_index >= total - 1), use_container_width=True, key="next_q"):
            st.session_state.quiz_q_index = min(total - 1, q_index + 1)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


with right:
    # Session metrics
    st.markdown('<div class="sc-card sc-card-tight">', unsafe_allow_html=True)
    st.markdown("<h3>Session Metrics</h3>", unsafe_allow_html=True)
    answered = sum(1 for a in st.session_state.quiz_answers.values() if a)
    pct_answered = (answered / total) * 100
    mm, ss = divmod(elapsed, 60)
    mml, ssl = divmod(time_left, 60)
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
        f"<span>Time Elapsed</span><span style='font-weight:700;'>{mm:02d}:{ss:02d}</span></div>"
        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
        f"<span>Time Remaining</span><span style='font-weight:700;color:var(--secondary);'>{mml:02d}:{ssl:02d}</span></div>"
        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
        f"<span>Answered</span><span style='font-weight:700;'>{answered}/{total} ({pct_answered:.0f}%)</span></div>"
        f"<div style='display:flex;justify-content:space-between;'>"
        f"<span>Flagged</span><span style='font-weight:700;'>{len(st.session_state.quiz_flagged)}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Cancel
    st.markdown('<div style="margin-top:16px;"></div>', unsafe_allow_html=True)
    if st.button("✖ Cancel Quiz", use_container_width=True, key="cancel_quiz"):
        st.session_state.quiz_session = None
        st.session_state.quiz_answers = {}
        st.session_state.quiz_flagged = set()
        st.rerun()

# ── Show last quiz result, if any ───────────────────────

if st.session_state.get("quiz_result") and st.session_state.quiz_session is None:
    r = st.session_state.quiz_result
    st.success(f"Score: {r['score']*100:.0f}%")
    if r.get("weak_topics"):
        st.warning("Weak topics: " + ", ".join(r["weak_topics"]))
    with st.expander("Per-question breakdown", expanded=False):
        for item in r["breakdown"]:
            icon = "✅" if item["correct"] else "❌"
            st.write(f"{icon} `{item['question_id'][:8]}` — {item['explanation']}")
