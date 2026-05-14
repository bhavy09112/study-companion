"""Shared helpers for the Streamlit UI: API client, theming, session state."""
from __future__ import annotations

import time
from typing import Optional

import requests
import streamlit as st

DEFAULT_API_URL = "http://localhost:8000"


# ── Theme (Academic Precision design system) ───────────

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@500;600;700&family=Literata:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap');

:root {
    --primary: #002045;
    --primary-container: #1a365d;
    --secondary: #0060ac;
    --secondary-container: #64a8fe;
    --secondary-fixed: #d4e3ff;
    --surface: #f8f9ff;
    --surface-bright: #f8f9ff;
    --surface-low: #eff4ff;
    --surface-container: #e6eeff;
    --surface-container-high: #dde9ff;
    --surface-container-lowest: #ffffff;
    --on-surface: #0d1c2f;
    --on-surface-variant: #43474e;
    --outline: #74777f;
    --outline-variant: #c4c6cf;
    --error: #ba1a1a;
    --error-container: #ffdad6;
    --on-error-container: #93000a;
    --success: #2e7d32;
}

html, body, [class*="css"] {
    font-family: 'Literata', Georgia, serif;
    color: var(--on-surface);
}
h1, h2, h3, h4, h5, h6,
.stButton, .stTabs button, .stSelectbox label, .stTextInput label,
.stSlider label, .stRadio label, .stMetric label, .stCaption,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
    font-family: 'Hanken Grotesk', system-ui, sans-serif !important;
    letter-spacing: -0.005em;
}
h1, h2, h3 { color: var(--primary); font-weight: 700; }

/* App background */
.stApp { background: var(--surface); }
section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--outline-variant); }
section[data-testid="stSidebar"] h1 { color: var(--primary); font-size: 18px !important; }

/* Buttons — primary navy */
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: var(--primary) !important;
    color: #fff !important;
    border: 1px solid var(--primary) !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em;
    box-shadow: 0 2px 4px rgba(0,32,69,0.08);
}
.stButton > button[kind="primary"]:hover {
    background: var(--primary-container) !important;
    border-color: var(--primary-container) !important;
}
.stButton > button:not([kind="primary"]) {
    background: #fff !important;
    color: var(--primary) !important;
    border: 1px solid var(--outline-variant) !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: var(--primary) !important;
    background: var(--surface-low) !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    border-radius: 4px !important;
    border: 1px solid var(--outline-variant) !important;
    background: #fff !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--secondary) !important;
    box-shadow: 0 0 0 1px var(--secondary) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--outline-variant); }
.stTabs [data-baseweb="tab"] {
    padding: 8px 16px;
    border-radius: 4px 4px 0 0;
    color: var(--on-surface-variant);
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom: 2px solid var(--primary) !important;
}

/* Cards */
.sc-card {
    background: #fff;
    border: 1px solid var(--outline-variant);
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,32,69,0.05);
}
.sc-card-tight { padding: 14px 16px; }
.sc-card h3 { margin: 0 0 8px 0; font-size: 16px; color: var(--primary); }
.sc-metric-value { font-size: 32px; font-weight: 700; color: var(--primary); line-height: 1.1; }
.sc-metric-label { font-size: 12px; color: var(--on-surface-variant); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.sc-metric-delta { font-size: 13px; color: var(--secondary); margin-top: 4px; }

/* Pill / chip */
.sc-chip {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--surface-container);
    color: var(--primary);
    padding: 2px 10px; border-radius: 9999px;
    font-size: 12px; font-weight: 600;
    font-family: 'Hanken Grotesk', sans-serif;
}
.sc-chip-error { background: var(--error-container); color: var(--on-error-container); }
.sc-chip-success { background: #e6f4ea; color: var(--success); }

/* Hint card */
.sc-hint {
    background: #fff;
    border-left: 4px solid var(--secondary-container);
    border-radius: 4px;
    padding: 12px 16px;
    border: 1px solid var(--outline-variant);
}

/* Progress bar (replace Streamlit default) */
.stProgress > div > div > div { background-color: var(--secondary) !important; }
.stProgress > div > div { background-color: var(--surface-container) !important; height: 8px !important; }

/* Mute footer */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }

