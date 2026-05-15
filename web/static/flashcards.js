// Flashcards page — targets the Stitch flashcards DOM.

(function () {
    const state = {
        cards: [],
        idx: 0,
        revealed: false,
        lastReviewedId: null,
    };

    // ── DOM lookups ─────────────────────────────────────

    function findByText(sel, label) {
        const re = new RegExp(`\\b${label}\\b`, "i");
        for (const el of document.querySelectorAll(sel)) {
            if (re.test((el.textContent || "").trim())) return el;
        }
        return null;
    }

    const main = document.querySelector("main");
    // Due badge — div with text "Review Due" containing a big number
    const dueBadge = (() => {
        for (const el of document.querySelectorAll("div")) {
            if (/Review Due/i.test(el.textContent || "") && el.querySelector(".font-headline-lg")) return el;
        }
        return null;
    })();
    const dueCountEl = dueBadge ? dueBadge.querySelector(".font-headline-lg") : null;

    // Progress bar: span "Card X of Y" + the bar
    const progressLabel = findByText("span", "Card");  // First match contains "Card N of M"
    const progressContainer = progressLabel ? progressLabel.parentElement : null;
    const progressBar = progressContainer ? progressContainer.querySelector(".bg-secondary, .bg-secondary.h-full") : null;

    // Card body — the big rounded-xl box. Find by min-h-[500px] or by containing "Q" badge
    const cardBox = (() => {
        for (const el of document.querySelectorAll("div")) {
            if (el.className && /rounded-xl/.test(el.className) && /min-h-\[500px\]/.test(el.className)) return el;
        }
        // fallback: find by Q badge then walk up
        const qBadge = Array.from(document.querySelectorAll("span")).find(s => (s.textContent || "").trim() === "Q");
        if (qBadge) {
            let c = qBadge; for (let i = 0; i < 6 && c; i++) { c = c.parentElement; if (c && /rounded-xl/.test(c.className || "")) return c; }
        }
        return null;
    })();

    // Inside cardBox:
    //   front h3 (question)
    //   reveal toggle button
    //   back paragraph
    //   rating section with three rating buttons

    function frontH3() { return cardBox ? cardBox.querySelector("h3") : null; }
    function backP() {
        if (!cardBox) return null;
        // The back is inside a flex-1 container with bg-surface-bright
        const back = cardBox.querySelector(".bg-surface-bright");
        return back ? back.querySelector("p") : null;
    }
    function revealBtn() {
        return findByText("button", "Reveal Answer");
    }
    function ratingButtons() {
        // Buttons after the dashed divider with text "Hard", "Good", "Easy"
        const hard = findByText("button", "^Hard$") || findByText("button", "Hard");
        const good = findByText("button", "^Good$") || findByText("button", "Good");
        const easy = findByText("button", "^Easy$") || findByText("button", "Easy");
        return { hard, good, easy };
    }

    // Top-bar action buttons in progress row: undo + more_vert
    const topActionButtons = progressContainer
        ? Array.from(progressContainer.querySelectorAll("button"))
        : [];
    function findIconBtn(iconName) {
        return topActionButtons.find(b => new RegExp(`>${iconName}<`).test(b.innerHTML || ""));
    }
    const undoBtn = findIconBtn("undo");
    const moreBtn = findIconBtn("more_vert");

    // ── State render ────────────────────────────────────

    async function loadDue() {
        try {
            const r = await api.fcDue();
            state.cards = r.cards || [];
            state.idx = 0;
            state.revealed = false;
            renderDueBadge(r.count);
            if (!state.cards.length) {
                renderEmpty();
            } else {
                renderCard();
            }
        } catch {}
    }

    function renderDueBadge(count) {
        if (dueCountEl) dueCountEl.textContent = String(count);
        if (dueBadge) {
            if (count > 0) {
                dueBadge.classList.remove("bg-secondary-fixed", "text-on-secondary-container");
                dueBadge.classList.add("bg-error-container", "text-on-error-container");
            } else {
                dueBadge.classList.remove("bg-error-container", "text-on-error-container");
                dueBadge.classList.add("bg-secondary-fixed", "text-on-secondary-container");
            }
        }
    }

    function renderEmpty() {
        if (!cardBox) return;
        cardBox.innerHTML = `
            <div class="flex-1 p-xl flex flex-col justify-center items-center text-center">
                <span class="material-symbols-outlined" style="font-size:48px;color:#0060ac;">celebration</span>
                <h3 class="font-headline-lg text-headline-lg text-on-surface mt-sm mb-xs">No cards due right now</h3>
                <p class="font-body-md text-on-surface-variant max-w-md mx-auto">
                    Generate study material and use <strong>Make Flashcards</strong> on the Study page,
                    or upload more material on a new topic.
                </p>
                <div class="flex gap-xs mt-md">
                    <a href="/" class="bg-primary text-on-primary font-label-md text-label-md py-xs px-md rounded hover:bg-on-primary-fixed-variant transition-colors flex items-center gap-xs">
                        <span class="material-symbols-outlined">book_2</span> Open Study
                    </a>
                    <button id="fc-export-empty" class="border border-outline-variant text-primary font-label-md text-label-md py-xs px-md rounded hover:bg-surface-container-low transition-colors flex items-center gap-xs">
                        <span class="material-symbols-outlined">download</span> Export Anki
                    </button>
                </div>
            </div>
        `;
        const ee = document.getElementById("fc-export-empty");
        if (ee) ee.addEventListener("click", exportAnki);
        if (progressLabel) progressLabel.textContent = "Card 0 of 0";
        if (progressBar) progressBar.style.width = "0%";
    }

    function renderCard() {
        if (!cardBox || !state.cards.length) return;
        const c = state.cards[state.idx];
        const total = state.cards.length;
        if (progressLabel) progressLabel.textContent = `Card ${state.idx + 1} of ${total}`;
        if (progressBar) progressBar.style.width = `${((state.idx + 1) / total) * 100}%`;

        cardBox.innerHTML = `
            <!-- Front -->
            <div class="flex-1 p-xl flex flex-col justify-center items-center text-center relative z-10">
                <div class="absolute top-md left-md bg-surface-container px-3 py-1 rounded-full border border-surface-dim">
                    <span class="font-label-sm text-label-sm text-on-secondary-container font-bold tracking-wider">Q</span>
                </div>
                ${c.topic ? `<div class="absolute top-md right-md font-label-sm text-label-sm text-on-surface-variant">${escapeHtml(c.topic)}</div>` : ""}
                <h3 class="font-headline-lg text-headline-lg text-on-surface max-w-2xl leading-relaxed">${escapeHtml(c.front || "")}</h3>
            </div>
            <!-- Toggle -->
            <div class="w-full px-xl py-xs flex justify-center relative z-20">
                <div class="w-full border-t border-dashed border-outline-variant absolute top-1/2 left-0 z-0"></div>
                <button id="fc-reveal" class="bg-surface-container-lowest border border-outline text-on-surface-variant font-label-sm text-label-sm px-4 py-1.5 rounded-full z-10 hover:bg-surface hover:text-primary transition-colors flex items-center gap-1 shadow-sm ${state.revealed ? "hidden" : ""}">
                    <span class="material-symbols-outlined text-[14px]">visibility</span>
                    Reveal Answer
                </button>
            </div>
            <!-- Back -->
            <div class="flex-1 p-xl ${state.revealed ? "flex" : "hidden"} flex-col justify-center items-center text-center bg-surface-bright rounded-b-xl relative border-t border-surface-container opacity-90">
                <div class="absolute top-md left-md bg-secondary-container px-3 py-1 rounded-full border border-secondary-fixed">
                    <span class="font-label-sm text-label-sm text-on-secondary-container font-bold tracking-wider">A</span>
                </div>
                <p class="font-body-md text-body-md text-on-surface-variant max-w-2xl text-left leading-relaxed">${renderMarkdown(c.back || "")}</p>
            </div>
            <!-- Rating -->
            <div class="${state.revealed ? "flex" : "hidden"} p-md bg-surface-container-lowest border-t border-outline-variant rounded-b-xl flex-col items-center gap-sm">
                <span class="font-label-sm text-label-sm text-on-surface-variant">How difficult was it to recall?</span>
                <div class="flex w-full max-w-md gap-4">
                    <button data-q="1" class="rate-btn flex-1 py-3 px-4 rounded border border-outline-variant bg-surface hover:bg-error-container hover:border-[#ffb4ab] hover:text-on-error-container transition-all flex flex-col items-center justify-center gap-1 group">
                        <span class="font-label-md text-label-md text-on-surface-variant group-hover:text-on-error-container">Again</span>
                        <span class="font-label-sm text-[11px] opacity-70">&lt; 1m</span>
                    </button>
                    <button data-q="3" class="rate-btn flex-1 py-3 px-4 rounded border border-outline-variant bg-surface hover:bg-surface-container transition-all flex flex-col items-center justify-center gap-1">
                        <span class="font-label-md text-label-md">Hard</span>
                        <span class="font-label-sm text-[11px] opacity-70">~6m</span>
                    </button>
                    <button data-q="4" class="rate-btn flex-1 py-3 px-4 rounded border border-primary text-primary hover:bg-primary-container hover:text-on-primary-container transition-all flex flex-col items-center justify-center gap-1 group">
                        <span class="font-label-md text-label-md">Good</span>
                        <span class="font-label-sm text-[11px] opacity-70">10m</span>
                    </button>
                    <button data-q="5" class="rate-btn flex-1 py-3 px-4 rounded bg-primary text-on-primary hover:bg-on-primary-fixed-variant transition-all shadow-[0_2px_4px_rgba(0,32,69,0.2)] flex flex-col items-center justify-center gap-1">
                        <span class="font-label-md text-label-md">Easy</span>
                        <span class="font-label-sm text-[11px] text-surface-variant">4d</span>
                    </button>
                </div>
            </div>
        `;
        const r = document.getElementById("fc-reveal");
        if (r) r.addEventListener("click", () => { state.revealed = true; renderCard(); });
        cardBox.querySelectorAll(".rate-btn").forEach(b => {
            b.addEventListener("click", () => rate(parseInt(b.dataset.q, 10)));
        });
    }

    // ── Actions ────────────────────────────────────────

    async function rate(quality) {
        if (!state.cards.length) return;
        const c = state.cards[state.idx];
        try {
            await api.fcReview({ card_id: c.id, quality });
            state.lastReviewedId = c.id;
            toast(`Reviewed — q=${quality}.`, "success");
        } catch {}
        state.cards.splice(state.idx, 1);
        state.revealed = false;
        if (state.idx >= state.cards.length) state.idx = 0;
        renderDueBadge(state.cards.length);
        if (!state.cards.length) renderEmpty(); else renderCard();
    }

    async function undo() {
        if (!state.lastReviewedId) { toast("Nothing to undo."); return; }
        try {
            const r = await api.fcUndo({ card_id: state.lastReviewedId });
            if (r && r.undone) {
                toast("Last review undone.", "success");
                state.lastReviewedId = null;
                loadDue();
            } else toast("Nothing to undo.");
        } catch {}
    }

    async function exportAnki() {
        try {
            const blob = await api.exportAnki();
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "study_companion.apkg"; a.click();
            toast("Anki package downloaded.", "success");
        } catch {}
    }

    // ── Wire ───────────────────────────────────────────

    document.addEventListener("DOMContentLoaded", () => {
        if (undoBtn) undoBtn.addEventListener("click", undo);
        if (moreBtn) {
            moreBtn.addEventListener("click", e => {
                e.preventDefault();
                // Treat as "Export Anki" trigger
                exportAnki();
            });
            moreBtn.title = "Export Anki";
        }
        document.addEventListener("keydown", e => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
            if (!state.cards.length) return;
            if (e.code === "Space") {
                e.preventDefault();
                if (!state.revealed) { state.revealed = true; renderCard(); }
            } else if (state.revealed && ["1","2","3","4"].includes(e.key)) {
                e.preventDefault();
                const qMap = { "1": 1, "2": 3, "3": 4, "4": 5 };
                rate(qMap[e.key]);
            }
        });
        document.addEventListener("sc:new-session", loadDue);
        document.addEventListener("sc:index-changed", loadDue);
        loadDue();
    });
})();
