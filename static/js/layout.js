/* GastroInsight AI · Barra lateral, página activa, pestañas y ajuste a la ventana. */
(function () {
    "use strict";
    // Incrustada en una pestaña (Visión IA): por la marca ?embed=1 o porque está dentro de otra página,
    // aunque una redirección del servidor haya quitado la marca de la dirección.
    const embedded = document.body.dataset.embed === "1" || window.self !== window.top;
    if (embedded) document.body.dataset.embed = "1";
    const sidebar = embedded ? null : document.querySelector(".app-sidebar");
    const header = sidebar ? sidebar.parentElement : null;
    const navBar = document.querySelector(".main-nav");
    if (navBar && navBar.parentElement && navBar.parentElement !== document.body) navBar.parentElement.classList.add("header-centered");
    if (embedded) {
        document.body.classList.add("embed-mode");
        // Oculta todo lo que precede al contenido principal (encabezado, logo, menú), sea cual sea su estructura.
        const mainContent = document.querySelector("main");
        if (mainContent) {
            [...document.body.children].forEach((element) => {
                if (element.contains(mainContent) || element.tagName === "SCRIPT") return;
                if (element.compareDocumentPosition(mainContent) & Node.DOCUMENT_POSITION_FOLLOWING) element.style.display = "none";
            });
            document.querySelectorAll("header").forEach((h) => { if (!h.contains(mainContent)) h.style.display = "none"; });
        }
        const nav = document.querySelector(".main-nav");
        let top = nav;
        while (top && top.parentElement && top.parentElement !== document.body) top = top.parentElement;
        if (top && top !== document.body) top.style.display = "none";
        document.querySelectorAll("a[href^='/']").forEach((link) => {
            const url = new URL(link.href, location.origin);
            if (!url.searchParams.has("embed")) { url.searchParams.set("embed", "1"); link.href = url.pathname + url.search + url.hash; }
        });
        document.querySelectorAll("form[action^='/'], form:not([action])").forEach((form) => {
            const action = new URL(form.getAttribute("action") || location.pathname, location.origin);
            action.searchParams.set("embed", "1");
            form.setAttribute("action", action.pathname + action.search);
        });
    }

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

/* GastroInsight AI · Secciones plegables y modo compacto de la barra lateral. */
(function () {
    "use strict";
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar || document.body.dataset.embed === "1") return;
    const KEY = "gi-side-collapsed";
    const MINI = "gi-side-mini";
    let collapsed = {};
    try { collapsed = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { collapsed = {}; }

    sidebar.querySelectorAll(".side-section").forEach((section) => {
        const title = section.querySelector(".side-title");
        if (!title) return;
        const name = title.textContent.trim();
        title.setAttribute("role", "button");
        title.setAttribute("tabindex", "0");
        title.title = "Mostrar u ocultar esta sección";
        const pref = collapsed[name];
        const hasActive = section.querySelector(".side-link.is-active");
        if (!hasActive && (pref === true || (pref === undefined && name !== "Operación"))) section.classList.add("is-collapsed");
        const toggle = () => {
            section.classList.toggle("is-collapsed");
            collapsed[name] = section.classList.contains("is-collapsed");
            try { localStorage.setItem(KEY, JSON.stringify(collapsed)); } catch (e) { /* sin almacenamiento */ }
        };
        title.addEventListener("click", toggle);
        title.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); } });
    });

    sidebar.querySelectorAll(".side-link").forEach((link) => { if (!link.title) link.title = link.textContent.trim(); });

    const mini = document.createElement("button");
    mini.type = "button";
    mini.className = "side-mini-toggle";
    mini.title = "Contraer o expandir el menú";
    mini.setAttribute("aria-label", "Contraer o expandir el menú");
    sidebar.appendChild(mini);
    const apply = (on) => { document.body.classList.toggle("sidebar-mini", on); mini.textContent = on ? "»" : "«"; };
    let saved = false;
    try { saved = localStorage.getItem(MINI) === "1"; } catch (e) { saved = false; }
    apply(saved);
    mini.addEventListener("click", () => {
        const on = !document.body.classList.contains("sidebar-mini");
        apply(on);
        try { localStorage.setItem(MINI, on ? "1" : "0"); } catch (e) { /* sin almacenamiento */ }
    });
})();

/* GastroInsight AI · Al hacer scroll, el logo se contrae en una «G» dentro de la barra lateral. */
(function () {
    "use strict";
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar || document.body.dataset.embed === "1" || sidebar.querySelector(".side-brand")) return;
    const brand = document.createElement("a");
    brand.href = "/";
    brand.className = "side-brand";
    brand.title = "GastroInsight AI · Inicio";
    brand.setAttribute("aria-label", "GastroInsight AI, ir al inicio");
    brand.innerHTML = '<span class="side-brand-g">G</span>';
    sidebar.prepend(brand);
    const headerHeight = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--app-header")) || 64;
    const update = () => document.body.classList.toggle("header-collapsed", window.scrollY > headerHeight() - 8);
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
})();

