"""Progress dashboard — bento metrics, activity heatmap, recent sessions."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from ui._shared import apply_theme, init_state, render_sidebar, api_call

st.set_page_config(
    page_title="Study Companion · Progress",
    page_icon="📊",
    layout="wide",
)

apply_theme()
init_state()
render_sidebar()

st.markdown(
    "<h2>Dashboard Metrics</h2>"
    "<p style='color:var(--on-surface-variant);'>Track your cognitive load, mastery, and system health.</p>",
    unsafe_allow_html=True,
)

dash = api_call("get", "/dashboard") or {}
heatmap = api_call("get", "/activity/heatmap", params={"days": 30}) or {"days": []}
sessions = api_call("get", "/sessions/recent", params={"limit": 6}) or {"sessions": []}
progress = api_call("get", "/progress") or {"topics": [], "overall_mastery": 0.0, "total_cards": 0}
health = api_call("get", "/health") or {}

# Row 1: Three metric cards
m1, m2, m3 = st.columns(3)

with m1:
    hrs = dash.get("study_hours_total", 0.0)
    week = dash.get("study_hours_week", 0.0)
    pct = dash.get("weekly_goal_percent", 0.0)
    st.markdown(
        f"<div class='sc-card'>"
        f"<div class='sc-metric-label'>Study Time</div>"
        f"<div class='sc-metric-value'>{hrs:.1f}<span style='font-size:18px;color:var(--on-surface-variant);'> hrs</span></div>"
        f"<div class='sc-metric-delta'>+{week:.1f} hrs this week</div>"
        f"<div style='margin-top:16px;'>"
        f"<div style='display:flex;justify-content:space-between;font-size:12px;color:var(--on-surface-variant);'>"
        f"<span>Weekly Goal</span><span>{pct:.0f}%</span></div></div>",
        unsafe_allow_html=True,
    )
    st.progress(min(pct / 100.0, 1.0))
    st.markdown("</div>", unsafe_allow_html=True)

with m2:
    ret = dash.get("flashcard_retention", 0.0) * 100
    due = dash.get("review_due_count", 0)
    mastered = dash.get("mastered_count", 0)
    st.markdown(
        f"<div class='sc-card'>"
        f"<div class='sc-metric-label'>Flashcard Mastery</div>"
        f"<div class='sc-metric-value'>{ret:.0f}<span style='font-size:18px;color:var(--on-surface-variant);'>%</span></div>"
        f"<div class='sc-metric-delta'>Retention across all decks</div>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;'>"
        f"<div style='background:var(--surface-low);padding:8px 10px;border-radius:6px;'>"
        f"<div class='sc-metric-label'>Review Due</div>"
        f"<div style='font-weight:700;color:var(--primary);'>{due} cards</div></div>"
        f"<div style='background:var(--surface-low);padding:8px 10px;border-radius:6px;'>"
        f"<div class='sc-metric-label'>Mastered</div>"
        f"<div style='font-weight:700;color:var(--secondary);'>{mastered} cards</div></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

with m3:
    grade = dash.get("quiz_letter_grade", "—")
    avg = dash.get("quiz_avg_score")
    avg_label = f"{avg*100:.0f}%" if avg is not None else "no data"
    st.markdown(
        f"<div class='sc-card'>"
        f"<div class='sc-metric-label'>Quiz Performance</div>"
        f"<div class='sc-metric-value'>{grade}<span style='font-size:16px;color:var(--on-surface-variant);margin-left:8px;'>Avg</span></div>"
        f"<div class='sc-metric-delta'>Last 12 assessments · {avg_label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# Row 2: System health + activity heatmap
sh, ah = st.columns([5, 7])

with sh:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    st.markdown("<h3>Model &amp; Index Health</h3>", unsafe_allow_html=True)
    healthy = health.get("model_loaded", False)
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
        f"<span>Index Status</span>"
        f"<span class='sc-chip {'sc-chip-success' if healthy else 'sc-chip-error'}'>"
        f"{'Healthy' if healthy else 'Offline'}</span></div>"
        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
        f"<span>Active Model</span><span style='font-weight:600;color:var(--secondary);'>{health.get('model_name','—')}</span></div>"
        f"<div style='display:flex;justify-content:space-between;margin-bottom:8px;'>"
        f"<span>Vector Chunk Count</span><span style='font-weight:600;'>{health.get('index_size',0):,}</span></div>"
        f"<div style='display:flex;justify-content:space-between;'>"
        f"<span>Total Cards</span><span style='font-weight:600;'>{health.get('db_cards',0):,}</span></div>",
        unsafe_allow_html=True,
    )
    if st.button("🔁 Run Diagnostics", key="run_diag"):
        st.toast("Refreshed health snapshot")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with ah:
    st.markdown('<div class="sc-card">', unsafe_allow_html=True)
    st.markdown("<h3>Activity Intensity (last 30 days)</h3>", unsafe_allow_html=True)
    days = heatmap["days"]
    if not days:
        st.caption("No activity logged yet. Generate study content or run a quiz.")
    else:
        max_count = max((d["count"] for d in days), default=1)
        bars = "".join(
            f"<div class='sc-bar' style='height:{max(8, int((d['count']/max_count)*96))}px;'"
            f" title='{d['day']}: {d['count']} sessions'></div>"
            for d in days
        )
        st.markdown(f"<div class='sc-bars'>{bars}</div>", unsafe_allow_html=True)
        first, last = days[0]["day"], days[-1]["day"]
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;color:var(--on-surface-variant);"
            f"font-size:11px;margin-top:6px;'><span>{first}</span><span>{last}</span></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# Row 3: Topic mastery
st.markdown('<div class="sc-card">', unsafe_allow_html=True)
st.markdown("<h3>Topic Mastery</h3>", unsafe_allow_html=True)
topics = progress.get("topics", [])
if not topics:
    st.caption("No topics tracked yet. Run a quiz to start scoring mastery per topic.")
else:
    for t in topics:
        c1, c2, c3 = st.columns([3, 7, 1])
        c1.write(f"**{t['name']}**")
        c2.progress(min(t["mastery_score"], 1.0))
        c3.write(f"{t['mastery_score']*100:.0f}%")
st.markdown("</div>", unsafe_allow_html=True)

# Row 4: Recent sessions
st.markdown('<div class="sc-card">', unsafe_allow_html=True)
st.markdown("<h3>Recent Study Sessions</h3>", unsafe_allow_html=True)
rs = sessions.get("sessions", [])
if not rs:
    st.caption("Your recent sessions will appear here.")
else:
    rows = []
    for s in rs:
        try:
            dt = datetime.fromisoformat(s["started_at"].replace("Z", ""))
            when = dt.strftime("%b %d, %I:%M %p")
        except Exception:
            when = s["started_at"]
        mins = s["duration_seconds"] // 60
        impact = s.get("impact_score")
        impact_txt = f"+{impact:.0f}" if impact and impact > 0 else (f"{impact:.0f}" if impact else "—")
        rows.append(
            f"<tr><td><strong>{s.get('topic') or s['kind'].title()}</strong>"
            f"<div style='font-size:11px;color:var(--on-surface-variant);'>{s['kind']}</div></td>"
            f"<td>{when}</td><td>{mins} min</td>"
            f"<td style='text-align:right;'><span class='sc-chip'>{impact_txt}</span></td></tr>"
        )
    st.markdown(
        "<table class='sc-table'><thead><tr>"
        "<th>Topic / Activity</th><th>Date</th><th>Duration</th><th style='text-align:right;'>Impact</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>",
        unsafe_allow_html=True,
    )
st.markdown("</div>", unsafe_allow_html=True)
