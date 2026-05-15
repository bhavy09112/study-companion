// Quiz page — targets the Stitch quiz DOM. Replaces the question card body
// based on state (start / active / result). Side panel updates session metrics.

(function () {
    const state = {
        session: null,
        questions: [],
        answers: {},        // qid -> "A"|"B"|"C"|"D"
        flagged: new Set(),
        idx: 0,
        startedAt: null,
        timeLimit: 300,
        difficulty: "Medium",
        timerId: null,
        hintText: "",
    };

    // ── Locate Stitch panels ───────────────────────────

    const main = document.querySelector("main");
    // Main quiz card (col-span-8)
    const quizCard = main ? main.querySelector(".col-span-8") : null;
    // Side panel container (col-span-4)
    const sidePanel = main ? main.querySelector(".col-span-4") : null;
    // Page header (h2 + topic <p>)
    const pageH2 = main ? main.querySelector("h2") : null;
    const pageTopicP = pageH2 ? pageH2.parentElement.querySelector("p") : null;

    // Session Metrics + AI Hint cards inside the side panel — kept; we just update fields.
    // Inside side panel:
    //   First card contains "Session Metrics" + 3 rows of label / value.
    //   Second card contains "AI Context Hint" + paragraph.

    // ── Helpers ────────────────────────────────────────

    function fmtTime(s) {
        const m = Math.floor(s / 60).toString().padStart(2, "0");
        const ss = (s % 60).toString().padStart(2, "0");
        return `${m}:${ss}`;
    }

    function setHeader(topics) {
        if (pageTopicP) pageTopicP.textContent = topics.length ? `Topic: ${topics.join(", ")}` : "Generate quiz questions from your indexed material.";
    }

    // ── Side panel updates ─────────────────────────────

    function updateSidePanel() {
        if (!sidePanel) return;
        const elapsed = state.startedAt ? Math.floor((Date.now() - state.startedAt) / 1000) : 0;
        const left = Math.max(0, state.timeLimit - elapsed);
        const answered = Object.values(state.answers).filter(v => v && String(v).trim()).length;
        const acc = answered ? Math.round((answered / state.questions.length) * 100) : 0;

        // Replace the first card's values
        const metricsCard = sidePanel.querySelector(".bg-surface-container-lowest");
        if (metricsCard) {
            // Walk rows and update values
            const rows = metricsCard.querySelectorAll(".flex.justify-between");
            if (rows[0]) {
                const v = rows[0].querySelectorAll("span")[1];
                if (v) v.textContent = fmtTime(elapsed);
            }
            if (rows[1]) {
                const v = rows[1].querySelectorAll("span")[1];
                if (v) { v.textContent = `${answered}/${state.questions.length}`; v.classList.remove("text-secondary"); v.classList.add("text-primary"); }
            }
            if (rows[2]) {
                const v = rows[2].querySelectorAll("span")[1];
                if (v) { v.textContent = fmtTime(left); v.style.color = left < 30 ? "#ba1a1a" : ""; }
            }
        }
        // Hint card update
        const hintCard = sidePanel.querySelectorAll(".bg-surface-bright")[0];
        if (hintCard) {
            const p = hintCard.querySelector("p");
            if (p) p.textContent = state.hintText || "Tap “Hint” on a question for a Socratic nudge from the AI tutor — without spoiling the answer.";
        }
    }

    // ── Start-state form ───────────────────────────────

    function renderStart() {
        if (!quizCard) return;
        quizCard.innerHTML = `
            <h3 class="font-headline-lg-mobile text-headline-lg-mobile font-bold text-on-background mb-md">Start a new quiz</h3>
            <p class="font-body-md text-on-surface-variant mb-md">Generate multiple-choice questions grounded in your indexed material.</p>

            <div class="flex flex-col gap-md">
                <div>
                    <label class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider block mb-xs">Topics (comma-separated)</label>
                    <input id="q-topics" type="text" placeholder="photosynthesis, cellular respiration"
                           class="w-full border border-outline-variant rounded-lg py-[10px] px-sm font-body-md bg-surface-bright focus:outline-none focus:border-secondary focus:border-2" />
                </div>
                <div class="grid grid-cols-3 gap-md">
                    <div>
                        <label class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex justify-between">
                            Questions <span id="q-n-val" class="text-primary font-bold">5</span>
                        </label>
                        <input id="q-n" type="range" min="1" max="20" value="5" class="mt-xs w-full" />
                    </div>
                    <div>
                        <label class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider flex justify-between">
                            Time (sec) <span id="q-time-val" class="text-primary font-bold">300</span>
                        </label>
                        <input id="q-time" type="range" min="60" max="1800" step="30" value="300" class="mt-xs w-full" />
                    </div>
                    <div>
                        <label class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider block">Difficulty</label>
                        <select id="q-diff" class="w-full mt-xs border border-outline-variant rounded-lg py-[10px] pl-sm pr-10 font-body-md bg-surface-bright cursor-pointer">
                            <option>Easy</option><option selected>Medium</option><option>Hard</option>
                        </select>
                    </div>
                </div>
                <button id="q-start" disabled class="bg-primary text-on-primary font-label-md text-label-md rounded py-sm px-lg hover:bg-on-primary-fixed-variant transition-colors flex items-center justify-center gap-xs self-start disabled:opacity-50 disabled:cursor-not-allowed">
                    <span class="material-symbols-outlined">rocket_launch</span> Start Quiz
                </button>
            </div>
        `;
        // Wire form
        const topics = quizCard.querySelector("#q-topics");
        const startBtn = quizCard.querySelector("#q-start");
        topics.addEventListener("input", () => startBtn.disabled = !topics.value.trim());
        quizCard.querySelector("#q-n").addEventListener("input", e => quizCard.querySelector("#q-n-val").textContent = e.target.value);
        quizCard.querySelector("#q-time").addEventListener("input", e => quizCard.querySelector("#q-time-val").textContent = e.target.value);
        startBtn.addEventListener("click", async () => {
            const ts = topics.value.split(",").map(s => s.trim()).filter(Boolean);
            const n = parseInt(quizCard.querySelector("#q-n").value, 10);
            const t = parseInt(quizCard.querySelector("#q-time").value, 10);
            state.difficulty = quizCard.querySelector("#q-diff").value;
            startBtn.disabled = true;
            const o = startBtn.innerHTML;
            startBtn.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> Generating…`;
            try {
                const s = await api.quizStart({ topics: ts, n_questions: n, time_limit_seconds: t });
                if (!s.questions || !s.questions.length) {
                    toast("No questions could be generated. Upload more material.", "error");
                    return;
                }
                state.session = s; state.questions = s.questions; state.idx = 0;
                state.answers = {}; state.flagged = new Set(); state.hintText = "";
                state.timeLimit = s.time_limit_seconds; state.startedAt = Date.now();
                setHeader(ts);
                renderQuestion();
                startTimer();
            } catch {} finally {
                startBtn.disabled = false;
                startBtn.innerHTML = o;
            }
        });
        updateSidePanel();
    }

    // ── Active question ────────────────────────────────

    function renderQuestion() {
        if (!quizCard || !state.questions.length) return;
        const q = state.questions[state.idx];
        const selected = state.answers[q.id];
        const flagged = state.flagged.has(q.id);
        const isLast = state.idx === state.questions.length - 1;
        const progress = ((state.idx + 1) / state.questions.length) * 100;

        const optsHtml = (q.options || []).map((opt, i) => {
            const letter = "ABCD"[i];
            const sel = selected === letter;
            return `
                <label data-letter="${letter}" class="opt-item group flex items-start gap-sm p-sm rounded border ${sel ? "border-2 border-secondary bg-surface-bright" : "border-outline-variant"} hover:bg-surface-container-low hover:border-outline cursor-pointer transition-colors">
                    <div class="mt-1 shrink-0 w-5 h-5 rounded-full border ${sel ? "border-2 border-secondary" : "border-outline-variant group-hover:border-secondary"} flex items-center justify-center">
                        <div class="w-2.5 h-2.5 rounded-full ${sel ? "bg-secondary" : "bg-transparent"}"></div>
                    </div>
                    <span class="font-body-md text-body-md text-on-background"><strong>${letter})</strong> ${escapeHtml(opt)}</span>
                </label>`;
        }).join("");

        quizCard.innerHTML = `
            <div class="flex justify-between items-center mb-md">
                <span class="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">Question ${state.idx+1} of ${state.questions.length}</span>
                <span class="font-label-sm text-label-sm text-secondary font-bold">${state.difficulty} Difficulty</span>
            </div>
            <div class="w-full h-2 bg-tertiary-fixed rounded-full mb-xl overflow-hidden">
                <div class="h-full bg-secondary rounded-full transition-all" style="width:${progress}%"></div>
            </div>
            <div class="mb-xl">
                <h3 class="font-headline-lg-mobile text-headline-lg-mobile font-bold text-on-background leading-relaxed">${escapeHtml(q.text)}</h3>
                ${q.topic ? `<p class="font-label-sm text-label-sm text-on-surface-variant mt-xs uppercase tracking-wider">${escapeHtml(q.topic)}</p>` : ""}
            </div>
            <div class="flex flex-col gap-sm mb-xl">
                ${optsHtml}
            </div>
            <div class="flex justify-between items-center mt-auto pt-md border-t border-outline-variant">
                <div class="flex gap-xs">
                    <button id="q-hint" class="text-on-surface-variant font-label-md text-label-md px-sm py-xs hover:bg-surface-container-low rounded transition-colors flex items-center gap-xs border border-outline-variant">
                        <span class="material-symbols-outlined text-sm">lightbulb</span> Hint
                    </button>
                    <button id="q-flag" class="text-secondary font-label-md text-label-md px-sm py-xs hover:bg-surface-container-low rounded transition-colors flex items-center gap-xs border border-outline-variant">
                        <span class="material-symbols-outlined text-sm ${flagged ? "filled" : ""}" ${flagged ? 'style="font-variation-settings:\'FILL\' 1;"' : ""}>flag</span> ${flagged ? "Flagged" : "Flag for Review"}
                    </button>
                </div>
                <div class="flex gap-xs">
                    <button id="q-prev" ${state.idx === 0 ? "disabled" : ""} class="text-primary border border-outline-variant font-label-md text-label-md py-xs px-sm rounded hover:bg-surface-container-low transition-colors flex items-center gap-xs disabled:opacity-40 disabled:cursor-not-allowed">
                        <span class="material-symbols-outlined text-sm">arrow_back</span> Prev
                    </button>
                    ${isLast
                        ? `<button id="q-submit" class="bg-primary text-on-primary font-label-md text-label-md py-sm px-lg rounded hover:bg-on-primary-fixed-variant transition-colors flex items-center gap-xs shadow-sm">
                                Submit Answers <span class="material-symbols-outlined text-sm">check_circle</span>
                           </button>`
                        : `<button id="q-next" class="bg-primary text-on-primary font-label-md text-label-md py-sm px-lg rounded hover:bg-on-primary-fixed-variant transition-colors flex items-center gap-xs shadow-sm">
                                Next <span class="material-symbols-outlined text-sm">arrow_forward</span>
                           </button>`}
                </div>
            </div>
        `;

        // Wire options
        quizCard.querySelectorAll(".opt-item").forEach(el => {
            el.addEventListener("click", () => {
                state.answers[q.id] = el.dataset.letter;
                renderQuestion();
                updateSidePanel();
            });
        });
        // Wire footer buttons
        const prev = quizCard.querySelector("#q-prev");
        const next = quizCard.querySelector("#q-next");
        const submit = quizCard.querySelector("#q-submit");
        const hint = quizCard.querySelector("#q-hint");
        const flagBtn = quizCard.querySelector("#q-flag");
        if (prev) prev.addEventListener("click", () => { state.idx--; state.hintText = ""; renderQuestion(); updateSidePanel(); });
        if (next) next.addEventListener("click", () => { state.idx++; state.hintText = ""; renderQuestion(); updateSidePanel(); });
        if (submit) submit.addEventListener("click", submitQuiz);
        if (hint) hint.addEventListener("click", async () => {
            hint.disabled = true;
            const o = hint.innerHTML;
            hint.innerHTML = `<span class="material-symbols-outlined text-sm animate-spin">progress_activity</span> Thinking…`;
            try {
                const r = await api.quizHint({ question_id: q.id, session_id: state.session.session_id });
                state.hintText = r.hint;
                updateSidePanel();
            } catch {} finally {
                hint.disabled = false;
                hint.innerHTML = o;
            }
        });
        if (flagBtn) flagBtn.addEventListener("click", async () => {
            const newState = !state.flagged.has(q.id);
            if (newState) state.flagged.add(q.id); else state.flagged.delete(q.id);
            try { await api.quizFlag({ session_id: state.session.session_id, question_id: q.id, flagged: newState }); } catch {}
            renderQuestion();
        });

        updateSidePanel();
    }

    // ── Timer ──────────────────────────────────────────

    function startTimer() {
        if (state.timerId) clearInterval(state.timerId);
        state.timerId = setInterval(() => {
            updateSidePanel();
            const elapsed = Math.floor((Date.now() - state.startedAt) / 1000);
            if (elapsed >= state.timeLimit) {
                clearInterval(state.timerId);
                toast("Time's up — submitting.", "error");
                submitQuiz();
            }
        }, 1000);
    }

    // ── Submit + result ────────────────────────────────

    async function submitQuiz() {
        if (state.timerId) clearInterval(state.timerId);
        const answers = Object.entries(state.answers)
            .filter(([, v]) => v && String(v).trim())
            .map(([qid, v]) => ({ question_id: qid, answer: String(v) }));
        try {
            const r = await api.quizSubmit({ session_id: state.session.session_id, answers });
            renderResult(r);
        } catch {}
    }

    function renderResult(r) {
        if (!quizCard) return;
        const correct = r.breakdown.filter(b => b.correct).length;
        quizCard.innerHTML = `
            <h3 class="font-headline-lg-mobile text-headline-lg-mobile font-bold text-on-background mb-md">Quiz Complete</h3>
            <div class="grid grid-cols-3 gap-gutter mb-md">
                <div class="bg-surface-bright border border-outline-variant rounded-lg p-md">
                    <div class="font-label-sm uppercase tracking-wider text-on-surface-variant">Score</div>
                    <div class="font-headline-xl text-headline-xl text-primary">${(r.score*100).toFixed(0)}%</div>
                </div>
                <div class="bg-surface-bright border border-outline-variant rounded-lg p-md">
                    <div class="font-label-sm uppercase tracking-wider text-on-surface-variant">Correct</div>
                    <div class="font-headline-xl text-headline-xl text-secondary">${correct}/${r.breakdown.length}</div>
                </div>
                <div class="bg-surface-bright border border-outline-variant rounded-lg p-md">
                    <div class="font-label-sm uppercase tracking-wider text-on-surface-variant">Flagged</div>
                    <div class="font-headline-xl text-headline-xl text-on-surface">${state.flagged.size}</div>
                </div>
            </div>
            ${r.weak_topics.length
                ? `<div class="bg-error-container text-on-error-container rounded-lg p-sm mb-md flex gap-xs items-center"><span class="material-symbols-outlined">priority_high</span> Weak topics: <strong>${r.weak_topics.map(escapeHtml).join(", ")}</strong></div>`
                : `<div class="bg-secondary-fixed text-on-secondary-container rounded-lg p-sm mb-md flex gap-xs items-center"><span class="material-symbols-outlined">check_circle</span> No weak topics — well done.</div>`}
            <h4 class="font-label-md text-label-md uppercase tracking-wider text-on-surface-variant mb-sm">Per-question breakdown</h4>
            <div class="flex flex-col gap-xs mb-md">
                ${r.breakdown.map(b => {
                    const q = state.questions.find(qq => qq.id === b.question_id);
                    const icon = b.correct ? `<span class="material-symbols-outlined" style="color:#2e7d32">check_circle</span>` : `<span class="material-symbols-outlined text-error">cancel</span>`;
                    return `
                    <div class="flex gap-sm p-sm border border-outline-variant rounded bg-surface-bright">
                        ${icon}
                        <div class="flex-1">
                            <div class="font-body-md text-on-surface">${escapeHtml(q ? q.text : "")}</div>
                            <div class="font-body-sm text-on-surface-variant mt-xs">${escapeHtml(b.explanation || "")}</div>
                        </div>
                    </div>`;
                }).join("")}
            </div>
            <div class="flex gap-xs">
                <button id="q-again" class="bg-primary text-on-primary font-label-md text-label-md py-xs px-md rounded hover:bg-on-primary-fixed-variant transition-colors flex items-center gap-xs">
                    <span class="material-symbols-outlined">restart_alt</span> New Quiz
                </button>
                <a href="/progress-page" class="border border-outline-variant text-primary font-label-md text-label-md py-xs px-md rounded hover:bg-surface-container-low transition-colors flex items-center gap-xs">
                    <span class="material-symbols-outlined">analytics</span> View Progress
                </a>
            </div>
        `;
        quizCard.querySelector("#q-again").addEventListener("click", reset);
    }

    function reset() {
        if (state.timerId) clearInterval(state.timerId);
        state.session = null; state.questions = []; state.answers = {};
        state.flagged = new Set(); state.idx = 0; state.startedAt = null; state.hintText = "";
        renderStart();
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderStart();
        document.addEventListener("sc:new-session", reset);
    });
})();
