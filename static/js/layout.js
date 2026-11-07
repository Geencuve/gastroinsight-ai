/* GastroInsight AI · Barra lateral, página activa, pestañas y ajuste a la ventana. */
(function () {
    "use strict";
    const sidebar = document.querySelector(".app-sidebar");
    const header = sidebar ? sidebar.parentElement : null;

    function syncHeader() {
        if (!header) return;
        const height = Math.round(header.getBoundingClientRect().height);
        document.documentElement.style.setProperty("--app-header", `${height > 30 && height < 160 ? height : 64}px`);
    }

    if (sidebar) {
        // El encabezado usa backdrop-filter, que "atrapa" a los elementos fijos: la barra lateral
        // se mueve al <body> para que se fije a la ventana.
        if (header !== document.body) document.body.prepend(sidebar);
        document.body.classList.add("has-sidebar");
        syncHeader();
        window.addEventListener("resize", syncHeader);

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "sidebar-toggle";
        toggle.setAttribute("aria-label", "Abrir menú");
        toggle.textContent = "☰";
        document.body.appendChild(toggle);
        toggle.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
        document.addEventListener("click", (event) => {
            if (document.body.classList.contains("sidebar-open") && !event.target.closest(".app-sidebar, .sidebar-toggle")) {
                document.body.classList.remove("sidebar-open");
            }
        });

        let best = null;
        sidebar.querySelectorAll(".side-link[href]").forEach((link) => {
            const path = new URL(link.getAttribute("href"), location.origin).pathname;
            const match = path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);
            if (match && (!best || path.length > best.path.length)) best = { link, path };
        });
        if (best) best.link.classList.add("is-active");
    }

    function activate(container, index) {
        const buttons = container.querySelectorAll(":scope > .tab-bar [data-tab-button]");
        const panels = container.querySelectorAll(":scope > [data-tab-panel]");
        buttons.forEach((b, i) => { b.classList.toggle("is-active", i === index); b.setAttribute("aria-selected", i === index); });
        panels.forEach((p, i) => { p.hidden = i !== index; });
        try { sessionStorage.setItem(`gi-tab-${location.pathname}-${container.dataset.tabs || "x"}`, String(index)); } catch (e) { /* sin almacenamiento */ }
    }

    function initTabs(container) {
        const buttons = container.querySelectorAll(":scope > .tab-bar [data-tab-button]");
        buttons.forEach((button, index) => button.addEventListener("click", () => activate(container, index)));
        let saved = 0;
        try { saved = parseInt(sessionStorage.getItem(`gi-tab-${location.pathname}-${container.dataset.tabs || "x"}`) || "0", 10); } catch (e) { saved = 0; }
        activate(container, saved < buttons.length ? saved : 0);
    }

    const ideas = [...document.querySelectorAll(".idea-section")];
    if (ideas.length >= 2 && ideas.every((s) => s.parentElement === ideas[0].parentElement)) {
        const container = document.createElement("div");
        container.dataset.tabs = "ideas";
        const bar = document.createElement("div");
        bar.className = "tab-bar";
        bar.setAttribute("role", "tablist");
        ideas[0].before(container);
        container.appendChild(bar);
        ideas.forEach((section) => {
            const heading = section.querySelector("h2");
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.tabButton = "";
            button.setAttribute("role", "tab");
            button.textContent = heading ? heading.textContent.trim() : "Sección";
            bar.appendChild(button);
            section.dataset.tabPanel = "";
            section.classList.add("tab-panel");
            container.appendChild(section);
        });
    }
    document.querySelectorAll("[data-tabs]").forEach(initTabs);
})();
