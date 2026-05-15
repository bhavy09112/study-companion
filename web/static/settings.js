// Settings page — targets the Stitch settings DOM.

(function () {
    const KEYS = { url: "api_base_url", topk: "top_k", temp: "temperature" };

    function findInputByPrecedingLabel(text) {
        const re = new RegExp(`\\b${text}\\b`, "i");
        for (const lbl of document.querySelectorAll("label")) {
            if (re.test((lbl.textContent || "").trim())) {
                // Search siblings + descendants of parent for matching input
                let p = lbl.parentElement;
                for (let depth = 0; depth < 3 && p; depth++, p = p.parentElement) {
                    const inp = p.querySelector("input, select, textarea");
                    if (inp) return inp;
                }
            }
        }
        return null;
    }

    function findBtnByText(label) {
        const re = new RegExp(label, "i");
        for (const b of document.querySelectorAll("button")) {
            if (re.test((b.textContent || "").trim())) return b;
        }
        return null;
    }

    function findCardByText(label) {
        const re = new RegExp(`\\b${label}\\b`, "i");
        for (const c of document.querySelectorAll(".bg-surface-container-lowest, .rounded-xl, .rounded-lg")) {
            if (re.test(c.textContent || "")) return c;
        }
        return null;
    }

    // ── Locate elements ─────────────────────────────────

    const apiUrlInput = document.getElementById("api-url") || findInputByPrecedingLabel("Local API URL");
    const topKInput   = document.getElementById("top-k") || findInputByPrecedingLabel("Top-K");
    const tempInput   = document.getElementById("temperature") || findInputByPrecedingLabel("Temperature");
    const testConnBtn = findBtnByText("Test Connection");
    const saveBtn     = findBtnByText("Save Settings");
    const discardBtn  = findBtnByText("Discard Changes");
    const manageFilesBtn = findBtnByText("Manage Indexed Files") || findBtnByText("Manage");
    const clearBtn    = findBtnByText("Clear Knowledge Index") || findBtnByText("Clear");

    // Value chip badges next to sliders (the rounded "40" / "0.7" badges)
    function findSliderBadge(input) {
        if (!input) return null;
        let p = input.parentElement;
        for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
            const badge = p.querySelector("span.bg-surface-container, span.text-primary.bg-surface-container, .py-1.px-3.rounded");
            if (badge) return badge;
        }
        return null;
    }
    const topKBadge = findSliderBadge(topKInput);
    const tempBadge = findSliderBadge(tempInput);

    // Storage progress bar + label
    const storageCard = findCardByText("Local Storage") || findCardByText("Vector Index");
    const storageBar  = storageCard ? storageCard.querySelector(".bg-secondary.h-full, .bg-secondary.rounded-full") : null;
    const storageLabel = storageCard
        ? Array.from(storageCard.querySelectorAll(".flex.justify-between .font-label-md, .flex.justify-between span")).find(el => /GB|chunks/i.test(el.textContent || ""))
        : null;

    // ── Initial values from localStorage ───────────────

    function loadFromStorage() {
        const url = localStorage.getItem(KEYS.url) || location.origin;
        const topk = parseInt(localStorage.getItem(KEYS.topk) || "5", 10);
        const temp = parseFloat(localStorage.getItem(KEYS.temp) || "0.7");
        if (apiUrlInput) apiUrlInput.value = url;
        if (topKInput) {
            topKInput.min = "1"; topKInput.max = "20";
            topKInput.value = String(Math.min(20, Math.max(1, topk)));
        }
        if (tempInput) {
            tempInput.min = "0"; tempInput.max = "2"; tempInput.step = "0.1";
            tempInput.value = String(temp);
        }
        if (topKBadge && topKInput) topKBadge.textContent = topKInput.value;
        if (tempBadge && tempInput) tempBadge.textContent = parseFloat(tempInput.value).toFixed(1);
    }

    function wireSliders() {
        if (topKInput) topKInput.addEventListener("input", e => {
            if (topKBadge) topKBadge.textContent = e.target.value;
        });
        if (tempInput) tempInput.addEventListener("input", e => {
            if (tempBadge) tempBadge.textContent = parseFloat(e.target.value).toFixed(1);
        });
    }

    function saveSettings() {
        const url = apiUrlInput ? apiUrlInput.value.trim() : location.origin;
        const topk = topKInput ? parseInt(topKInput.value, 10) : 5;
        const temp = tempInput ? parseFloat(tempInput.value) : 0.7;
        localStorage.setItem(KEYS.url, url);
        localStorage.setItem(KEYS.topk, String(topk));
        localStorage.setItem(KEYS.temp, String(temp));
        window.STUDY_COMPANION_API_BASE = url;
        toast("Settings saved.", "success");
    }

    async function testConnection() {
        const url = apiUrlInput ? apiUrlInput.value.trim() : location.origin;
        if (testConnBtn) {
            testConnBtn.disabled = true;
            var o = testConnBtn.innerHTML;
            testConnBtn.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> Testing…`;
        }
        try {
            const r = await fetch(`${url}/health`, { method: "GET" });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const h = await r.json();
            toast(`Connected · ${h.model_name || "model"} · ${h.index_size} chunks`, "success");
        } catch (e) {
            toast(`Connection failed: ${e.message}`, "error");
        } finally {
            if (testConnBtn) { testConnBtn.disabled = false; testConnBtn.innerHTML = o; }
        }
    }

    async function refreshStorage() {
        try {
            const r = await api.indexFiles();
            const total = r.total_chunks || 0;
            // Approx 1 GB per 5000 chunks (placeholder mapping)
            const usedGb = (total / 5000).toFixed(2);
            const capGb = 5;
            const pct = Math.min(100, (total / 5000) * 100);
            if (storageBar) storageBar.style.width = `${pct}%`;
            if (storageLabel) storageLabel.textContent = `${usedGb} GB / ${capGb} GB`;
            return r;
        } catch { return null; }
    }

    function injectFilesPanel(files) {
        // Inject an expandable file list under the Local Storage card if not present
        if (!storageCard) return;
        let panel = storageCard.querySelector(".sc-files-panel");
        if (!panel) {
            panel = document.createElement("details");
            panel.className = "sc-files-panel mt-md border border-outline-variant rounded-lg overflow-hidden";
            panel.innerHTML = `
                <summary class="flex justify-between items-center p-xs cursor-pointer hover:bg-surface-container-low list-none">
                    <span class="font-label-md text-label-md text-on-surface">Indexed Files (<span class="sc-files-count">${files.length}</span>)</span>
                    <span class="material-symbols-outlined text-on-surface-variant">expand_more</span>
                </summary>
                <div class="sc-files-list p-xs flex flex-col gap-xs border-t border-outline-variant"></div>
            `;
            // Insert above the bottom action button(s)
            const lastAction = storageCard.querySelector(".flex.flex-col.gap-sm.pt-sm, .flex.flex-col.gap-sm");
            if (lastAction) lastAction.parentElement.insertBefore(panel, lastAction);
            else storageCard.appendChild(panel);
        } else {
            panel.querySelector(".sc-files-count").textContent = files.length;
        }
        const list = panel.querySelector(".sc-files-list");
        list.innerHTML = files.length
            ? files.map(f => `
                <div class="flex items-center justify-between border border-outline-variant rounded p-xs bg-surface-bright">
                    <div class="flex items-center gap-xs overflow-hidden">
                        <span class="material-symbols-outlined text-secondary text-[18px]">description</span>
                        <span class="font-body-sm text-on-surface truncate">${escapeHtml(f.source)}</span>
                    </div>
                    <span class="font-label-sm text-on-surface-variant whitespace-nowrap ml-xs">${f.chunk_count} chunks</span>
                </div>`).join("")
            : `<p class="font-body-sm text-on-surface-variant">Nothing indexed yet.</p>`;
    }

    async function clearIndex() {
        if (!confirm("Delete the entire knowledge index? Raw uploads and flashcards are kept. This cannot be undone.")) return;
        if (clearBtn) {
            clearBtn.disabled = true;
            var o = clearBtn.innerHTML;
            clearBtn.innerHTML = `<span class="material-symbols-outlined animate-spin">progress_activity</span> Clearing…`;
        }
        try {
            const r = await api.clearIndex();
            toast(`Cleared ${r.deleted_chunks} chunks.`, "success");
            const files = await refreshStorage();
            if (files) injectFilesPanel(files.files || []);
            document.dispatchEvent(new CustomEvent("sc:index-changed"));
        } catch {} finally {
            if (clearBtn) { clearBtn.disabled = false; clearBtn.innerHTML = o; }
        }
    }

    // Inject a small Bookmarks card at the bottom of the right column
    async function injectBookmarks() {
        try {
            const r = await api.bookmarks();
            const bms = r.bookmarks || [];
            const container = storageCard ? storageCard.parentElement : null;
            if (!container) return;
            let card = container.querySelector(".sc-bookmarks-card");
            if (!card) {
                card = document.createElement("div");
                card.className = "sc-bookmarks-card bg-surface-container-lowest rounded-xl border border-outline-variant p-md mt-lg shadow-[0_2px_4px_rgba(0,32,69,0.05)]";
                container.appendChild(card);
            }
            card.innerHTML = `
                <div class="flex items-center gap-sm mb-md border-b border-surface-container pb-sm justify-between">
                    <div class="flex items-center gap-sm"><span class="material-symbols-outlined text-primary">bookmark</span><h3 class="font-headline-lg text-primary m-0" style="font-size:20px;line-height:28px;">Bookmarks</h3></div>
                    <span class="font-label-sm text-on-surface-variant">${bms.length}</span>
                </div>
                ${bms.length === 0
                    ? `<p class="font-body-sm text-on-surface-variant">Save outputs from the Study page to find them here.</p>`
                    : `<div class="flex flex-col gap-xs">
                        ${bms.slice(0, 10).map(b => `
                            <details class="border border-outline-variant rounded overflow-hidden">
                                <summary class="flex justify-between items-center p-xs cursor-pointer hover:bg-surface-container-low list-none">
                                    <div class="flex items-center gap-xs overflow-hidden">
                                        <span class="material-symbols-outlined text-secondary text-[16px]">bookmark</span>
                                        <span class="font-body-sm text-on-surface truncate">${escapeHtml(b.topic || "Untitled")}</span>
                                        <span class="font-label-sm text-on-surface-variant">${escapeHtml(b.mode || "")}</span>
                                    </div>
                                    <button data-bm="${b.id}" class="bm-del text-error" title="Delete"><span class="material-symbols-outlined text-[18px]">delete</span></button>
                                </summary>
                                <div class="p-xs border-t border-outline-variant text-body-sm">${renderMarkdown(b.content)}</div>
                            </details>`).join("")}
                    </div>`}
            `;
            card.querySelectorAll(".bm-del").forEach(b => b.addEventListener("click", async e => {
                e.preventDefault(); e.stopPropagation();
                await api.delBookmark(b.dataset.bm);
                toast("Bookmark removed.", "success");
                injectBookmarks();
            }));
        } catch {}
    }

    // ── Wire ───────────────────────────────────────────

    document.addEventListener("DOMContentLoaded", async () => {
        loadFromStorage();
        wireSliders();
        if (testConnBtn) testConnBtn.addEventListener("click", testConnection);
        if (saveBtn) saveBtn.addEventListener("click", saveSettings);
        if (discardBtn) discardBtn.addEventListener("click", () => {
            loadFromStorage();
            toast("Reverted.");
        });
        if (clearBtn) clearBtn.addEventListener("click", clearIndex);
        if (manageFilesBtn) manageFilesBtn.addEventListener("click", async () => {
            const r = await refreshStorage();
            if (r) injectFilesPanel(r.files || []);
        });

        const r = await refreshStorage();
        if (r) injectFilesPanel(r.files || []);
        injectBookmarks();
    });
})();
