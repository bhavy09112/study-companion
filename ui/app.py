"""Streamlit entry — Study page.

Multi-page UI. Other pages live in `ui/pages/`:
    01_📝_Quiz.py, 02_🃏_Flashcards.py, 03_📊_Progress.py, 04_⚙️_Settings.py
Design system: Academic Precision (Hanken Grotesk + Literata, Academic Blues).
"""
from __future__ import annotations

import time

import streamlit as st

from ui._shared import (
    apply_theme, init_state, render_sidebar, api_call,
    card_open, card_close,
)

st.set_page_config(
    page_title="Study Companion AI · Study",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()
init_state()
render_sidebar()

# ── Page header ─────────────────────────────────────────

st.markdown(
    "<h2 style='margin-bottom:4px;'>Study a Topic</h2>"
    "<p style='color:var(--on-surface-variant);margin:0 0 16px 0;'>"
    "Ask anything from your indexed material. Generate explanations, exam notes, "
    "mnemonics, concept maps, and more — grounded in your sources.</p>",
    unsafe_allow_html=True,
)

# ── Generation Control Deck ─────────────────────────────

with st.container():
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([5, 3, 2])
    with c1:
        topic = st.text_input(
            "Topic or Question",
            value=st.session_state.get("study_topic", ""),
            placeholder="e.g., Explain the mechanisms of Action Potentials",
            key="ui_study_topic",
        )
    with c2:
        mode_options = [
            ("simple_explanation", "Simple Explanation"),
            ("key_concepts", "Key Concepts"),
            ("exam_critical", "Exam Critical"),
            ("detailed_explanation", "Deep Dive"),
            ("common_mistakes", "Common Mistakes"),
            ("practice_questions", "Practice Questions"),
            ("revision_sheet", "Revision Sheet"),
            ("mnemonics", "Mnemonics"),
            ("concept_map", "Concept Map"),
        ]
        labels = [b for _, b in mode_options]
        keys = [a for a, _ in mode_options]
        try:
            default_idx = keys.index(st.session_state.get("study_mode", "key_concepts"))
        except ValueError:
            default_idx = 1
        chosen_label = st.selectbox("Output Mode", labels, index=default_idx, key="ui_mode_select")
        mode = keys[labels.index(chosen_label)]
        st.session_state.study_mode = mode
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        generate_clicked = st.button(
            "✨ Generate", type="primary", use_container_width=True,
            disabled=not topic.strip(), key="ui_generate_btn",
        )
    st.markdown("</div>", unsafe_allow_html=True)

st.session_state.study_topic = topic

# ── Run generation ──────────────────────────────────────

if generate_clicked and topic.strip():
    st.session_state.study_started_at = time.time()
    with st.spinner("Generating study material…"):
        result = api_call("post", "/generate", json={
            "topic": topic,
            "mode": mode,
            "top_k": st.session_state.top_k,
            "temperature": st.session_state.temperature,
        })
    if result:
        st.session_state.study_result = result
        # Log a study session for the dashboard
        api_call("post", "/sessions", silent=True, json={
            "kind": "study",
            "topic": topic[:120],
            "duration_seconds": int(time.time() - st.session_state.study_started_at),
            "impact_score": 5.0,
        })

result = st.session_state.get("study_result")

# ── Result + Sidebar layout ─────────────────────────────

left, right = st.columns([8, 4], gap="large")

with left:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    header_l, header_r = st.columns([6, 1])
    with header_l:
        st.markdown("<h3 style='margin:0;'>📄 Generated Content</h3>", unsafe_allow_html=True)
    with header_r:
        if result and st.button("🔖 Save", key="bookmark_btn", help="Bookmark this output"):
            api_call("post", "/bookmarks", silent=True, json={
                "content": result["output"],
                "topic": st.session_state.study_topic,
                "mode": st.session_state.study_mode,
            })
            st.toast("Bookmarked")
    st.divider()

    if not result:
        st.info("Enter a topic above and click **Generate** to produce study material from your indexed sources.")
    else:
        if result.get("uncertain"):
            st.warning("⚠ This topic may not be well-covered by your uploaded materials.")
        for w in result.get("warnings", []):
            st.info(w)
        st.markdown(result["output"])

        # Copy + flashcards
        cpy_col, fc_col = st.columns(2)
        with cpy_col:
            # Streamlit lacks a real clipboard hook; use a download fallback
            st.download_button(
                "📋 Copy as Markdown", data=result["output"], file_name="study_notes.md",
                mime="text/markdown", use_container_width=True, key="copy_md",
            )
        with fc_col:
            if st.button("➕ Make Flashcards from this", use_container_width=True, key="make_fc"):
                with st.spinner("Extracting Q/A pairs…"):
                    fc = api_call("post", "/flashcards/from-text", json={
                        "text": result["output"],
                        "topic": st.session_state.study_topic or None,
                        "n_cards": 8,
                    })
                if fc:
                    st.success(f"Added {fc['cards_added']} cards. Open Flashcards to review.")
    st.markdown("</div>", unsafe_allow_html=True)


with right:
    # Quick Actions
    st.markdown('<div class="sc-card sc-card-tight">', unsafe_allow_html=True)
    st.markdown("<h3>⚡ Quick Actions</h3>"
                "<p style='color:var(--on-surface-variant);font-size:13px;'>"
                "Modify the current generated content.</p>",
                unsafe_allow_html=True)
    qa_disabled = result is None

    def _refine(action: str, target_language: str | None = None) -> None:
        with st.spinner(f"{action.title()}…"):
            r = api_call("post", "/generate/refine", json={
                "content": result["output"],
                "action": action,
                "target_language": target_language,
            })
        if r:
            new_result = dict(result)
            new_result["output"] = r["output"]
            st.session_state.study_result = new_result
            st.rerun()

    if st.button("📝 Summarize", use_container_width=True, disabled=qa_disabled, key="qa_sum"):
        _refine("summarize")
    if st.button("👶 Simplify", use_container_width=True, disabled=qa_disabled, key="qa_simp"):
        _refine("simplify")
    if st.button("🔬 Elaborate", use_container_width=True, disabled=qa_disabled, key="qa_elab"):
        _refine("elaborate")

    tcol1, tcol2 = st.columns([3, 2])
    with tcol1:
        lang = st.text_input("Translate to", value="Spanish", key="qa_lang", label_visibility="collapsed",
                              placeholder="Language")
    with tcol2:
        if st.button("🌐 Go", use_container_width=True, disabled=qa_disabled, key="qa_trans"):
            _refine("translate", target_language=lang)
    st.markdown("</div>", unsafe_allow_html=True)

    # Cited Sources
    st.markdown('<div class="sc-card sc-card-tight" style="margin-top:16px;">', unsafe_allow_html=True)
    sources = (result or {}).get("sources", []) or []
    st.markdown(
        f"<h3>📚 Cited Sources "
        f"<span class='sc-chip' style='float:right;'>{len(sources)}</span></h3>",
        unsafe_allow_html=True,
    )
    if not sources:
        st.caption("Sources will appear once you generate from indexed material.")
    else:
        for s in sources:
            with st.expander(f"📄 {s['source']} · p.{s['page']} · {s['score']:.2f}"):
                st.caption(f"chunk_id: `{s['chunk_id']}`")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Quick-mode chips ────────────────────────────────────

st.divider()
st.caption("Quick modes")
qm_cols = st.columns(5)
quick_modes = [
    ("📖 Simple", "simple_explanation"),
    ("🔑 Key Points", "key_concepts"),
    ("⚡ Exam", "exam_critical"),
    ("🧠 Mnemonics", "mnemonics"),
    ("🗺️ Concept Map", "concept_map"),
]
for col, (label, qmode) in zip(qm_cols, quick_modes):
    with col:
        if st.button(label, use_container_width=True, key=f"qm_{qmode}"):
            if topic.strip():
                st.session_state.study_mode = qmode
                with st.spinner("Generating…"):
                    res = api_call("post", "/generate", json={
                        "topic": topic, "mode": qmode,
                        "top_k": st.session_state.top_k,
                        "temperature": st.session_state.temperature,
                    })
                if res:
                    st.session_state.study_result = res
                    st.rerun()
            else:
                st.toast("Enter a topic first.")
