// Quiz page wiring.

(function () {
    const state = {
        session: null,
        questions: [],
        answers: {},          // qid -> letter ("A"|"B"|"C"|"D") or text
        flagged: new Set(),
        idx: 0,
        startedAt: null,
        timeLimit: 300,
        difficulty: "Medium",
        timerId: null,
        hints: {},            // qid -> string
    };

    // ── DOM ─────────────────────────────────────────────
    const $ = id => document.getElementById(id);

    // ── Start view ──────────────────────────────────────

    function wireStart() {
        $("quiz-topics").addEventListener("input", () => {
            $("quiz-start-btn").disabled = !$("quiz-topics").value.trim();
        });
        $("quiz-n").addEventListener("input", e => $("quiz-n-val").textContent = e.target.value);
        $("quiz-time").addEventListener("input", e => $("quiz-time-val").textContent = e.target.value);

        $("quiz-start-btn").addEventListener("click", async () => {
            const topicsRaw = $("quiz-topics").value;
            const topics = topicsRaw.split(",").map(s => s.trim()).filter(Boolean);
            if (!topics.length) return;
            const n = parseInt($("quiz-n").value, 10);
            const t = parseInt($("quiz-time").value, 10);
            const diff = $("quiz-difficulty").value;

            const btn = $("quiz-start-btn");
            btn.disabled = true;
            const original = btn.innerHTML;
            btn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span> Generating…`;
            try {
                const session = await api.quizStart({
                    topics, n_questions: n, time_limit_seconds: t,
                });
                if (!session.questions || !session.questions.length) {
                    toast("No questions could be generated. Upload more material on these topics.", "error");
                    return;
                }
                state.session = session;
                state.questions = session.questions;
                state.answers = {};
                state.flagged = new Set();
                state.idx = 0;
                state.startedAt = Date.now();
                state.timeLimit = session.time_limit_seconds;
                state.difficulty = diff;
                state.hints = {};

                $("quiz-start").classList.add("hidden");
                $("quiz-result").classList.add("hidden");
                $("quiz-active").classList.remove("hidden");
                $("quiz-topic-label").textContent = `Topics: ${topics.join(", ")}`;
                $("quiz-difficulty-label").textContent = `${diff} Difficulty`;
                renderQuestion();
                renderJumpGrid();
                startTimer();
            } catch {} finally {
                btn.disabled = !$("quiz-topics").value.trim();
                btn.innerHTML = original;
            }
        });
    }

    // ── Question view ───────────────────────────────────

    function renderJumpGrid() {
        const root = $("quiz-question-grid");
        root.innerHTML = state.questions.map((q, i) => {
            const answered = state.answers[q.id] !== undefined && state.answers[q.id] !== "";
            const flagged = state.flagged.has(q.id);
            const active = i === state.idx;
            const base = "h-9 rounded font-label-md text-label-md flex items-center justify-center cursor-pointer transition-colors border";
            const cls = active
                ? "bg-primary text-on-primary border-primary"
                : answered
                ? "bg-secondary-fixed text-primary border-secondary-fixed-dim hover:bg-secondary-container"
                : "bg-surface-bright text-on-surface border-outline-variant hover:border-primary";
            const dot = flagged ? `<span class="material-symbols-outlined text-[12px] ml-[2px] text-error">flag</span>` : "";
            return `<button data-idx="${i}" class="${base} ${cls}">${i + 1}${dot}</button>`;
        }).join("");
        root.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
            state.idx = parseInt(b.dataset.idx, 10);
            renderQuestion();
            renderJumpGrid();
        }));
    }

    function renderQuestion() {
        const q = state.questions[state.idx];
        $("quiz-progress-label").textContent = `Question ${state.idx + 1} of ${state.questions.length}`;
        $("quiz-progress-bar").style.width = `${((state.idx + 1) / state.questions.length) * 100}%`;
        $("quiz-question-text").textContent = q.text;

        // Options
        const opts = $("quiz-options");
        const selected = state.answers[q.id];
        if (q.options && q.options.length) {
            opts.innerHTML = q.options.map((opt, i) => {
                const letter = "ABCD"[i];
                const sel = selected === letter;
                return `
                <label data-letter="${letter}" class="group opt-item flex items-start gap-sm p-sm rounded border ${sel ? "opt-selected" : "border-outline-variant"} hover:bg-surface-container-low hover:border-outline cursor-pointer transition-colors">
                    <div class="mt-1 shrink-0 w-5 h-5 rounded-full border ${sel ? "border-2 border-secondary" : "border-outline-variant group-hover:border-secondary"} flex items-center justify-center">
                        <div class="opt-dot w-2.5 h-2.5 rounded-full ${sel ? "bg-secondary" : "bg-transparent"}"></div>
                    </div>
                    <span class="font-body-md text-on-background">${escapeHtml(opt)}</span>
                </label>`;
            }).join("");
            opts.querySelectorAll(".opt-item").forEach(el => {
                el.addEventListener("click", () => {
                    state.answers[q.id] = el.dataset.letter;
                    renderQuestion();
                    renderJumpGrid();
                    updateStats();
                });
            });
        } else {
            opts.innerHTML = `
                <textarea data-qid="${q.id}" placeholder="Your answer…" rows="4"
                    class="w-full border border-outline-variant rounded-lg p-sm font-body-md bg-surface-bright focus:outline-none focus:border-secondary focus:border-2"
                >${escapeHtml(selected || "")}</textarea>`;
            opts.querySelector("textarea").addEventListener("input", e => {
                state.answers[q.id] = e.target.value;
                updateStats();
            });
        }

        // Hint
        const hint = state.hints[q.id];
        if (hint) {
            $("quiz-hint-box").classList.remove("hidden");
            $("quiz-hint-text").textContent = hint;
        } else {
            $("quiz-hint-box").classList.add("hidden");
        }

        // Flag button state
        const flagged = state.flagged.has(q.id);
        $("quiz-flag-icon").textContent = flagged ? "flag_2" : "flag";
        $("quiz-flag-icon").classList.toggle("icon-fill", flagged);
        $("quiz-flag-label").textContent = flagged ? "Flagged" : "Flag for Review";

        // Nav buttons
        $("quiz-prev").disabled = state.idx === 0;
        const last = state.idx === state.questions.length - 1;
        $("quiz-next").classList.toggle("hidden", last);
        $("quiz-submit").classList.toggle("hidden", !last);

        updateStats();
    }

    function updateStats() {
        const answered = Object.values(state.answers).filter(v => v && String(v).trim()).length;
        $("quiz-answered").textContent = `${answered} / ${state.questions.length}`;
        $("quiz-flagged-count").textContent = state.flagged.size;
    }

    function startTimer() {
        if (state.timerId) clearInterval(state.timerId);
        const tick = () => {
            const elapsed = Math.floor((Date.now() - state.startedAt) / 1000);
            const left = Math.max(0, state.timeLimit - elapsed);
            $("quiz-time-elapsed").textContent = fmtTime(elapsed);
            $("quiz-time-remaining").textContent = fmtTime(left);
            $("quiz-time-remaining").style.color = left < 30 ? "#ba1a1a" : "";
            if (left === 0) {
                clearInterval(state.timerId);
                toast("Time's up — submitting…", "error");
                submitQuiz();
            }
        };
        tick();
        state.timerId = setInterval(tick, 1000);
    }

    function fmtTime(s) {
        const m = Math.floor(s / 60).toString().padStart(2, "0");
        const ss = (s % 60).toString().padStart(2, "0");
        return `${m}:${ss}`;
    }

    function wireActive() {
        $("quiz-prev").addEventListener("click", () => {
            state.idx = Math.max(0, state.idx - 1);
            renderQuestion(); renderJumpGrid();
        });
        $("quiz-next").addEventListener("click", () => {
            state.idx = Math.min(state.questions.length - 1, state.idx + 1);
            renderQuestion(); renderJumpGrid();
        });
        $("quiz-submit").addEventListener("click", submitQuiz);
        $("quiz-cancel").addEventListener("click", () => {
            if (confirm("Cancel quiz? Progress will be lost.")) {
                resetToStart();
            }
        });

        $("quiz-flag-btn").addEventListener("click", async () => {
            const q = state.questions[state.idx];
            const newState = !state.flagged.has(q.id);
            if (newState) state.flagged.add(q.id); else state.flagged.delete(q.id);
            try {
                await api.quizFlag({
                    session_id: state.session.session_id,
                    question_id: q.id, flagged: newState,
                });
            } catch {}
            renderQuestion(); renderJumpGrid();
        });

        $("quiz-hint-btn").addEventListener("click", async () => {
            const q = state.questions[state.idx];
            if (state.hints[q.id]) return;  // already loaded
            const btn = $("quiz-hint-btn");
            btn.disabled = true;
            const o = btn.innerHTML;
            btn.innerHTML = `<span class="material-symbols-outlined text-sm animate-spin">progress_activity</span> Thinking…`;
            try {
                const r = await api.quizHint({
                    question_id: q.id, session_id: state.session.session_id,
                });
                state.hints[q.id] = r.hint;
                renderQuestion();
            } catch {} finally {
                btn.disabled = false;
                btn.innerHTML = o;
            }
        });
    }

    async function submitQuiz() {
        if (state.timerId) clearInterval(state.timerId);
        const answers = Object.entries(state.answers)
            .filter(([, v]) => v && String(v).trim())
            .map(([qid, v]) => ({ question_id: qid, answer: String(v) }));
        try {
            const r = await api.quizSubmit({
                session_id: state.session.session_id,
                answers,
            });
            showResult(r);
        } catch {}
    }

    function showResult(r) {
        $("quiz-active").classList.add("hidden");
        $("quiz-result").classList.remove("hidden");
        $("result-score").textContent = `${(r.score * 100).toFixed(0)}%`;
        const correct = r.breakdown.filter(b => b.correct).length;
        $("result-correct").textContent = `${correct}/${r.breakdown.length}`;
        $("result-weak").innerHTML = r.weak_topics.length
            ? r.weak_topics.map(t => `<span class="bg-error-container text-on-error-container font-label-sm text-label-sm px-xs py-[2px] rounded mr-xs">${escapeHtml(t)}</span>`).join("")
            : `<span class="text-success">No weak topics — well done.</span>`;
        $("result-breakdown").innerHTML = r.breakdown.map((b, i) => {
            const q = state.questions.find(qq => qq.id === b.question_id);
            const icon = b.correct ? `<span class="material-symbols-outlined text-success">check_circle</span>` : `<span class="material-symbols-outlined text-error">cancel</span>`;
            return `
                <div class="flex gap-sm p-sm border border-outline-variant rounded bg-surface-bright">
                    ${icon}
                    <div class="flex-1">
                        <div class="font-body-md text-on-surface">${escapeHtml(q ? q.text : "")}</div>
                        <div class="font-body-sm text-on-surface-variant mt-xs">${escapeHtml(b.explanation || "")}</div>
                    </div>
                </div>`;
        }).join("");
    }

    function resetToStart() {
        if (state.timerId) clearInterval(state.timerId);
        state.session = null;
        state.questions = [];
        state.answers = {};
        state.flagged = new Set();
        state.idx = 0;
        state.hints = {};
        $("quiz-active").classList.add("hidden");
        $("quiz-result").classList.add("hidden");
        $("quiz-start").classList.remove("hidden");
    }

    document.addEventListener("DOMContentLoaded", () => {
        wireStart();
        wireActive();
        $("result-again").addEventListener("click", resetToStart);
        document.addEventListener("sc:new-session", resetToStart);
    });
})();
