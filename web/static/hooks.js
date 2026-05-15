// Shared hooks — wires sidebar Upload, topbar Search, New Session, and
// a System Health refresh on every page. Targets the Stitch DOM by visible
// text, so the HTML itself is never modified.

(function () {
    // ── Find sidebar buttons by their visible label ─────

    function findByText(selector, label) {
        const re = new RegExp(`\\b${label}\\b`, "i");
        for (const el of document.querySelectorAll(selector)) {
            if (re.test((el.textContent || "").trim())) return el;
        }
        return null;
    }

    // ── Toast container (injected once) ─────────────────

    function ensureToast() {
        let el = document.getElementById("sc-toast");
        if (!el) {
            el = document.createElement("div");
            el.id = "sc-toast";
            el.style.cssText = `
                position: fixed; bottom: 24px; right: 24px; z-index: 9999;
                background: #233144; color: #ebf1ff; padding: 12px 20px;
                border-radius: 6px; font-family: 'Hanken Grotesk', sans-serif;
                font-size: 14px; box-shadow: 0 10px 25px rgba(0,32,69,0.15);
                opacity: 0; transform: translateY(12px); transition: all 0.2s ease;
                pointer-events: none; max-width: 360px;
            `;
            document.body.appendChild(el);
        }
        return el;
    }
    window.toast = function (msg, kind = "") {
        const el = ensureToast();
        el.textContent = msg;
        el.style.background = kind === "error" ? "#ba1a1a"
            : kind === "success" ? "#2e7d32" : "#233144";
        el.style.opacity = "1";
        el.style.transform = "translateY(0)";
        clearTimeout(el._t);
        el._t = setTimeout(() => {
            el.style.opacity = "0";
            el.style.transform = "translateY(12px)";
        }, 3000);
    };

    // ── Upload modal (injected once) ────────────────────

    function buildUploadModal() {
        if (document.getElementById("sc-upload-modal")) return;
        const wrap = document.createElement("div");
        wrap.id = "sc-upload-modal";
        wrap.style.cssText = `
            position: fixed; inset: 0; background: rgba(13,28,47,0.45); z-index: 9000;
            display: none; align-items: center; justify-content: center; padding: 16px;
        `;
        wrap.innerHTML = `
            <div style="background:#fff; border-radius:8px; max-width:520px; width:100%;
                        box-shadow: 0 10px 25px rgba(0,32,69,0.20); padding:24px;
                        font-family: 'Hanken Grotesk', sans-serif;">
                <h3 style="margin:0 0 4px 0; color:#002045; font-size:20px; font-weight:700;">Upload Material</h3>
                <p style="margin:0 0 16px 0; color:#43474e; font-size:14px;">PDF, DOCX, TXT, MD, images, or a URL — chunked, embedded, and indexed locally.</p>

                <div id="sc-drop" style="border:2px dashed #64a8fe; background:rgba(100,168,254,0.05);
                                        border-radius:6px; padding:24px; text-align:center; cursor:pointer; transition:all .15s;">
                    <div style="font-size:32px; color:#0060ac;">
                        <span class="material-symbols-outlined" style="font-size:32px;">cloud_upload</span>
                    </div>
                    <div style="font-weight:600; color:#002045; margin-top:4px;">Click to select or drop files</div>
                    <div id="sc-file-list" style="margin-top:8px; font-size:13px; color:#43474e;"></div>
                </div>
                <input id="sc-file-input" type="file" multiple style="display:none"
                       accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.html,.htm" />

                <div style="margin-top:14px;">
                    <label style="font-size:12px; color:#43474e; text-transform:uppercase; letter-spacing:.05em; font-weight:600;">Or paste a URL</label>
                    <input id="sc-url-input" type="text" placeholder="https://…"
                           style="width:100%; margin-top:4px; padding:10px 12px; border:1px solid #c4c6cf; border-radius:4px; font-family:'Literata',serif; font-size:14px;" />
                </div>

                <div style="display:flex; gap:8px; justify-content:flex-end; margin-top:20px;">
                    <button id="sc-upload-cancel" style="padding:10px 16px; border:1px solid #c4c6cf; background:#fff; color:#002045; border-radius:4px; font-weight:600; cursor:pointer;">Cancel</button>
                    <button id="sc-upload-go" style="padding:10px 20px; background:#002045; color:#fff; border:none; border-radius:4px; font-weight:600; cursor:pointer; display:inline-flex; align-items:center; gap:6px;">
                        <span class="material-symbols-outlined" style="font-size:18px;">cloud_upload</span>
                        Ingest
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(wrap);

        const drop = wrap.querySelector("#sc-drop");
        const fi = wrap.querySelector("#sc-file-input");
        const list = wrap.querySelector("#sc-file-list");
        const urlIn = wrap.querySelector("#sc-url-input");

        drop.addEventListener("click", () => fi.click());
        fi.addEventListener("change", () => updateFileList());
        ["dragover", "dragenter"].forEach(ev => drop.addEventListener(ev, e => {
            e.preventDefault(); drop.style.background = "rgba(100,168,254,0.15)";
        }));
        ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => {
            e.preventDefault(); drop.style.background = "rgba(100,168,254,0.05)";
        }));
        drop.addEventListener("drop", e => {
            e.preventDefault();
            fi.files = e.dataTransfer.files;
            updateFileList();
        });
        function updateFileList() {
            const f = Array.from(fi.files || []);
            list.textContent = f.length ? f.map(x => x.name).join(", ") : "";
        }

        wrap.querySelector("#sc-upload-cancel").addEventListener("click", closeUpload);
        wrap.addEventListener("click", e => { if (e.target === wrap) closeUpload(); });
        wrap.querySelector("#sc-upload-go").addEventListener("click", async () => {
            const files = Array.from(fi.files || []);
            const url = (urlIn.value || "").trim();
            if (!files.length && !url) { window.toast("Add a file or URL first."); return; }
            const fd = new FormData();
            files.forEach(f => fd.append("files", f));
            const btn = wrap.querySelector("#sc-upload-go");
            btn.disabled = true;
            btn.innerHTML = `<span class="material-symbols-outlined" style="font-size:18px;">progress_activity</span> Indexing…`;
            try {
                const r = await api.ingest(fd, url || null);
                window.toast(`Indexed ${r.chunks_added} chunks from ${r.sources.length} source(s).`, "success");
                fi.value = ""; urlIn.value = ""; updateFileList();
                refreshHealth();
                document.dispatchEvent(new CustomEvent("sc:index-changed"));
                closeUpload();
            } catch { /* toast shown by apiFetch */ }
            finally {
                btn.disabled = false;
                btn.innerHTML = `<span class="material-symbols-outlined" style="font-size:18px;">cloud_upload</span> Ingest`;
            }
        });
    }

    function openUpload() {
        buildUploadModal();
        document.getElementById("sc-upload-modal").style.display = "flex";
    }
    function closeUpload() {
        const m = document.getElementById("sc-upload-modal");
        if (m) m.style.display = "none";
    }
    window.scOpenUpload = openUpload;

    // ── Topbar Search ───────────────────────────────────

    function wireTopbarSearch() {
        const input = Array.from(document.querySelectorAll("input[type=text]"))
            .find(i => (i.placeholder || "").toLowerCase().includes("search"));
        if (!input) return;

        // Inject results dropdown anchored under the input's parent
        const parent = input.parentElement;
        parent.style.position = parent.style.position || "relative";
        const dd = document.createElement("div");
        dd.style.cssText = `
            position: absolute; top: calc(100% + 4px); left: 0; right: 0;
            background: #fff; border: 1px solid #c4c6cf; border-radius: 6px;
            box-shadow: 0 10px 25px rgba(0,32,69,0.15); z-index: 80;
            max-height: 420px; overflow-y: auto; display: none;
        `;
        parent.appendChild(dd);

        let t;
        input.addEventListener("input", () => {
            clearTimeout(t);
            const q = input.value.trim();
            if (!q) { dd.style.display = "none"; dd.innerHTML = ""; return; }
            t = setTimeout(async () => {
                try {
                    const r = await api.search(q, 8);
                    if (!r.hits.length) {
                        dd.innerHTML = `<div style="padding:10px 12px; color:#43474e; font-size:13px;">No matches.</div>`;
                    } else {
                        dd.innerHTML = r.hits.map(h => `
                            <div style="padding:8px 12px; border-bottom:1px solid #eff4ff; cursor:pointer;"
                                 onmouseover="this.style.background='#eff4ff'" onmouseout="this.style.background='transparent'">
                                <div style="display:flex; gap:8px; align-items:center; margin-bottom:2px;">
                                    <span style="font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:#43474e; font-weight:600;">${h.kind}</span>
                                    <span style="font-size:13px; color:#0d1c2f; font-weight:600;">${escapeHtml(h.title)}</span>
                                </div>
                                <div style="font-size:12px; color:#43474e;">${escapeHtml(h.snippet)}</div>
                            </div>
                        `).join("");
                    }
                    dd.style.display = "block";
                } catch {}
            }, 220);
        });
        document.addEventListener("click", e => {
            if (!parent.contains(e.target)) dd.style.display = "none";
        });
    }

    // ── New Session ─────────────────────────────────────

    function wireNewSession() {
        const btn = findByText("button, a", "New Session");
        if (!btn) return;
        btn.addEventListener("click", e => {
            e.preventDefault();
            document.dispatchEvent(new CustomEvent("sc:new-session"));
            window.toast("New session started.", "success");
        });
    }

    // ── Upload button ───────────────────────────────────

    function wireUploadButton() {
        const btn = findByText("button", "Upload Document");
        if (!btn) return;
        btn.addEventListener("click", e => { e.preventDefault(); openUpload(); });
    }

    // ── Help (open API docs) ────────────────────────────

    function wireHelp() {
        document.querySelectorAll("button, a").forEach(el => {
            const inner = (el.innerHTML || "");
            if (/material-symbols-outlined[^>]*>help</.test(inner) && !el.dataset.scHelp) {
                el.dataset.scHelp = "1";
                el.addEventListener("click", e => {
                    e.preventDefault();
                    window.open("/docs", "_blank");
                });
            }
        });
    }

    // ── System Health (sidebar footer) ──────────────────

    async function refreshHealth() {
        try {
            const h = await api.health();
            // Find "System Health" anchor/text and append/update a small status line under it
            const link = findByText("a", "System Health");
            if (link) {
                let badge = link.querySelector(".sc-health-badge");
                if (!badge) {
                    badge = document.createElement("span");
                    badge.className = "sc-health-badge";
                    badge.style.cssText = "margin-left:auto; font-size:11px; padding:2px 8px; border-radius:9999px; font-weight:600;";
                    link.appendChild(badge);
                }
                const ok = h.model_loaded;
                badge.textContent = ok ? "OK" : "Down";
                badge.style.background = ok ? "#e6f4ea" : "#ffdad6";
                badge.style.color = ok ? "#2e7d32" : "#93000a";
            }
            // Expose to pages via event
            document.dispatchEvent(new CustomEvent("sc:health", { detail: h }));
        } catch {}
    }
    window.refreshHealth = refreshHealth;

    // ── Markdown + escape helpers (exposed globally) ───

    window.escapeHtml = function (s) {
        return (s || "").replace(/[&<>"']/g, c =>
            ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    };

    window.renderMarkdown = function (md) {
        if (!md) return "";
        let html = escapeHtml(md);
        html = html.replace(/```([\s\S]*?)```/g, (_, code) =>
            `<pre style="background:#0d1c2f;color:#ebf1ff;padding:12px 16px;border-radius:6px;overflow-x:auto;font-size:13px;"><code>${code.trim()}</code></pre>`);
        html = html.replace(/`([^`]+)`/g,
            `<code style="background:#eff4ff;padding:2px 6px;border-radius:4px;font-size:13px;">$1</code>`);
        html = html.replace(/^####\s+(.+)$/gm, '<h4 style="font-family:Hanken Grotesk;color:#0d1c2f;font-weight:600;font-size:14px;margin:16px 0 6px 0;">$1</h4>');
        html = html.replace(/^###\s+(.+)$/gm, '<h3 class="font-label-md text-label-md font-bold text-on-surface mt-lg mb-sm">$1</h3>');
        html = html.replace(/^##\s+(.+)$/gm, '<h2 class="font-headline-lg-mobile text-headline-lg-mobile text-primary mt-lg mb-sm font-bold">$1</h2>');
        html = html.replace(/^#\s+(.+)$/gm, '<h1 class="font-headline-lg text-headline-lg text-primary mb-md">$1</h1>');
        html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>");
        html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote style="border-left:4px solid #64a8fe;background:#eff4ff;color:#43474e;padding:8px 16px;margin:16px 0;border-radius:0 4px 4px 0;">$1</blockquote>');
        html = html.replace(/(^|\n)((?:- [^\n]+\n?)+)/g, (_, pre, block) => {
            const items = block.trim().split(/\n/).map(l => `<li>${l.replace(/^- /, "")}</li>`).join("");
            return `${pre}<ul class="list-disc pl-md mb-md space-y-1 text-on-surface-variant">${items}</ul>`;
        });
        html = html.replace(/(^|\n)((?:\d+\. [^\n]+\n?)+)/g, (_, pre, block) => {
            const items = block.trim().split(/\n/).map(l => `<li>${l.replace(/^\d+\.\s+/, "")}</li>`).join("");
            return `${pre}<ol class="list-decimal pl-md mb-md space-y-1 text-on-surface-variant">${items}</ol>`;
        });
        html = html.split(/\n{2,}/).map(p => {
            if (/^\s*<(h\d|ul|ol|pre|blockquote)/.test(p)) return p;
            return `<p class="mb-sm text-on-surface-variant">${p.replace(/\n/g, "<br>")}</p>`;
        }).join("\n");
        return html;
    };

    // ── Bootstrap ───────────────────────────────────────

    document.addEventListener("DOMContentLoaded", () => {
        wireUploadButton();
        wireTopbarSearch();
        wireNewSession();
        wireHelp();
        refreshHealth();
    });
})();
