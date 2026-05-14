// Flashcards page wiring.

(function () {
    const state = {
        cards: [],
        idx: 0,
        revealed: false,
        lastReviewedId: null,
    };
    const $ = id => document.getElementById(id);

    async function loadDue() {
        try {
            const r = await api.fcDue();
            state.cards = r.cards || [];
            $("due-count").textContent = r.count;
            if (!state.cards.length) {
                $("fc-empty").classList.remove("hidden");
                $("fc-active").classList.add("hidden");
                $("due-badge").classList.add("opacity-50");
            } else {
                $("fc-empty").classList.add("hidden");
                $("fc-active").classList.remove("hidden");
                $("due-badge").classList.remove("opacity-50");
                state.idx = 0;
                state.revealed = false;
                renderCard();
            }
        } catch {}
    }

    function renderCard() {
        if (!state.cards.length) return;
        const c = state.cards[state.idx];
        $("fc-progress-label").textContent = `Card ${state.idx + 1} of ${state.cards.length}`;
        $("fc-progress-bar").style.width = `${((state.idx + 1) / state.cards.length) * 100}%`;
        $("fc-front").textContent = c.front;
        $("fc-back").textContent = c.back;
        $("fc-topic").textContent = c.topic ? `Topic: ${c.topic}` : "";
        $("deck-name").textContent = c.topic || "All Cards";

        if (state.revealed) {
            $("fc-back-wrap").classList.remove("hidden");
            $("fc-back-wrap").classList.add("flex");
            $("fc-rating").classList.remove("hidden");
            $("fc-rating").classList.add("flex");
            $("fc-reveal").classList.add("hidden");
        } else {
            $("fc-back-wrap").classList.add("hidden");
            $("fc-back-wrap").classList.remove("flex");
            $("fc-rating").classList.add("hidden");
            $("fc-rating").classList.remove("flex");
            $("fc-reveal").classList.remove("hidden");
        }
    }

    async function rate(quality) {
        if (!state.cards.length) return;
        const c = state.cards[state.idx];
        try {
            await api.fcReview({ card_id: c.id, quality });
            state.lastReviewedId = c.id;
            toast(`Reviewed — next in ${quality >= 4 ? "days" : "minutes"}.`, "success");
        } catch {}
        // Advance
        state.cards.splice(state.idx, 1);
        if (state.idx >= state.cards.length) state.idx = 0;
        state.revealed = false;
        if (!state.cards.length) {
            $("due-count").textContent = "0";
            $("fc-empty").classList.remove("hidden");
            $("fc-active").classList.add("hidden");
            $("due-badge").classList.add("opacity-50");
        } else {
            $("due-count").textContent = state.cards.length;
            renderCard();
        }
    }

    async function undo() {
        if (!state.lastReviewedId) { toast("Nothing to undo."); return; }
        try {
            const r = await api.fcUndo({ card_id: state.lastReviewedId });
            if (r && r.undone) {
                toast("Last review undone — reload to see the card again.", "success");
                state.lastReviewedId = null;
                await loadDue();
            } else {
                toast("Nothing to undo.");
            }
        } catch {}
    }

    async function exportAnki() {
        try {
            const blob = await api.exportAnki();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = "study_companion.apkg"; a.click();
            URL.revokeObjectURL(url);
            toast("Anki package downloaded.", "success");
        } catch {}
    }

    function wire() {
        $("fc-reveal").addEventListener("click", () => { state.revealed = true; renderCard(); });
        $("fc-undo").addEventListener("click", undo);
        $("fc-export").addEventListener("click", exportAnki);
        const exportEmpty = $("export-anki-empty");
        if (exportEmpty) exportEmpty.addEventListener("click", exportAnki);
        $("fc-skip").addEventListener("click", () => {
            if (!state.cards.length) return;
            state.idx = (state.idx + 1) % state.cards.length;
            state.revealed = false;
            renderCard();
        });
        document.querySelectorAll(".rate-btn").forEach(b => {
            b.addEventListener("click", () => rate(parseInt(b.dataset.q, 10)));
        });
        document.addEventListener("keydown", e => {
            if (!state.cards.length) return;
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
            if (e.key === " " || e.code === "Space") {
                e.preventDefault();
                if (!state.revealed) { state.revealed = true; renderCard(); }
            } else if (state.revealed && ["1", "2", "3", "4"].includes(e.key)) {
                e.preventDefault();
                const qMap = { "1": 1, "2": 3, "3": 4, "4": 5 };
                rate(qMap[e.key]);
            }
        });
        document.addEventListener("sc:new-session", loadDue);
    }

    document.addEventListener("DOMContentLoaded", () => {
        wire();
        loadDue();
    });
})();
