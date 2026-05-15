// Progress page — targets the Stitch dashboard DOM and replaces mock values.

(function () {
    function findCardByLabel(label) {
        const re = new RegExp(`\\b${label}\\b`, "i");
        for (const c of document.querySelectorAll(".bg-surface-container-lowest, .bg-surface-bright")) {
            if (re.test(c.textContent || "")) return c;
        }
        return null;
    }

    async function loadAll() {
        const [dash, heat, sess, prog, health] = await Promise.all([
            api.dashboard().catch(() => null),
            api.heatmap(30).catch(() => null),
            api.sessions(8).catch(() => null),
            api.progress().catch(() => null),
            api.health().catch(() => null),
        ]);

        if (dash) renderMetrics(dash);
        if (health) renderHealth(health);
        if (heat) renderHeatmap(heat);
        if (sess) renderSessions(sess);
        if (prog) renderTopics(prog);
    }

    function renderMetrics(d) {
        // Card 1: Study Progress
        const card1 = findCardByLabel("Study Progress");
        if (card1) {
            const main = card1.querySelector(".font-headline-xl");
            if (main) {
                main.innerHTML = `${(d.study_hours_total || 0).toFixed(1)}<span class="text-[20px] font-medium text-on-surface-variant ml-1">hrs</span>`;
            }
            const sub = card1.querySelector("p.font-body-sm");
            if (sub) sub.innerHTML = `+${(d.study_hours_week || 0).toFixed(1)} hrs this week`;
            // Weekly goal bar + label
            const bar = card1.querySelector(".bg-secondary.rounded-full");
            if (bar) bar.style.width = `${Math.min(100, d.weekly_goal_percent || 0)}%`;
            const pctSpan = card1.querySelectorAll(".flex.justify-between span");
            if (pctSpan && pctSpan[1]) pctSpan[1].textContent = `${Math.round(d.weekly_goal_percent || 0)}%`;
        }

        // Card 2: Flashcard Mastery
        const card2 = findCardByLabel("Flashcard Mastery");
        if (card2) {
            const main = card2.querySelector(".font-headline-xl");
            if (main) {
                main.innerHTML = `${Math.round((d.flashcard_retention || 0) * 100)}<span class="text-[20px] font-medium text-on-surface-variant ml-1">%</span>`;
            }
            // The two stat tiles at the bottom
            const tiles = card2.querySelectorAll(".bg-surface.rounded-lg");
            if (tiles[0]) {
                const v = tiles[0].querySelector(".font-label-md");
                if (v) v.textContent = `${d.review_due_count || 0} cards`;
            }
            if (tiles[1]) {
                const v = tiles[1].querySelector(".font-label-md");
                if (v) v.textContent = `${d.mastered_count || 0} cards`;
            }
        }

        // Card 3: Quiz Performance
        const card3 = findCardByLabel("Quiz Performance");
        if (card3) {
            const main = card3.querySelector(".font-headline-xl");
            if (main) {
                main.innerHTML = `${d.quiz_letter_grade || "—"}<span class="text-[20px] font-medium text-on-surface-variant ml-2">Avg</span>`;
            }
            const sub = card3.querySelector("p.font-body-sm");
            if (sub) {
                sub.textContent = d.quiz_avg_score != null
                    ? `Avg ${Math.round(d.quiz_avg_score * 100)}% across last 12 quizzes.`
                    : "Take a quiz to start tracking.";
            }
        }
    }

    function renderHealth(h) {
        const card = findCardByLabel("Model & Index Health") || findCardByLabel("Index Status");
        if (!card) return;
        const rows = card.querySelectorAll(".flex.items-center.justify-between");
        // Row 0: Index Status (pill on right)
        if (rows[0]) {
            const right = rows[0].lastElementChild;
            if (right) {
                right.textContent = h.model_loaded ? "Healthy" : "Offline";
                right.classList.remove("bg-surface-container", "text-primary", "bg-error-container", "text-on-error-container");
                if (h.model_loaded) right.classList.add("bg-secondary-fixed", "text-on-secondary-container");
                else right.classList.add("bg-error-container", "text-on-error-container");
            }
            // Status dot
            const dot = rows[0].querySelector(".w-2.h-2.rounded-full");
            if (dot) dot.style.background = h.model_loaded ? "#2e7d32" : "#ba1a1a";
        }
        if (rows[1]) {
            const v = rows[1].lastElementChild;
            if (v) v.textContent = h.model_name || "—";
        }
        if (rows[2]) {
            const v = rows[2].lastElementChild;
            if (v) v.textContent = (h.index_size || 0).toLocaleString();
        }
        if (rows[3]) {
            const v = rows[3].lastElementChild;
            if (v) v.textContent = "just now";
        }
        const diagBtn = Array.from(card.querySelectorAll("button")).find(b => /Run Diagnostics/i.test(b.textContent || ""));
        if (diagBtn && !diagBtn.dataset.wired) {
            diagBtn.dataset.wired = "1";
            diagBtn.addEventListener("click", async () => {
                diagBtn.disabled = true;
                const o = diagBtn.innerHTML;
                diagBtn.innerHTML = `Running… <span class="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>`;
                try {
                    const fresh = await api.health();
                    renderHealth(fresh);
                    toast("Diagnostics complete.", "success");
                } catch {} finally {
                    diagBtn.disabled = false;
                    diagBtn.innerHTML = o;
                }
            });
        }
    }

    function renderHeatmap(r) {
        // Find Activity Intensity card
        const card = findCardByLabel("Activity Intensity");
        if (!card) return;
        const chart = card.querySelector(".h-48");
        if (!chart) return;
        const days = r.days || [];
        if (!days.length) {
            chart.innerHTML = `<p class="font-body-sm text-on-surface-variant w-full text-center self-center">No activity yet.</p>`;
            return;
        }
        const max = Math.max(...days.map(d => d.count), 1);
        chart.innerHTML = days.map(d => {
            const h = Math.max(4, Math.round((d.count / max) * 100));
            const color = d.count === 0 ? "bg-surface-container" : (h > 70 ? "bg-secondary" : "bg-secondary-container");
            return `<div class="w-full ${color} rounded-t hover:bg-primary transition-colors relative group" style="height:${h}%">
                        <div class="absolute -top-10 left-1/2 -translate-x-1/2 bg-inverse-surface text-inverse-on-surface font-label-sm text-label-sm px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">${d.day}: ${d.count}</div>
                    </div>`;
        }).join("");
        // Date labels
        const labels = card.querySelectorAll(".flex.justify-between.text-on-surface-variant span");
        if (labels.length >= 2) {
            labels[0].textContent = days[0].day;
            labels[labels.length - 1].textContent = days[days.length - 1].day;
        }
    }

    function renderSessions(r) {
        // Recent Study Sessions card — last col-span-12 card
        const card = findCardByLabel("Recent Study Sessions");
        if (!card) return;
        const listContainer = card.querySelector(".divide-y") || card.querySelector(".w-full > .divide-y") || card;
        let list = card.querySelector(".divide-y.divide-surface-variant") || card.querySelector(".divide-y");
        if (!list) {
            // fall back: container after the table header
            const headers = card.querySelector(".grid-cols-12.gap-4.px-md.py-sm");
            list = headers ? headers.nextElementSibling : null;
        }
        if (!list) return;
        const sessions = r.sessions || [];
        if (!sessions.length) {
            list.innerHTML = `<div class="p-md text-on-surface-variant font-body-sm">No sessions recorded yet.</div>`;
            return;
        }
        list.innerHTML = sessions.map(s => {
            let when = s.started_at;
            try {
                when = new Date(s.started_at.replace(" ", "T") + "Z").toLocaleString(undefined, {
                    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                });
            } catch {}
            const mins = Math.max(0, Math.round(s.duration_seconds / 60));
            const impact = s.impact_score;
            const impactTxt = impact == null ? "—" : (impact >= 0 ? `+${Math.round(impact)}` : Math.round(impact));
            const trendIcon = impact == null ? "trending_flat" : (impact >= 0 ? "trending_up" : "trending_down");
            const kindIcon = ({ study: "menu_book", quiz: "quiz", flashcards: "style" })[s.kind] || "circle";
            return `
                <div class="grid grid-cols-12 gap-4 px-md py-3 items-center hover:bg-surface-container-low transition-colors duration-150 cursor-pointer">
                    <div class="col-span-5 flex items-center gap-3">
                        <span class="material-symbols-outlined text-secondary bg-secondary-fixed p-1.5 rounded-md text-[20px]">${kindIcon}</span>
                        <div>
                            <div class="font-body-md text-body-md text-on-surface font-medium leading-tight">${escapeHtml(s.topic || s.kind.charAt(0).toUpperCase() + s.kind.slice(1))}</div>
                            <div class="font-label-sm text-label-sm text-on-surface-variant mt-0.5 uppercase tracking-wider">${s.kind}</div>
                        </div>
                    </div>
                    <div class="col-span-3 font-body-sm text-body-sm text-on-surface">${when}</div>
                    <div class="col-span-2 font-body-sm text-body-sm text-on-surface">${mins} min</div>
                    <div class="col-span-2 text-right">
                        <span class="inline-flex items-center gap-1 bg-surface-container px-2 py-1 rounded text-primary font-label-md text-label-md">
                            ${impactTxt} <span class="material-symbols-outlined text-[14px]">${trendIcon}</span>
                        </span>
                    </div>
                </div>`;
        }).join("");
        // Wire "View All" link to refresh
        const viewAll = Array.from(card.querySelectorAll("button")).find(b => /View All/i.test(b.textContent || ""));
        if (viewAll && !viewAll.dataset.wired) {
            viewAll.dataset.wired = "1";
            viewAll.addEventListener("click", e => { e.preventDefault(); loadAll(); });
        }
    }

    function renderTopics(p) {
        // The Stitch design doesn't have a dedicated topic-mastery card;
        // surface a compact list under recent sessions if there are topics.
        if (!p.topics || !p.topics.length) return;
        const sessionsCard = findCardByLabel("Recent Study Sessions");
        if (!sessionsCard || sessionsCard.querySelector(".sc-topic-mastery")) return;
        const wrap = document.createElement("div");
        wrap.className = "sc-topic-mastery p-md border-t border-outline-variant";
        wrap.innerHTML = `
            <div class="flex items-center justify-between mb-sm">
                <h3 class="font-label-md text-label-md text-primary m-0">Topic Mastery</h3>
                <span class="font-label-sm text-on-surface-variant">${p.topics.length} tracked</span>
            </div>
            <div class="flex flex-col gap-xs">
                ${p.topics.slice(0, 10).map(t => {
                    const pct = Math.round((t.mastery_score || 0) * 100);
                    return `
                        <div class="grid grid-cols-12 gap-md items-center">
                            <div class="col-span-3 font-body-md text-on-surface truncate">${escapeHtml(t.name)}</div>
                            <div class="col-span-7"><div class="h-2 w-full bg-tertiary-fixed rounded-full overflow-hidden"><div class="bg-secondary h-full rounded-full" style="width:${pct}%"></div></div></div>
                            <div class="col-span-1 text-right font-label-md text-label-md text-on-surface">${pct}%</div>
                            <div class="col-span-1 text-right font-label-sm text-on-surface-variant">${t.card_count} cards</div>
                        </div>`;
                }).join("")}
            </div>
        `;
        sessionsCard.appendChild(wrap);
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadAll();
        document.addEventListener("sc:new-session", loadAll);
        document.addEventListener("sc:index-changed", loadAll);
        // Wire heatmap range select
        const sel = (() => {
            for (const s of document.querySelectorAll("select")) {
                if (/Last 30 Days|This Week/i.test(s.textContent || "")) return s;
            }
            return null;
        })();
        if (sel) sel.addEventListener("change", async () => {
            const map = { "Last 30 Days": 30, "This Week": 7 };
            const days = map[sel.value] || (sel.value.match(/\d+/) ? parseInt(sel.value, 10) : 30);
            const heat = await api.heatmap(days).catch(() => null);
            if (heat) renderHeatmap(heat);
        });
    });
})();
