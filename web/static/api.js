// Shared API client + UI helpers for Study Companion frontend.
// All HTML pages load this file; per-page scripts (study.js, quiz.js, …) consume it.

const API_BASE = window.STUDY_COMPANION_API_BASE
    || (location.port ? `${location.protocol}//${location.hostname}:${location.port}` : location.origin);

// ── HTTP wrapper ────────────────────────────────────────

async function apiFetch(path, { method = "GET", body, formData, params, silent = false } = {}) {
    let url = `${API_BASE}${path}`;
    if (params) {
        const q = new URLSearchParams(params).toString();
        if (q) url += `?${q}`;
    }
    const opts = { method, headers: {} };
    if (formData) {
        opts.body = formData;
    } else if (body !== undefined) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    try {
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            let detail = `${resp.status} ${resp.statusText}`;
            try {
                const data = await resp.json();
                if (data.detail) detail = data.detail;
            } catch {}
            if (!silent) toast(detail, "error");
            const err = new Error(detail);
            err.status = resp.status;
            throw err;
        }
        const ctype = resp.headers.get("content-type") || "";
        if (ctype.includes("application/json")) return await resp.json();
        return await resp.blob();
    } catch (e) {
        if (!silent && e.message && !e.status) toast(`Cannot reach API: ${e.message}`, "error");
        throw e;
    }
}

const api = {
    health:     ()                    => apiFetch("/health", { silent: true }),
    generate:   (b)                   => apiFetch("/generate", { method: "POST", body: b }),
    refine:     (b)                   => apiFetch("/generate/refine", { method: "POST", body: b }),
    ingest:     (fd, urlsParam)       => apiFetch(`/ingest${urlsParam ? `?urls=${encodeURIComponent(urlsParam)}` : ""}`, { method: "POST", formData: fd }),
    search:     (q, limit = 8)        => apiFetch("/search", { params: { q, limit } }),
    quizStart:  (b)                   => apiFetch("/quiz/start", { method: "POST", body: b }),
    quizSubmit: (b)                   => apiFetch("/quiz/submit", { method: "POST", body: b }),
    quizHint:   (b)                   => apiFetch("/quiz/hint", { method: "POST", body: b }),
    quizFlag:   (b)                   => apiFetch("/quiz/flag", { method: "POST", body: b, silent: true }),
    fcDue:      ()                    => apiFetch("/flashcards/due"),
    fcReview:   (b)                   => apiFetch("/flashcards/review", { method: "POST", body: b }),
    fcUndo:     (b)                   => apiFetch("/flashcards/undo", { method: "POST", body: b, silent: true }),
    fcFromText: (b)                   => apiFetch("/flashcards/from-text", { method: "POST", body: b }),
    progress:   ()                    => apiFetch("/progress"),
    dashboard:  ()                    => apiFetch("/dashboard"),
    sessions:   (limit = 10)          => apiFetch("/sessions/recent", { params: { limit } }),
    heatmap:    (days = 30)           => apiFetch("/activity/heatmap", { params: { days } }),
    logSession: (b)                   => apiFetch("/sessions", { method: "POST", body: b, silent: true }),
    indexFiles: ()                    => apiFetch("/index/files"),
    clearIndex: ()                    => apiFetch("/index", { method: "DELETE" }),
    bookmarks:  ()                    => apiFetch("/bookmarks"),
    addBookmark: (b)                  => apiFetch("/bookmarks", { method: "POST", body: b }),
    delBookmark: (id)                 => apiFetch(`/bookmarks/${id}`, { method: "DELETE" }),
    exportAnki: ()                    => apiFetch("/export/anki"),
};

// ── Toast ───────────────────────────────────────────────

function toast(message, kind = "") {
    let el = document.getElementById("sc-toast");
    if (!el) {
        el = document.createElement("div");
        el.id = "sc-toast";
        el.className = "sc-toast";
        document.body.appendChild(el);
    }
    el.className = `sc-toast ${kind}`;
    el.textContent = message;
    requestAnimationFrame(() => el.classList.add("show"));
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("show"), 3200);
}

// ── Markdown renderer (minimal, safe) ──────────────────

