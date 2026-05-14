// Progress dashboard wiring.

(function () {
    const $ = id => document.getElementById(id);

    async function loadAll() {
        await Promise.all([loadDash(), loadHeatmap(), loadSessions(), loadTopics(), loadHealth()]);
    }

    async function loadDash() {
        try {
            const d = await api.dashboard();
            $("m-hours").textContent = (d.study_hours_total ?? 0).toFixed(1);
            $("m-week").textContent = (d.study_hours_week ?? 0).toFixed(1);
            $("m-goal-pct").textContent = Math.round(d.weekly_goal_percent ?? 0);
            $("m-goal-bar").style.width = `${Math.min(100, d.weekly_goal_percent ?? 0)}%`;
            $("m-retention").textContent = Math.round((d.flashcard_retention ?? 0) * 100);
            $("m-due").textContent = d.review_due_count ?? 0;
            $("m-mastered").textContent = d.mastered_count ?? 0;
            $("m-grade").textContent = d.quiz_letter_grade || "—";
            $("m-quiz-detail").textContent = d.quiz_avg_score != null
                ? `Avg ${Math.round(d.quiz_avg_score * 100)}% across last 12 quizzes`
                : "Take a quiz to start tracking.";
            renderSparkline();
        } catch {}
    }

    function renderSparkline() {
        // Render a passive sparkline based on heatmap (set later, refresh together)
        const root = $("m-sparkline");
        root.innerHTML = "";
        const days = (window._heatmapDays || []).slice(-7);
        if (!days.length) {
            for (let i = 0; i < 7; i++) {
                const d = document.createElement("div");
                d.className = "flex-1 bg-surface-container rounded-t-sm";
                d.style.height = "4px";
                root.appendChild(d);
            }
            return;
        }
        const max = Math.max(...days.map(d => d.count), 1);
        days.forEach(d => {
            const bar = document.createElement("div");
            const h = Math.max(8, Math.round((d.count / max) * 48));
            bar.className = d.count > 0
                ? "flex-1 bg-secondary-container rounded-t-sm"
                : "flex-1 bg-surface-container rounded-t-sm";
            bar.style.height = `${h}px`;
            bar.title = `${d.day}: ${d.count} sessions`;
            root.appendChild(bar);
        });
    }

    async function loadHeatmap() {
        const days = parseInt($("heatmap-range").value, 10);
        try {
            const r = await api.heatmap(days);
            window._heatmapDays = r.days || [];
            const root = $("heatmap-bars");
            root.innerHTML = "";
            if (!r.days.length) {
                root.innerHTML = `<p class="font-body-sm text-on-surface-variant self-center mx-auto">No activity yet.</p>`;
                $("heatmap-start").textContent = "—";
                $("heatmap-end").textContent = "—";
                return;
            }
            const max = Math.max(...r.days.map(d => d.count), 1);
            r.days.forEach(d => {
                const pct = Math.round((d.count / max) * 100);
                const bar = document.createElement("div");
                bar.className = "w-full rounded-t cursor-pointer transition-colors hover:bg-secondary relative group";
                bar.style.height = `${Math.max(4, pct)}%`;
                bar.style.minHeight = "4px";
                bar.style.background = d.count === 0 ? "#e6eeff" : (pct > 70 ? "#0060ac" : "#a4c9ff");
                bar.innerHTML = `<div class="absolute -top-9 left-1/2 -translate-x-1/2 bg-inverse-surface text-inverse-on-surface font-label-sm text-label-sm px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">${d.day}: ${d.count}</div>`;
                root.appendChild(bar);
            });
            $("heatmap-start").textContent = r.days[0].day;
            $("heatmap-end").textContent = r.days[r.days.length - 1].day;
            renderSparkline();
        } catch {}
    }

    async function loadSessions() {
        try {
            const r = await api.sessions(8);
            const root = $("sessions-list");
            if (!r.sessions.length) {
                root.innerHTML = `<div class="p-md text-on-surface-variant font-body-sm">No sessions recorded yet.</div>`;
                return;
            }
            root.innerHTML = r.sessions.map(s => {
                let when = s.started_at;
                try {
                    when = new Date(s.started_at.replace(" ", "T") + "Z").toLocaleString(undefined, {
                        month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                    });
                } catch {}
                const mins = Math.max(0, Math.round(s.duration_seconds / 60));
                const impact = s.impact_score;
                const impactTxt = impact == null ? "—" : (impact >= 0 ? `+${impact.toFixed(0)}` : impact.toFixed(0));
                const trendIcon = impact == null ? "trending_flat" : (impact >= 0 ? "trending_up" : "trending_down");
                const kindIcon = { study: "menu_book", quiz: "quiz", flashcards: "style" }[s.kind] || "circle";
                return `
                <div class="grid grid-cols-12 gap-md px-md py-3 items-center hover:bg-surface-container-low transition-colors duration-150">
                    <div class="col-span-5 flex items-center gap-sm">
                        <span class="material-symbols-outlined text-secondary bg-secondary-fixed p-1.5 rounded-md text-[20px]">${kindIcon}</span>
                        <div>
                            <div class="font-body-md text-on-surface font-medium leading-tight">${escapeHtml(s.topic || s.kind.charAt(0).toUpperCase() + s.kind.slice(1))}</div>
                            <div class="font-label-sm text-on-surface-variant mt-[2px] uppercase tracking-wider">${s.kind}</div>
                        </div>
                    </div>
                    <div class="col-span-3 font-body-sm text-on-surface">${when}</div>
                    <div class="col-span-2 font-body-sm text-on-surface">${mins} min</div>
                    <div class="col-span-2 text-right">
                        <span class="inline-flex items-center gap-1 bg-surface-container px-2 py-1 rounded text-primary font-label-md text-label-md">
                            ${impactTxt} <span class="material-symbols-outlined text-[14px]">${trendIcon}</span>
                        </span>
                    </div>
                </div>`;
            }).join("");
        } catch {}
    }

    async function loadTopics() {
        try {
            const r = await api.progress();
            const root = $("topic-mastery");
            if (!r.topics.length) {
                root.innerHTML = `<p class="font-body-sm text-on-surface-variant">No topics tracked yet. Run a quiz to start scoring mastery per topic.</p>`;
                return;
            }
            root.innerHTML = r.topics.map(t => {
                const pct = Math.round((t.mastery_score || 0) * 100);
                return `
                <div class="grid grid-cols-12 gap-md items-center">
                    <div class="col-span-3 font-body-md text-on-surface font-medium truncate">${escapeHtml(t.name)}</div>
                    <div class="col-span-7">
                        <div class="h-2 w-full bg-tertiary-fixed rounded-full overflow-hidden">
                            <div class="bg-secondary h-full rounded-full" style="width:${pct}%"></div>
                        </div>
                    </div>
                    <div class="col-span-1 text-right font-label-md text-label-md text-on-surface">${pct}%</div>
                    <div class="col-span-1 text-right font-label-sm text-on-surface-variant">${t.card_count} cards</div>
                </div>`;
            }).join("");
        } catch {}
    }

    async function loadHealth() {
        try {
            const h = await api.health();
            $("h-status-pill").textContent = h.model_loaded ? "Healthy" : "Offline";
            $("h-status-pill").className = `font-label-md text-label-md px-2 py-[2px] rounded ${h.model_loaded ? "bg-success-container text-success" : "bg-error-container text-on-error-container"}`;
            $("h-status-dot").className = `w-2 h-2 rounded-full ${h.model_loaded ? "bg-success" : "bg-error"}`;
            $("h-model").textContent = h.model_name || "—";
            $("h-chunks").textContent = (h.index_size ?? 0).toLocaleString();
            $("h-cards").textContent = (h.db_cards ?? 0).toLocaleString();
            $("h-sync").textContent = new Date().toLocaleTimeString();
        } catch {}
    }

    document.addEventListener("DOMContentLoaded", () => {
        $("refresh-dash").addEventListener("click", loadAll);
        $("sessions-refresh").addEventListener("click", loadSessions);
        $("heatmap-range").addEventListener("change", loadHeatmap);
        $("h-diagnostics").addEventListener("click", async () => {
            const btn = $("h-diagnostics");
            btn.disabled = true;
            const o = btn.innerHTML;
            btn.innerHTML = `Running… <span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>`;
            await loadHealth();
            toast("Diagnostics complete.", "success");
            btn.disabled = false;
            btn.innerHTML = o;
        });
        document.addEventListener("sc:new-session", loadAll);
        loadAll();
    });
})();
