// Settings page wiring.

(function () {
    const $ = id => document.getElementById(id);
    const KEYS = { url: "api_base_url", topk: "top_k", temp: "temperature" };

    let initial = {};
    let confirmCallback = null;

    function loadFromStorage() {
        initial = {
            url: localStorage.getItem(KEYS.url) || (window.STUDY_COMPANION_API_BASE || location.origin),
            topk: parseInt(localStorage.getItem(KEYS.topk) || "5", 10),
            temp: parseFloat(localStorage.getItem(KEYS.temp) || "0.7"),
        };
        $("api-url").value = initial.url;
        $("top-k").value = initial.topk;
        $("top-k-val").textContent = initial.topk;
        $("temperature").value = initial.temp;
        $("temperature-val").textContent = initial.temp.toFixed(1);
    }

    function wireSliders() {
        $("top-k").addEventListener("input", e => $("top-k-val").textContent = e.target.value);
        $("temperature").addEventListener("input", e => $("temperature-val").textContent = parseFloat(e.target.value).toFixed(1));
    }

    async function testConnection() {
        const url = $("api-url").value.trim();
        const status = $("conn-status");
        status.textContent = "Testing…";
        status.className = "font-label-sm text-on-surface-variant";
        try {
            const r = await fetch(`${url}/health`, { method: "GET" });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const h = await r.json();
            status.textContent = `✓ Connected · ${h.model_name || "model"} · ${h.index_size} chunks`;
            status.className = "font-label-sm text-success";
        } catch (e) {
            status.textContent = `✗ ${e.message || "Connection failed"}`;
            status.className = "font-label-sm text-error";
        }
    }

    function saveSettings() {
        const url = $("api-url").value.trim();
        const topk = parseInt($("top-k").value, 10);
        const temp = parseFloat($("temperature").value);
        localStorage.setItem(KEYS.url, url);
        localStorage.setItem(KEYS.topk, String(topk));
        localStorage.setItem(KEYS.temp, String(temp));
        window.STUDY_COMPANION_API_BASE = url;
        initial = { url, topk, temp };
        toast("Settings saved.", "success");
    }

    function discardChanges() { loadFromStorage(); toast("Reverted."); }

    function openConfirm(title, msg, cb) {
        $("confirm-title").textContent = title;
        $("confirm-msg").textContent = msg;
        confirmCallback = cb;
        $("confirm-bg").classList.add("show");
    }
    function closeConfirm() { $("confirm-bg").classList.remove("show"); confirmCallback = null; }

    async function loadIndexFiles() {
        try {
            const r = await api.indexFiles();
            $("idx-chunks").textContent = (r.total_chunks ?? 0).toLocaleString();
            $("idx-fill").style.width = `${Math.min(100, (r.total_chunks / 5000) * 100)}%`;
            $("idx-files-count").textContent = (r.files || []).length;
            const root = $("idx-files-list");
            if (!r.files.length) {
                root.innerHTML = `<p class="font-body-sm text-on-surface-variant">Nothing indexed yet.</p>`;
            } else {
                root.innerHTML = r.files.map(f => `
                    <div class="flex items-center justify-between border border-outline-variant rounded p-xs bg-surface-bright">
                        <div class="flex items-center gap-xs overflow-hidden">
                            <span class="material-symbols-outlined text-secondary text-[18px]">description</span>
                            <span class="font-body-sm text-on-surface truncate">${escapeHtml(f.source)}</span>
                        </div>
                        <span class="font-label-sm text-on-surface-variant whitespace-nowrap ml-xs">${f.chunk_count} chunks</span>
                    </div>`).join("");
            }
        } catch {}
    }

    async function clearIndex() {
        openConfirm(
            "Clear knowledge index?",
            "This permanently deletes all indexed chunks and FAISS/BM25 indices. Your raw uploads in data/raw and your flashcards are kept.",
            async () => {
                closeConfirm();
                try {
                    const r = await api.clearIndex();
                    toast(`Cleared ${r.deleted_chunks} chunks.`, "success");
                    await loadIndexFiles();
                } catch {}
            }
        );
    }

    async function loadBookmarks() {
        try {
            const r = await api.bookmarks();
            const root = $("bookmarks-list");
            if (!r.bookmarks.length) {
                root.innerHTML = `<p class="font-body-sm text-on-surface-variant">No bookmarks yet. Save outputs from the Study page.</p>`;
                return;
            }
            root.innerHTML = r.bookmarks.map(b => {
                const preview = (b.content || "").slice(0, 200).replace(/\n+/g, " ");
                return `
                <details class="border border-outline-variant rounded-lg overflow-hidden">
                    <summary class="flex justify-between items-center p-xs cursor-pointer hover:bg-surface-container-low list-none">
                        <div class="flex items-center gap-xs overflow-hidden">
                            <span class="material-symbols-outlined text-secondary text-[18px]">bookmark</span>
                            <div class="overflow-hidden">
                                <div class="font-label-md text-on-surface truncate">${escapeHtml(b.topic || "Untitled")}</div>
                                <div class="font-label-sm text-on-surface-variant truncate">${escapeHtml(b.mode || "")} · ${escapeHtml(b.created_at || "")}</div>
                            </div>
                        </div>
                        <div class="flex gap-xs items-center">
                            <button data-bm="${b.id}" class="bm-del text-error hover:underline font-label-sm" title="Delete">
                                <span class="material-symbols-outlined text-[18px]">delete</span>
                            </button>
                            <span class="material-symbols-outlined text-on-surface-variant">expand_more</span>
                        </div>
                    </summary>
                    <div class="p-sm border-t border-outline-variant prose-sc text-body-sm">${renderMarkdown(b.content)}</div>
                </details>`;
            }).join("");
            root.querySelectorAll(".bm-del").forEach(b => b.addEventListener("click", async e => {
                e.preventDefault();
                e.stopPropagation();
                await api.delBookmark(b.dataset.bm);
                toast("Bookmark removed.", "success");
                loadBookmarks();
            }));
        } catch {}
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadFromStorage();
        wireSliders();
        $("test-conn").addEventListener("click", testConnection);
        $("save-settings").addEventListener("click", saveSettings);
        $("discard-settings").addEventListener("click", discardChanges);
        $("manage-files").addEventListener("click", loadIndexFiles);
        $("clear-index").addEventListener("click", clearIndex);
        $("bookmarks-refresh").addEventListener("click", loadBookmarks);
        $("confirm-cancel").addEventListener("click", closeConfirm);
        $("confirm-bg").addEventListener("click", e => { if (e.target === $("confirm-bg")) closeConfirm(); });
        $("confirm-ok").addEventListener("click", () => { if (confirmCallback) confirmCallback(); });

        loadIndexFiles();
        loadBookmarks();
    });
})();
