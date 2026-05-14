"""Settings — connectivity, model parameters, storage management, bookmarks."""
from __future__ import annotations

import requests
import streamlit as st

from ui._shared import apply_theme, init_state, render_sidebar, api_call, DEFAULT_API_URL

st.set_page_config(
    page_title="Study Companion · Settings",
    page_icon="⚙️",
    layout="wide",
)

apply_theme()
init_state()
render_sidebar()

st.markdown(
    "<h2>Application Settings</h2>"
    "<p style='color:var(--on-surface-variant);max-width:680px;'>"
    "Configure your local AI environment, adjust model parameters, and manage stored data.</p>",
    unsafe_allow_html=True,
)

left, right = st.columns([7, 5], gap="large")

# ── Connectivity ────────────────────────────────────────

with left:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    st.markdown("<h3>🌐 Connectivity</h3>", unsafe_allow_html=True)
    api_url = st.text_input(
        "Local API URL",
        value=st.session_state.get("api_url", DEFAULT_API_URL),
        key="set_api_url",
    )
    st.caption("Endpoint where the FastAPI backend is running.")

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Test Connection", key="test_conn"):
            try:
                r = requests.get(f"{api_url}/health", timeout=5)
                if r.status_code == 200:
                    h = r.json()
                    st.success(f"Connected · model={h.get('model_name','?')} · index={h.get('index_size')}")
                else:
                    st.error(f"HTTP {r.status_code}")
            except Exception as e:
                st.error(f"Failed: {e}")
    with c2:
        if st.button("Save URL", type="primary", key="save_url"):
            st.session_state.api_url = api_url
            st.toast("API URL saved")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Model parameters ────────────────────────────────
    st.markdown('<div class="sc-card" style="margin-top:16px;">', unsafe_allow_html=True)
    st.markdown("<h3>🎛 Model Parameters</h3>", unsafe_allow_html=True)
    top_k = st.slider(
        "Top-K retrieved chunks", 1, 20,
        st.session_state.get("top_k", 5),
        help="How many chunks to feed into the LLM as context.",
    )
    temperature = st.slider(
        "Temperature", 0.0, 2.0,
        st.session_state.get("temperature", 0.7), 0.1,
        help="0 = deterministic; higher = more creative.",
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ── Storage management ──────────────────────────────────

with right:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    st.markdown("<h3>💾 Local Storage</h3>", unsafe_allow_html=True)

    idx_data = api_call("get", "/index/files") or {"files": [], "total_chunks": 0}
    total_chunks = idx_data["total_chunks"]
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;margin-bottom:6px;'>"
        f"<span class='sc-metric-label'>Vector Index</span>"
        f"<span style='font-weight:600;'>{total_chunks:,} chunks</span></div>",
        unsafe_allow_html=True,
    )
    # Cap visual at 5000 chunks for the bar
    pct = min(1.0, total_chunks / 5000)
    st.progress(pct)
    st.caption("Documents and flashcards are stored locally — fully private.")

    with st.expander(f"📁 Indexed files ({len(idx_data['files'])})"):
        if not idx_data["files"]:
            st.caption("Nothing indexed yet. Upload material from the sidebar.")
        else:
            for f in idx_data["files"]:
                st.markdown(f"<div class='sc-source'>📄 {f['source']} "
                            f"<small>· {f['chunk_count']} chunks</small></div>",
                            unsafe_allow_html=True)

    danger = st.checkbox("I understand this deletes my knowledge index", key="clear_ack")
    if st.button("🗑 Clear Knowledge Index", disabled=not danger, key="clear_idx"):
        with st.spinner("Clearing…"):
            r = api_call("delete", "/index")
        if r and r.get("cleared"):
            st.success(f"Removed {r.get('deleted_chunks', 0)} chunks.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Bookmarks
    st.markdown('<div class="sc-card" style="margin-top:16px;">', unsafe_allow_html=True)
    st.markdown("<h3>🔖 Bookmarks</h3>", unsafe_allow_html=True)
    bm = api_call("get", "/bookmarks") or {"bookmarks": []}
    if not bm["bookmarks"]:
        st.caption("Save any generated output from the Study page to find it here.")
    else:
        for b in bm["bookmarks"][:10]:
            with st.expander(f"📌 {b.get('topic') or 'Untitled'} · {b.get('mode') or 'mode?'}"):
                st.markdown(b["content"])
                if st.button("Remove", key=f"del_bm_{b['id']}"):
                    api_call("delete", f"/bookmarks/{b['id']}", silent=True)
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ── Save / Discard global controls ──────────────────────

st.divider()
sl, sr = st.columns([6, 6])
with sl:
    if st.button("Discard Changes", key="discard_changes"):
        st.rerun()
with sr:
    if st.button("💾 Save Settings", type="primary", use_container_width=True, key="save_settings"):
        st.session_state.api_url = api_url
        st.session_state.top_k = top_k
        st.session_state.temperature = temperature
        st.success("Settings saved.")

# ── About ───────────────────────────────────────────────

st.markdown('<div class="sc-card" style="margin-top:24px;">', unsafe_allow_html=True)
st.markdown("<h3>ℹ About</h3>", unsafe_allow_html=True)
st.markdown(
    """
**Study Companion AI** v1.1.0 — a local-first, RAG-augmented study assistant.
Built with Mistral-7B + Ollama + FAISS + FastAPI + Streamlit.

* Multi-format ingestion · Hybrid retrieval · Domain-aware formatting
* SM-2 spaced repetition · Quick refinements · Anki export
"""
)
st.markdown("</div>", unsafe_allow_html=True)