/* Page padding */
.block-container { max-width: 1280px; padding-top: 1.5rem; }

/* Flashcard styling */
.sc-flashcard {
    background: #fff;
    border: 1px solid var(--outline-variant);
    border-radius: 12px;
    padding: 56px 40px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,32,69,0.05);
    min-height: 220px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Hanken Grotesk', sans-serif;
}
.sc-flashcard-front { font-size: 22px; font-weight: 600; color: var(--on-surface); }
.sc-flashcard-back {
    background: var(--surface-bright);
    color: var(--on-surface-variant);
    border-top: 1px solid var(--surface-container);
}

/* Heatmap bars */
.sc-bars { display: flex; align-items: flex-end; gap: 2px; height: 96px; }
.sc-bar { flex: 1; background: var(--surface-container); border-radius: 2px 2px 0 0; transition: background 0.15s; }
.sc-bar:hover { background: var(--secondary); }

/* Brand header */
.sc-brand { display: flex; gap: 10px; align-items: center; padding: 0 0 16px 0; border-bottom: 1px solid var(--outline-variant); margin-bottom: 16px; }
.sc-brand-mark {
    width: 36px; height: 36px; border-radius: 8px;
    background: var(--primary); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-family: 'Hanken Grotesk', sans-serif;
}
.sc-brand h1 { margin: 0; font-size: 16px; color: var(--primary); }
.sc-brand p { margin: 0; font-size: 11px; color: var(--on-surface-variant); text-transform: uppercase; letter-spacing: 0.05em; }

/* Source / citation accordion */
.sc-source {
    background: #fff; border: 1px solid var(--outline-variant); border-radius: 6px;
    padding: 10px 12px; margin-bottom: 6px;
    font-size: 13px; color: var(--on-surface);
}
.sc-source small { color: var(--on-surface-variant); }

/* Tables in Progress */
.sc-table { width: 100%; border-collapse: collapse; }
.sc-table th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--on-surface-variant); padding: 8px 12px; background: var(--surface-bright); border-bottom: 1px solid var(--outline-variant); font-family: 'Hanken Grotesk', sans-serif; }
.sc-table td { padding: 12px; border-bottom: 1px solid var(--surface-container); font-size: 14px; }
.sc-table tr:hover td { background: var(--surface-low); }

</style>
"""


def apply_theme() -> None:
    """Inject design-system CSS once per page."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def sidebar_brand() -> None:
    """Brand header inside the sidebar."""
    st.markdown(
        '<div class="sc-brand"><div class="sc-brand-mark">SC</div>'
        '<div><h1>Study Companion</h1><p>AI Assistant</p></div></div>',
        unsafe_allow_html=True,
    )


# ── Session state init ──────────────────────────────────