/* GastroInsight AI · Barra compacta agrupada: un ícono por sección y submenú flotante. */
(function () {
    "use strict";
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar || document.body.dataset.embed === "1" || sidebar.querySelector(".side-group-btn")) return;
    const ICONS = { "operación": "🛎️", "inteligencia": "🧠", "negocio": "📊", "gestión": "⚙️" };
    const flyout = document.createElement("div");
    flyout.className = "side-flyout";
    flyout.hidden = true;
    flyout.setAttribute("role", "menu");
    document.body.appendChild(flyout);
    let closeTimer = null;
    let openFor = null;
    const isMini = () => document.body.classList.contains("sidebar-mini");

    function close() {
        flyout.hidden = true;
        openFor = null;
        sidebar.querySelectorAll(".side-group-btn").forEach((b) => b.setAttribute("aria-expanded", "false"));
    }
    function scheduleClose() { clearTimeout(closeTimer); closeTimer = setTimeout(close, 220); }
    function open(button, section) {
        clearTimeout(closeTimer);
        const title = (section.querySelector(".side-title") || {}).textContent || "";
        flyout.innerHTML = `<p class="side-flyout-title"></p>`;
        flyout.querySelector(".side-flyout-title").textContent = title.trim();
        section.querySelectorAll(".side-link").forEach((link) => {
            const copy = link.cloneNode(true);
            copy.removeAttribute("id");
            copy.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
            copy.setAttribute("role", "menuitem");
            flyout.appendChild(copy);
        });
        flyout.hidden = false;
        const button_rect = button.getBoundingClientRect();
        const side_rect = sidebar.getBoundingClientRect();
        flyout.style.left = `${side_rect.right + 8}px`;
        let top = button_rect.top - 6;
        if (top + flyout.offsetHeight > window.innerHeight - 8) top = Math.max(8, window.innerHeight - flyout.offsetHeight - 8);
        flyout.style.top = `${top}px`;
        openFor = button;
        button.setAttribute("aria-expanded", "true");
    }

    sidebar.querySelectorAll(".side-section").forEach((section) => {
        const title = section.querySelector(".side-title");
        if (!title || !section.querySelector(".side-link")) return;
        const name = title.textContent.trim();
        const button = document.createElement("button");
        button.type = "button";
        button.className = "side-group-btn";
        button.title = name;
        button.setAttribute("aria-label", `Menú ${name}`);
        button.setAttribute("aria-haspopup", "true");
        button.setAttribute("aria-expanded", "false");
        button.innerHTML = `<span>${ICONS[name.toLowerCase()] || "•"}</span>`;
        if (section.querySelector(".side-link.is-active")) button.classList.add("is-active");
        const source = section.querySelector(".side-badge");
        if (source) {
            const badge = document.createElement("b");
            badge.className = "side-group-badge";
            button.appendChild(badge);
            const sync = () => { badge.textContent = source.textContent; badge.hidden = source.hidden || !source.textContent.trim(); };
            sync();
            new MutationObserver(sync).observe(source, { attributes: true, childList: true, characterData: true, subtree: true });
        }
        title.after(button);
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            close();
            const toggle = document.querySelector(".side-mini-toggle");
            if (isMini() && toggle) toggle.click();
            section.classList.remove("is-collapsed");
        });
        button.addEventListener("mouseenter", () => { if (isMini()) open(button, section); });
        button.addEventListener("mouseleave", scheduleClose);
    });
    flyout.addEventListener("mouseenter", () => clearTimeout(closeTimer));
    flyout.addEventListener("mouseleave", scheduleClose);
    document.addEventListener("click", (event) => { if (!flyout.hidden && !flyout.contains(event.target)) close(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
    window.addEventListener("scroll", close, { passive: true });
    window.addEventListener("resize", close);
})();

/* GastroInsight AI · Abrir y contraer la barra sin botón: espacio vacío, borde y Ctrl + B. */
(function () {
    "use strict";
    const sidebar = document.querySelector(".app-sidebar");
    const toggle = document.querySelector(".side-mini-toggle");
    if (!sidebar || !toggle || document.body.dataset.embed === "1") return;
    const edge = document.createElement("button");
    edge.type = "button";
    edge.className = "side-edge";
    sidebar.appendChild(edge);
    const sync = () => {
        const mini = document.body.classList.contains("sidebar-mini");
        edge.textContent = mini ? "›" : "‹";
        edge.title = mini ? "Abrir menú (Ctrl + B)" : "Contraer menú (Ctrl + B)";
        edge.setAttribute("aria-label", edge.title);
    };
    sync();
    new MutationObserver(sync).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    edge.addEventListener("click", (event) => { event.stopPropagation(); toggle.click(); });
    sidebar.addEventListener("click", (event) => {
        if (event.target.closest("a, button, summary, details, input, select, label, .side-title")) return;
        toggle.click();
    });
    document.addEventListener("keydown", (event) => {
        if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "b") return;
        if (event.target.closest("input, textarea, select, [contenteditable]")) return;
        event.preventDefault();
        toggle.click();
    });
})();
