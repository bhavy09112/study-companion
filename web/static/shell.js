// Shared application shell — sidebar + topbar.
// Each HTML page just sets <body data-page="..."> and contains an empty
// <div id="shell-root"></div> at the top of <body>. This script populates it.

(function () {
    const NAV_ITEMS = [
        { id: "study",      href: "/",             icon: "book_2",    label: "Study" },
        { id: "quiz",       href: "/quiz",         icon: "quiz",      label: "Quiz" },
        { id: "flashcards", href: "/flashcards",   icon: "style",     label: "Flashcards" },
        { id: "progress",   href: "/progress-page",icon: "analytics", label: "Progress" },
        { id: "settings",   href: "/settings",     icon: "settings",  label: "Settings" },
    ];

    function navHtml(activeId) {
        return NAV_ITEMS.map(it => {
            const active = it.id === activeId;
            const cls = active
                ? "nav-active flex items-center gap-sm px-sm py-[8px] rounded-lg text-primary font-bold border-r-2 border-primary bg-surface-container-high transition-all"
                : "flex items-center gap-sm px-sm py-[8px] rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-low transition-colors duration-200";
            const iconCls = active ? "material-symbols-outlined icon-fill" : "material-symbols-outlined";
            return `<a class="${cls}" href="${it.href}" data-nav="${it.id}">
                        <span class="${iconCls}">${it.icon}</span>
                        <span class="font-label-md text-label-md">${it.label}</span>
                    </a>`;
        }).join("\n");
    }

    function renderShell() {
        const active = document.body.dataset.page || "study";
        const root = document.getElementById("shell-root");
        if (!root) return;

        root.innerHTML = `
<!-- Sidebar -->
<nav class="bg-surface h-screen w-64 fixed left-0 top-0 border-r border-outline-variant flex flex-col py-md px-sm z-50">
    <a href="/" class="flex items-center gap-xs px-xs mb-lg no-underline">
        <div class="w-9 h-9 rounded-lg bg-primary flex items-center justify-center text-on-primary font-bold font-label-md">SC</div>
        <div>
            <h1 class="font-headline-lg text-primary text-[16px] leading-[20px] m-0 font-bold">Study Companion</h1>
            <p class="font-label-sm text-on-surface-variant m-0 uppercase tracking-wider">AI Assistant</p>
        </div>
    </a>

    <!-- Upload CTA -->
    <button id="sb-upload-btn" class="bg-primary text-on-primary font-label-md text-label-md rounded-lg py-xs px-sm mb-sm flex items-center justify-center gap-xs hover:bg-primary-container transition-colors duration-200 w-full">
        <span class="material-symbols-outlined text-[18px]">upload_file</span>
        Upload Document
    </button>
    <input type="file" id="sb-file" multiple class="hidden"
           accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.html,.htm" />
    <input type="text" id="sb-url" placeholder="…or paste a URL"
           class="w-full border border-outline-variant bg-surface-bright rounded-lg py-[6px] px-sm font-body-sm text-body-sm text-on-surface focus:outline-none focus:border-secondary mb-xs" />
    <button id="sb-ingest" class="border border-outline-variant text-primary hover:bg-surface-container-low font-label-md text-label-md rounded-lg py-[6px] px-sm flex items-center justify-center gap-xs transition-colors w-full mb-base">
        <span class="material-symbols-outlined text-[16px]">cloud_upload</span>
        Ingest
    </button>
    <p id="sb-upload-status" class="font-label-sm text-on-surface-variant px-xs mb-md min-h-[16px]"></p>

    <!-- Nav -->
    <div class="flex flex-col gap-base flex-1">
        ${navHtml(active)}
    </div>

    <!-- Footer / Health -->
    <div class="border-t border-outline-variant pt-sm">
        <div class="flex items-center gap-xs px-xs mb-xs">
            <span id="health-dot" class="w-2 h-2 rounded-full bg-surface-container"></span>
            <span class="font-label-sm text-on-surface-variant">System Health</span>
        </div>
        <div class="px-xs font-label-sm text-on-surface-variant leading-tight">
            <div>Model: <span id="health-model" class="text-primary font-bold">—</span></div>
            <div class="truncate" title=""><span id="health-model-name" class="text-on-surface-variant"></span></div>
            <div>Index: <span id="health-index" class="text-primary font-bold">0</span> · Cards: <span id="health-cards" class="text-primary font-bold">0</span></div>
        </div>
    </div>
</nav>

<!-- Top bar -->
<header class="bg-surface fixed top-0 right-0 z-40 border-b border-outline-variant flex justify-between items-center px-md h-16 ml-64 w-[calc(100%-16rem)]">
    <div class="flex-grow max-w-md relative">
        <span class="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant">search</span>
        <input id="topbar-search" type="text"
               class="w-full bg-surface-container-lowest border border-outline-variant rounded-full py-[6px] pl-10 pr-sm font-body-sm text-body-sm text-on-surface focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary transition-shadow"
               placeholder="Search resources, cards, chunks…" />
        <div id="topbar-search-results" class="sc-search-results hidden"></div>
    </div>
    <div class="flex items-center gap-md">
        <button id="topbar-new-session" class="text-primary font-label-md text-label-md hover:text-primary-container transition-colors">New Session</button>
        <a href="https://github.com/" target="_blank" rel="noopener" class="text-on-surface-variant hover:text-primary hover:bg-surface-container-low rounded-full p-1 transition-colors flex items-center justify-center">
            <span class="material-symbols-outlined">help</span>
        </a>
    </div>
</header>

<!-- Spacer so main content starts below sticky header -->
<div class="h-16 ml-64"></div>
        `;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", renderShell);
    } else {
        renderShell();
    }
})();
