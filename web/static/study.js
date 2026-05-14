// Study page wiring.

(function () {
    let currentResult = null;
    let generateStart = null;

    const topicInput   = () => document.getElementById("topic-input");
    const modeSelect   = () => document.getElementById("mode-select");
    const generateBtn  = () => document.getElementById("generate-btn");
    const resultArea   = () => document.getElementById("result-area");
    const sourcesList  = () => document.getElementById("sources-list");
    const sourcesCount = () => document.getElementById("sources-count");
    const copyBtn      = () => document.getElementById("copy-btn");
    const bookmarkBtn  = () => document.getElementById("bookmark-btn");
    const confChip     = () => document.getElementById("confidence-chip");

    function setLoading(loading) {
        const btn = generateBtn();
        const icon = document.getElementById("generate-icon");
        const label = document.getElementById("generate-label");
        if (loading) {
            btn.disabled = true;
            icon.textContent = "progress_activity";
            icon.classList.add("animate-spin");
            label.textContent = "Generating…";
        } else {
            btn.disabled = !topicInput().value.trim();
            icon.classList.remove("animate-spin");
            icon.textContent = "auto_awesome";
            label.textContent = "Generate";
        }
    }

    function toggleResultControls(enabled) {
        document.querySelectorAll(".qa-btn").forEach(b => b.disabled = !enabled);
        copyBtn().disabled = !enabled;
        bookmarkBtn().disabled = !enabled;
    }

    function renderConfidenceChip(uncertain) {
        const chip = confChip();
        chip.classList.remove("hidden", "bg-error-container", "text-on-error-container", "bg-success-container", "text-success");
        if (uncertain) {
            chip.classList.add("bg-error-container", "text-on-error-container");
            chip.textContent = "⚠ Low confidence";
        } else {
            chip.classList.add("bg-success-container", "text-success");
            chip.textContent = "✓ Grounded";
        }
    }

    function renderResult(r) {
        currentResult = r;
        const html = renderMarkdown(r.output || "");
        const warningBlock = (r.warnings || []).length
            ? `<div class="bg-error-container border-l-4 border-error rounded p-sm my-sm">
                 <strong class="font-label-md text-on-error-container">Warnings</strong>
                 <ul class="mt-xs text-body-sm">
                    ${r.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
                 </ul>
               </div>`
            : "";
        resultArea().innerHTML = warningBlock + html;
        renderConfidenceChip(r.uncertain);
        renderSources(r.sources || []);
        toggleResultControls(true);
    }

    function renderSources(sources) {
        sourcesCount().textContent = sources.length;
        const root = sourcesList();
        if (!sources.length) {
            root.innerHTML = `<p class="font-body-sm text-on-surface-variant">No sources cited for this output.</p>`;
            return;
        }
        root.innerHTML = sources.map(s => `
            <details class="group border border-outline-variant rounded-lg bg-surface-bright overflow-hidden">
                <summary class="flex justify-between items-center p-xs cursor-pointer hover:bg-surface-container-low transition-colors list-none">
                    <div class="flex items-center gap-xs overflow-hidden">
                        <span class="material-symbols-outlined text-secondary text-[16px] flex-shrink-0">description</span>
                        <span class="font-body-sm text-on-surface truncate">${escapeHtml(s.source || "unknown")}</span>
                    </div>
                    <div class="flex items-center gap-xs">
                        <span class="font-label-sm text-on-surface-variant text-[11px]">p.${s.page || 1}</span>
                        <span class="font-label-sm text-primary bg-surface-container-high px-[5px] py-[1px] rounded text-[11px]">${(s.score || 0).toFixed(2)}</span>
                        <span class="material-symbols-outlined text-on-surface-variant text-[18px] group-open:rotate-180 transition-transform">expand_more</span>
                    </div>
                </summary>
                <div class="p-xs pt-0 border-t border-outline-variant mt-xs">
                    <p class="font-body-sm text-on-surface-variant text-[12px] leading-[18px]">
                        chunk_id: <code class="text-[11px]">${escapeHtml(s.chunk_id || "")}</code>
                    </p>
                </div>
            </details>
        `).join("");
    }

    async function doGenerate(modeOverride) {
        const topic = topicInput().value.trim();
        const mode = modeOverride || modeSelect().value;
        if (!topic) { toast("Enter a topic first."); return; }
        if (modeOverride) modeSelect().value = modeOverride;

        setLoading(true);
        generateStart = Date.now();
        resultArea().innerHTML = `
            <div class="space-y-sm">
                <div class="sc-skeleton h-6 w-2/3"></div>
                <div class="sc-skeleton h-4 w-full"></div>
                <div class="sc-skeleton h-4 w-5/6"></div>
                <div class="sc-skeleton h-4 w-3/4"></div>
                <div class="sc-skeleton h-6 w-1/2 mt-md"></div>
                <div class="sc-skeleton h-4 w-full"></div>
                <div class="sc-skeleton h-4 w-4/5"></div>
            </div>`;
        try {
            const r = await api.generate({
                topic, mode,
                top_k: parseInt(localStorage.getItem("top_k") || "5", 10),
                temperature: parseFloat(localStorage.getItem("temperature") || "0.7"),
            });
            renderResult(r);
            api.logSession({
                kind: "study",
                topic: topic.slice(0, 120),
                duration_seconds: Math.round((Date.now() - generateStart) / 1000),
                impact_score: 5,
            }).catch(() => {});
        } catch (e) {
            resultArea().innerHTML = `<p class="text-error">Failed to generate. ${escapeHtml(e.message || "")}</p>`;
        } finally {
            setLoading(false);
        }
    }

    async function doRefine(action) {
        if (!currentResult) return;
        const btn = document.querySelector(`.qa-btn[data-action="${action}"]`);
        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Working…`;
        try {
            const payload = { content: currentResult.output, action };
            if (action === "translate") {
                payload.target_language = document.getElementById("translate-lang").value.trim() || "Spanish";
            }
            const r = await api.refine(payload);
            currentResult = { ...currentResult, output: r.output };
            resultArea().innerHTML = renderMarkdown(r.output);
            toast(`${action.charAt(0).toUpperCase()}${action.slice(1)} applied.`, "success");
        } catch {} finally {
            btn.disabled = false;
            btn.innerHTML = original;
        }
    }

    async function doMakeFlashcards() {
        if (!currentResult) return;
        const btn = document.querySelector('.qa-btn[data-action="make-flashcards"]');
        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span> Extracting…`;
        try {
            const r = await api.fcFromText({
                text: currentResult.output,
                topic: topicInput().value.trim() || null,
                n_cards: 8,
            });
            toast(`Added ${r.cards_added} flashcards.`, "success");
        } catch {} finally {
            btn.disabled = false;
            btn.innerHTML = original;
        }
    }

    async function doBookmark() {
        if (!currentResult) return;
        await api.addBookmark({
            content: currentResult.output,
            topic: topicInput().value.trim() || null,
            mode: modeSelect().value,
        });
        toast("Bookmarked.", "success");
    }

    async function doCopy() {
        if (!currentResult) return;
        try {
            await navigator.clipboard.writeText(currentResult.output);
            toast("Copied to clipboard.", "success");
        } catch {
            toast("Clipboard blocked — falling back to download.", "error");
            const blob = new Blob([currentResult.output], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = "study_notes.md"; a.click();
            URL.revokeObjectURL(url);
        }
    }

    function wire() {
        topicInput().addEventListener("input", () => {
            generateBtn().disabled = !topicInput().value.trim();
        });
        topicInput().addEventListener("keydown", e => {
            if (e.key === "Enter") { e.preventDefault(); doGenerate(); }
        });
        generateBtn().addEventListener("click", () => doGenerate());
        copyBtn().addEventListener("click", doCopy);
        bookmarkBtn().addEventListener("click", doBookmark);

        document.querySelectorAll(".qa-btn").forEach(b => {
            b.addEventListener("click", () => {
                const a = b.dataset.action;
                if (a === "make-flashcards") doMakeFlashcards();
                else doRefine(a);
            });
        });

        document.querySelectorAll(".qm-btn").forEach(b => {
            b.addEventListener("click", () => doGenerate(b.dataset.quick));
        });

        document.addEventListener("sc:new-session", () => {
            currentResult = null;
            topicInput().value = "";
            resultArea().innerHTML = `<p class="font-body-md text-on-surface-variant">Enter a topic above to start a new session.</p>`;
            sourcesList().innerHTML = `<p class="font-body-sm text-on-surface-variant">Sources will appear once you generate from indexed material.</p>`;
            sourcesCount().textContent = "0";
            confChip().classList.add("hidden");
            toggleResultControls(false);
            generateBtn().disabled = true;
        });

        // Initial disabled state
        generateBtn().disabled = true;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", wire);
    } else {
        wire();
    }
})();
