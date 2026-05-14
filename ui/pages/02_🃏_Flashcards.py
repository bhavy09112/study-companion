"""Flashcards page — SM-2 spaced repetition with Hard/Good/Easy ratings."""
from __future__ import annotations

import streamlit as st

from ui._shared import apply_theme, init_state, render_sidebar, api_call

st.set_page_config(
    page_title="Study Companion · Flashcards",
    page_icon="🃏",
    layout="wide",
)

apply_theme()
init_state()
render_sidebar()

st.markdown(
    "<div style='display:flex;align-items:end;justify-content:space-between;'>"
    "<div><div class='sc-metric-label'>Deck Review</div>"
    "<h2 style='margin:4px 0 0 0;'>Spaced Repetition</h2></div>"
    "</div>",
    unsafe_allow_html=True,
)

data = api_call("get", "/flashcards/due") or {"cards": [], "count": 0}
cards = data["cards"]
count = data["count"]

# Top metric: due count
m1, m2, m3 = st.columns([3, 3, 6])
with m1:
    badge_class = "sc-chip-error" if count > 0 else "sc-chip-success"
    st.markdown(
        f"<div class='sc-card sc-card-tight'>"
        f"<div class='sc-metric-label'>Review Due</div>"
        f"<div class='sc-metric-value' style='color:{'var(--error)' if count>0 else 'var(--success)'};'>{count}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

if not cards:
    st.info("🎉 No cards due. Upload some material and run **Make Flashcards** from the Study page, "
            "or add cards via `/flashcards/from-text`.")
    st.stop()

# Bound index
if "flashcard_index" not in st.session_state:
    st.session_state.flashcard_index = 0
idx = st.session_state.flashcard_index % len(cards)
card = cards[idx]
st.session_state.flashcard_last_card_id = card["id"]

# Progress bar + nav
with m3:
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-top:10px;'>"
        f"<span class='sc-metric-label'>Card {idx+1} of {len(cards)}</span></div>",
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / len(cards))

# The card
st.markdown(f'<div class="sc-flashcard"><div class="sc-flashcard-front">{card["front"]}</div></div>',
            unsafe_allow_html=True)

if card.get("topic"):
    st.caption(f"Topic: {card['topic']}")

# Reveal / Rate
if not st.session_state.flashcard_show_answer:
    if st.button("👁 Reveal Answer", type="primary", use_container_width=True, key="reveal_btn"):
        st.session_state.flashcard_show_answer = True
        st.rerun()
else:
    st.markdown(
        f"<div class='sc-flashcard sc-flashcard-back' style='margin-top:12px;'>"
        f"<div style='font-family:Literata,serif;'>{card['back']}</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<p style='text-align:center;color:var(--on-surface-variant);"
                "margin:16px 0 8px 0;'>How difficult was it to recall?</p>",
                unsafe_allow_html=True)
    rc1, rc2, rc3 = st.columns(3)
    # SM-2 quality mapping: Hard=2, Good=4, Easy=5
    rating_map = [("Hard", 2, "< 1m"), ("Good", 4, "~10m"), ("Easy", 5, "~4d")]

    def _rate(quality: int) -> None:
        with st.spinner("Scheduling…"):
            api_call("post", "/flashcards/review", silent=True, json={
                "card_id": card["id"], "quality": quality,
            })
        st.session_state.flashcard_index += 1
        st.session_state.flashcard_show_answer = False
        st.rerun()

    for col, (label, q, hint) in zip([rc1, rc2, rc3], rating_map):
        with col:
            if st.button(f"{label}  ·  {hint}", key=f"rate_{label}",
                         use_container_width=True,
                         type=("primary" if label == "Easy" else "secondary")):
                _rate(q)

# Footer controls
st.divider()
fc1, fc2, fc3 = st.columns([1, 1, 4])
with fc1:
    if st.button("↶ Undo Last", use_container_width=True, key="undo_btn"):
        if st.session_state.flashcard_last_card_id:
            r = api_call("post", "/flashcards/undo", silent=True,
                         json={"card_id": st.session_state.flashcard_last_card_id})
            if r and r.get("undone"):
                st.session_state.flashcard_index = max(0, st.session_state.flashcard_index - 1)
                st.session_state.flashcard_show_answer = False
                st.toast("Last review undone")
                st.rerun()
            else:
                st.toast("Nothing to undo")
with fc2:
    if st.button("📥 Export Anki", use_container_width=True, key="export_btn"):
        import requests
        try:
            resp = requests.get(f"{st.session_state.api_url}/export/anki", timeout=30)
            if resp.status_code == 200:
                st.download_button(
                    "⬇ Download .apkg",
                    data=resp.content,
                    file_name="study_companion.apkg",
                    mime="application/octet-stream",
                    key="dl_apkg",
                )
            else:
                st.warning("No cards to export yet.")
        except Exception as e:
            st.error(f"Export failed: {e}")
with fc3:
    st.caption("Tip: rate generously when you're close — SM-2 will widen intervals.")