def init_state() -> None:
    defaults = {
        "api_url": DEFAULT_API_URL,
        "top_k": 5,
        "temperature": 0.7,
        "quiz_session": None,
        "quiz_answers": {},
        "quiz_flagged": set(),
        "quiz_started_at": None,
        "quiz_hints": {},
        "flashcard_index": 0,
        "flashcard_show_answer": False,
        "flashcard_last_card_id": None,
        "study_result": None,
        "study_topic": "",
        "study_mode": "key_concepts",
        "study_started_at": time.time(),
        "search_query": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── API helpers ─────────────────────────────────────────

def api_call(method: str, endpoint: str, *, silent: bool = False, **kwargs):
    """Make an API call; surface errors in Streamlit unless silent=True."""
    url = f"{st.session_state.get('api_url', DEFAULT_API_URL)}{endpoint}"
    try:
        resp = getattr(requests, method)(url, timeout=120, **kwargs)
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.content
    except requests.exceptions.ConnectionError:
        if not silent:
            st.error("Cannot connect to API. Start it with: `uvicorn api.main:app --port 8000`")
        return None
    except requests.exceptions.HTTPError as e:
        if not silent:
            body = e.response.text[:240] if e.response is not None else ""
            st.error(f"API error: {e.response.status_code if e.response is not None else '?'} — {body}")
        return None
    except Exception as e:
        if not silent:
            st.error(f"Request failed: {e}")
        return None


def health_snapshot() -> Optional[dict]:
    return api_call("get", "/health", silent=True)


# ── Reusable widgets ────────────────────────────────────

def render_search_box(key_prefix: str = "topbar") -> None:
    """Global search field — queries /search."""
    q = st.text_input(
        "Search resources, cards, chunks…",
        value=st.session_state.get("search_query", ""),
        key=f"{key_prefix}_search",
        placeholder="Search concepts, documents, flashcards…",
        label_visibility="collapsed",
    )
    st.session_state.search_query = q
    if q.strip():
        with st.spinner("Searching…"):
            data = api_call("get", "/search", params={"q": q, "limit": 8})
        if data and data.get("hits"):
            for hit in data["hits"]:
                icon = {"chunk": "📄", "card": "🃏", "bookmark": "🔖"}.get(hit["kind"], "•")
                with st.expander(f"{icon} {hit['title']}"):
                    st.caption(f"kind={hit['kind']} · score={hit['score']:.2f}")
                    st.write(hit["snippet"])
        elif data is not None:
            st.caption("No matches.")


def upload_panel() -> None:
    """Sidebar upload widget shared across pages."""
    st.subheader("📄 Upload")
    files = st.file_uploader(
        "Documents",
        type=["pdf", "docx", "txt", "md", "png", "jpg", "jpeg", "html"],
        accept_multiple_files=True,
        key="sb_files",
        label_visibility="collapsed",
    )
    url = st.text_input("…or paste a URL", key="sb_url", placeholder="https://…")
    if st.button("Upload & Ingest", type="primary", use_container_width=True, key="sb_ingest"):
        if not files and not url:
            st.warning("Pick a file or paste a URL first.")
            return
        with st.spinner("Indexing…"):
            payload = []
            for f in files or []:
                payload.append(("files", (f.name, f.getvalue(), f.type or "application/octet-stream")))
            params = {"urls": url} if url else None
            data = api_call("post", "/ingest", files=payload or None, params=params)
        if data:
            st.success(f"Added {data['chunks_added']} chunks from {len(data['sources'])} source(s).")


def status_panel() -> None:
    """Compact system-health panel for the sidebar."""
    health = health_snapshot()
    st.subheader("🔧 Status")
    if not health:
        st.caption("API offline")
        return
    col1, col2 = st.columns(2)
    col1.metric("Model", "Ready" if health["model_loaded"] else "Down")
    col2.metric("Index", f"{health['index_size']}")
    st.caption(f"{health.get('model_name','')} · Cards: {health['db_cards']}")


def render_sidebar() -> None:
    """Standard sidebar shared across all pages."""
    with st.sidebar:
        sidebar_brand()
        upload_panel()
        st.divider()
        status_panel()
        st.divider()
        if st.button("New Session", use_container_width=True, key="sb_new_session"):
            for k in ("quiz_session", "quiz_answers", "quiz_flagged",
                       "flashcard_index", "flashcard_show_answer", "study_result"):
                if k in st.session_state:
                    st.session_state[k] = type(st.session_state[k])() if isinstance(st.session_state[k], (dict, set, list)) else None
            st.session_state.flashcard_index = 0
            st.session_state.flashcard_show_answer = False
            st.success("New session started.")


def card_open(title: str = "", icon: str = "") -> None:
    label = f"{icon} {title}" if icon else title
    st.markdown(f'<div class="sc-card"><h3>{label}</h3>', unsafe_allow_html=True)


def card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
