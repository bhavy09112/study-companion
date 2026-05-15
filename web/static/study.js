// Study page — wires the Stitch DOM to the backend without modifying markup.

(function () {
    // ── Mode mapping (Stitch select values → backend modes) ─

    const MODE_MAP = {
        "simple":      "simple_explanation",
        "key_concepts":"key_concepts",
        "exam":        "exam_critical",
        "deep_dive":   "detailed_explanation",
    };

    // ── DOM helpers ─────────────────────────────────────

    function $textBtn(label) {
        const re = new RegExp(`\\b${label}\\b`, "i");
        for (const b of document.querySelectorAll("button")) {
            if (re.test((b.textContent || "").trim())) return b;
        }
        return null;
    }
    function $cardByH3(label) {
        const re = new RegExp(`\\b${label}\\b`, "i");
        for (const h of document.querySelectorAll("h3, h2")) {
            if (re.test((h.textContent || "").trim())) {
                let c = h; while (c && !(c.matches && c.matches("article, section, div, aside"))) c = c.parentElement;
                return c;
            }
        }
        return null;
    }

    let currentResult = null;
    let generateStart = null;

    // ── Locate key elements ────────────────────────────

    const topicInput = document.getElementById("topic-input");
    const modeSelect = document.getElementById("output-mode");
    const generateBtn = $textBtn("Generate");
    // The Generated Content panel: article with h2 "Generated Content"
    const resultArticle = (() => {
        for (const a of document.querySelectorAll("article, section")) {
            const h = a.querySelector("h2");
            if (h && /Generated Content/i.test(h.textContent || "")) return a;
        }
        return null;
    })();
    const resultBody = document.getElementById("result-area")
        || (resultArticle ? resultArticle.querySelector(".prose, .prose-slate, [class*='prose']") : null);

    // Copy / Bookmark icon buttons (in the result header)
    const headerButtons = resultArticle ? resultArticle.querySelectorAll("button") : [];
    let copyBtn = null, bookmarkBtn = null;
    headerButtons.forEach(b => {
        const t = b.innerHTML || "";
        if (/content_copy/.test(t)) copyBtn = b;
        if (/bookmark/.test(t)) bookmarkBtn = b;
    });

    // Quick Actions buttons (right column)
    function findActionBtn(label) {
        return $textBtn(label);
    }
    const btnSummarize    = findActionBtn("Summarize");
    const btnSimplify     = findActionBtn("Simplify");
    const btnFlashcards   = findActionBtn("Make Flashcards");
    const btnTranslate    = findActionBtn("Translate");

    // Sources panel (card with h3 "Cited Sources")
    const sourcesCard = $cardByH3("Cited Sources");
    const sourcesCountEl = document.getElementById("sources-count")
        || (sourcesCard ? sourcesCard.querySelector("span.bg-surface-container-high, span.text-primary") : null);
    const sourcesListEl = document.getElementById("sources-list")
        || (sourcesCard ? sourcesCard.querySelector(".flex.flex-col.gap-xs, .flex-col.gap-xs") : null);

    // ── Render ──────────────────────────────────────────

    function setBusy(b) {
        if (!generateBtn) return;
        generateBtn.disabled = b;
        generateBtn.style.opacity = b ? "0.6" : "1";
        const icon = generateBtn.querySelector(".material-symbols-outlined");
        if (icon) {
            if (b) { icon.textContent = "progress_activity"; icon.classList.add("animate-spin"); }
            else { icon.textContent = "magic_button"; icon.classList.remove("animate-spin"); }
        }
    }

    function renderResult(r) {
        currentResult = r;
        if (!resultBody) return;
        let warningHtml = "";
        if (r.uncertain) {
            warningHtml += `<div class="bg-error-container border border-error text-on-error-container rounded-lg p-sm mb-md flex gap-sm items-start">
                <span class="material-symbols-outlined">warning</span>
                <span class="font-body-sm">This topic may not be well-covered by your uploaded material.</span>
            </div>`;
        }
        for (const w of (r.warnings || [])) {
            warningHtml += `<div class="bg-surface-container-low border border-outline-variant rounded-lg p-sm mb-md flex gap-sm items-start">
                <span class="material-symbols-outlined text-secondary">info</span>
                <span class="font-body-sm text-on-surface-variant">${escapeHtml(w)}</span>
            </div>`;
        }
        resultBody.innerHTML = warningHtml + renderMarkdown(r.output || "");
        renderSources(r.sources || []);
    }

    function renderSources(sources) {
        if (sourcesCountEl) sourcesCountEl.textContent = String(sources.length);
        if (!sourcesListEl) return;
        if (!sources.length) {
            sourcesListEl.innerHTML = `<p class="font-body-sm text-body-sm text-on-surface-variant">Sources will appear once you generate from indexed material.</p>`;
            return;
        }
        sourcesListEl.innerHTML = sources.map(s => `
            <details class="group border border-outline-variant rounded-lg bg-surface-bright overflow-hidden">
                <summary class="flex justify-between items-center p-xs cursor-pointer hover:bg-surface-container-low transition-colors list-none">
                    <div class="flex items-center gap-xs overflow-hidden">
                        <span class="material-symbols-outlined text-secondary text-[16px] flex-shrink-0">description</span>
                        <span class="font-body-sm text-body-sm text-on-surface truncate">${escapeHtml(s.source || "unknown")}</span>
                    </div>
                    <div class="flex items-center gap-xs">
                        <span class="font-label-sm text-label-sm text-on-surface-variant">p.${s.page || 1}</span>
                        <span class="bg-surface-container-high text-primary font-label-sm text-label-sm px-[5px] rounded">${(s.score || 0).toFixed(2)}</span>
                        <span class="material-symbols-outlined text-on-surface-variant text-[18px] group-open:rotate-180 transition-transform">expand_more</span>
                    </div>
                </summary>
                <div class="p-xs pt-0 border-t border-outline-variant mt-xs">
                    <p class="font-body-sm text-body-sm text-on-surface-variant text-[12px] leading-[18px]">
                        chunk_id: <code class="text-[11px] bg-surface-container-low px-1 rounded">${escapeHtml(s.chunk_id || "")}</code>
                    </p>
                </div>
            </details>
        `).join("");
    }

    function clearResult() {
        currentResult = null;
        if (resultBody) {
            resultBody.innerHTML = `
                <div class="bg-surface-container-low border border-outline-variant rounded-lg p-sm flex gap-sm items-start">
                    <span class="material-symbols-outlined text-secondary mt-[2px]">info</span>
                    <div>
                        <strong class="font-label-sm text-label-sm block mb-[2px]">Welcome</strong>
                        <span class="font-body-sm text-body-sm text-on-surface-variant">
                            Enter a topic above and hit <b>Generate</b>. The model will retrieve from your indexed sources and produce study material in the selected mode.
                        </span>
                    </div>
                </div>`;
        }
        renderSources([]);
    }

    // ── Actions ────────────────────────────────────────

    async function doGenerate() {
        if (!topicInput || !modeSelect) return;
        const topic = (topicInput.value || "").trim();
        if (!topic) { toast("Enter a topic first."); return; }
        const apiMode = MODE_MAP[modeSelect.value] || "key_concepts";

        setBusy(true);
        generateStart = Date.now();
        if (resultBody) {
            resultBody.innerHTML = `
                <div class="space-y-sm">
                    <div class="h-6 w-2/3 bg-surface-container rounded"></div>
                    <div class="h-4 w-full bg-surface-container rounded"></div>
                    <div class="h-4 w-5/6 bg-surface-container rounded"></div>
                    <div class="h-4 w-3/4 bg-surface-container rounded"></div>
                </div>`;
        }
        try {
            const r = await api.generate({
                topic, mode: apiMode,
                top_k: parseInt(localStorage.getItem("top_k") || "5", 10),
                temperature: parseFloat(localStorage.getItem("temperature") || "0.7"),
            });
            renderResult(r);
            api.logSession({
                kind: "study", topic: topic.slice(0, 120),
                duration_seconds: Math.round((Date.now() - generateStart) / 1000),
                impact_score: 5,
            }).catch(() => {});
        } catch (e) {
            if (resultBody) resultBody.innerHTML = `<p class="text-error">Failed to generate. ${escapeHtml(e.message || "")}</p>`;
        } finally { setBusy(false); }
    }

    async function doRefine(action, btn) {
        if (!currentResult) { toast("Generate something first."); return; }
        const o = btn ? btn.innerHTML : "";
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Working…`;
        }
        try {
            const payload = { content: currentResult.output, action };
            if (action === "translate") {
                const lang = prompt("Translate to which language?", "Spanish");
                if (!lang) { if (btn) { btn.disabled = false; btn.innerHTML = o; } return; }
                payload.target_language = lang;
            }
            const r = await api.refine(payload);
            currentResult = { ...currentResult, output: r.output };
            if (resultBody) resultBody.innerHTML = renderMarkdown(r.output);
            toast(`${action[0].toUpperCase()}${action.slice(1)} applied.`, "success");
        } catch {} finally {
            if (btn) { btn.disabled = false; btn.innerHTML = o; }
        }
    }

    async function doMakeFlashcards(btn) {
        if (!currentResult) { toast("Generate something first."); return; }
        const o = btn ? btn.innerHTML : "";
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Extracting…`;
        }
        try {
            const r = await api.fcFromText({
                text: currentResult.output,
                topic: (topicInput.value || "").trim() || null,
                n_cards: 8,
            });
            toast(`Added ${r.cards_added} flashcards.`, "success");
        } catch {} finally {
            if (btn) { btn.disabled = false; btn.innerHTML = o; }
        }
    }

    async function doCopy() {
        if (!currentResult) { toast("Nothing to copy yet."); return; }
        try {
            await navigator.clipboard.writeText(currentResult.output);
            toast("Copied to clipboard.", "success");
        } catch {
            const blob = new Blob([currentResult.output], { type: "text/markdown" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "study_notes.md";
            a.click();
        }
    }

    async function doBookmark() {
        if (!currentResult) { toast("Generate something first."); return; }
        await api.addBookmark({
            content: currentResult.output,
            topic: (topicInput.value || "").trim() || null,
            mode: MODE_MAP[modeSelect.value] || modeSelect.value,
        });
        toast("Bookmarked.", "success");
    }

    // ── Wiring ─────────────────────────────────────────

    document.addEventListener("DOMContentLoaded", () => {
        // Keep the HTML empty-state note until the user actually generates.

        if (generateBtn) generateBtn.addEventListener("click", doGenerate);
        if (topicInput) topicInput.addEventListener("keydown", e => {
            if (e.key === "Enter") { e.preventDefault(); doGenerate(); }
        });

        if (btnSummarize)  btnSummarize.addEventListener("click",  () => doRefine("summarize", btnSummarize));
        if (btnSimplify)   btnSimplify.addEventListener("click",   () => doRefine("simplify", btnSimplify));
        if (btnTranslate)  btnTranslate.addEventListener("click",  () => doRefine("translate", btnTranslate));
        if (btnFlashcards) btnFlashcards.addEventListener("click", () => doMakeFlashcards(btnFlashcards));

        if (copyBtn) copyBtn.addEventListener("click", doCopy);
        if (bookmarkBtn) bookmarkBtn.addEventListener("click", doBookmark);

        document.addEventListener("sc:new-session", () => {
            if (topicInput) topicInput.value = "";
            clearResult();
        });
    });
})();