function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderMarkdown(md) {
    if (!md) return "";
    let html = escapeHtml(md);
    // Code blocks ```…```
    html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Headings (process in order #### -> #)
    html = html.replace(/^####\s+(.+)$/gm, "<h4>$1</h4>");
    html = html.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>");
    // Bold / italic
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>");
    // Blockquote
    html = html.replace(/^&gt;\s?(.+)$/gm, "<blockquote>$1</blockquote>");
    // Unordered lists
    html = html.replace(/(^|\n)((?:- [^\n]+\n?)+)/g, (_, pre, block) => {
        const items = block.trim().split(/\n/).map(l => `<li>${l.replace(/^- /, "")}</li>`).join("");
        return `${pre}<ul>${items}</ul>`;
    });
    // Ordered lists
    html = html.replace(/(^|\n)((?:\d+\. [^\n]+\n?)+)/g, (_, pre, block) => {
        const items = block.trim().split(/\n/).map(l => `<li>${l.replace(/^\d+\.\s+/, "")}</li>`).join("");
        return `${pre}<ol>${items}</ol>`;
    });
    // Paragraphs from remaining blank-line-separated chunks
    html = html.split(/\n{2,}/).map(p => {
        if (/^\s*<(h\d|ul|ol|pre|blockquote)/.test(p)) return p;
        return `<p>${p.replace(/\n/g, "<br>")}</p>`;
    }).join("\n");
    return html;
}

// ── Sidebar / Topbar wiring (shared across pages) ──────

function highlightActiveNav() {
    document.querySelectorAll("[data-nav]").forEach(a => {
        if (a.dataset.nav === document.body.dataset.page) {
            a.classList.add("nav-active");
        }
    });
}

function wireSidebarUpload() {
    const btn = document.getElementById("sb-upload-btn");
    const fileInput = document.getElementById("sb-file");
    const urlInput = document.getElementById("sb-url");
    const ingestBtn = document.getElementById("sb-ingest");
    const status = document.getElementById("sb-upload-status");
    if (!ingestBtn) return;

    if (btn && fileInput) btn.addEventListener("click", () => fileInput.click());

    if (fileInput) fileInput.addEventListener("change", () => {
        if (status && fileInput.files.length) {
            status.textContent = `${fileInput.files.length} file(s) ready`;
        }
    });

    ingestBtn.addEventListener("click", async () => {
        const files = fileInput ? fileInput.files : [];
        const url = urlInput ? urlInput.value.trim() : "";
        if (!files.length && !url) { toast("Pick a file or paste a URL first."); return; }
        const fd = new FormData();
        for (const f of files) fd.append("files", f);
        ingestBtn.disabled = true;
        ingestBtn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span> Uploading…';
        try {
            const r = await api.ingest(fd, url || null);
            toast(`Added ${r.chunks_added} chunks from ${r.sources.length} source(s).`, "success");
            if (status) status.textContent = "Indexed ✓";
            if (fileInput) fileInput.value = "";
            if (urlInput) urlInput.value = "";
            refreshHealth();
        } catch (e) { /* toast shown by apiFetch */ }
        finally {
            ingestBtn.disabled = false;
            ingestBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">upload_file</span> Upload &amp; Ingest';
        }
    });
}

let _searchTimer = null;
function wireTopbarSearch() {
    const input = document.getElementById("topbar-search");
    const results = document.getElementById("topbar-search-results");
    if (!input || !results) return;

    input.addEventListener("input", () => {
        clearTimeout(_searchTimer);
        const q = input.value.trim();
        if (!q) { results.classList.add("hidden"); results.innerHTML = ""; return; }
        _searchTimer = setTimeout(async () => {
            try {
                const r = await api.search(q, 8);
                if (!r.hits.length) {
                    results.innerHTML = `<div class="sc-search-result text-on-surface-variant">No matches.</div>`;
                } else {
                    results.innerHTML = r.hits.map(h => `
                        <div class="sc-search-result">
                            <div class="flex gap-2 items-center mb-1">
                                <span class="text-[11px] uppercase tracking-wider text-on-surface-variant font-label-md">${h.kind}</span>
                                <span class="font-label-md text-on-surface truncate">${escapeHtml(h.title)}</span>
                            </div>
                            <div class="text-[12px] text-on-surface-variant font-body-sm leading-snug">${escapeHtml(h.snippet)}</div>
                        </div>
                    `).join("");
                }
                results.classList.remove("hidden");
            } catch {}
        }, 220);
    });

    document.addEventListener("click", e => {
        if (!input.contains(e.target) && !results.contains(e.target)) {
            results.classList.add("hidden");
        }
    });
}

function wireNewSession() {
    const btn = document.getElementById("topbar-new-session");
    if (!btn) return;
    btn.addEventListener("click", () => {
        // Clear page-specific volatile state via custom event
        document.dispatchEvent(new CustomEvent("sc:new-session"));
        toast("New session started.", "success");
    });
}

async function refreshHealth() {
    const m = document.getElementById("health-model");
    const i = document.getElementById("health-index");
    const c = document.getElementById("health-cards");
    const n = document.getElementById("health-model-name");
    const dot = document.getElementById("health-dot");
    if (!m && !i) return;
    try {
        const h = await api.health();
        if (m) m.textContent = h.model_loaded ? "Ready" : "Down";
        if (i) i.textContent = h.index_size?.toLocaleString() ?? "0";
        if (c) c.textContent = h.db_cards?.toLocaleString() ?? "0";
        if (n) n.textContent = h.model_name || "—";
        if (dot) dot.className = `w-2 h-2 rounded-full ${h.model_loaded ? "bg-success" : "bg-error"}`;
    } catch {
        if (m) m.textContent = "Offline";
        if (dot) dot.className = "w-2 h-2 rounded-full bg-error";
    }
}

// ── Bootstrap ──────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    highlightActiveNav();
    wireSidebarUpload();
    wireTopbarSearch();
    wireNewSession();
    refreshHealth();
});
