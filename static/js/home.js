/* GastroInsight AI · Inicio centrado: indicadores con ícono, sugerencias en tarjetas que se voltean y accesos rápidos. */
(function () {
    "use strict";
    if (location.pathname !== "/" || document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    document.body.classList.add("page-home");
    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    // Saludo centrado
    const greeting = main.querySelector("h1");
    if (greeting && greeting.parentElement) greeting.parentElement.classList.add("home-hero");

    // 1. Cuatro indicadores con ícono (el ticket promedio pasa a nota de las ventas)
    const kpis = [...main.querySelectorAll(".kpi")];
    const label = (kpi) => (kpi.querySelector(".kpi-label") || kpi).textContent.toLowerCase();
    const ticket = kpis.find((k) => label(k).includes("ticket"));
    const sales = kpis.find((k) => label(k).includes("vendido"));
    if (ticket && sales) {
        const value = (ticket.querySelector(".kpi-value") || {}).textContent;
        const note = sales.querySelector(".kpi-note");
        if (value && note) note.textContent = `Ticket promedio ${value.trim()}`;
        ticket.hidden = true;
    }
    [["vendido", "💰"], ["mesas", "🪑"], ["cobrar", "🧾"], ["satisf", "😊"]].forEach(([word, emoji]) => {
        const kpi = kpis.find((k) => label(k).includes(word));
        if (kpi && !kpi.querySelector(".kpi-icon")) {
            const icon = document.createElement("span");
            icon.className = "kpi-icon";
            icon.textContent = emoji;
            kpi.prepend(icon);
        }
    });

    // 2. Sugerencias en tarjetas que se voltean
    const sections = [...main.querySelectorAll(".idea-section")];
    const ideas = [];
    sections.forEach((section) => {
        const heading = section.querySelector("h2");
        const text = heading ? heading.textContent.toLowerCase() : "";
        const category = text.includes("venta") ? "Venta" : text.includes("marketing") ? "Marketing" : "Experiencia";
        section.querySelectorAll(".idea").forEach((idea) => ideas.push({ idea, category }));
    });
    if (ideas.length) {
        const box = document.createElement("section");
        box.className = "card home-tips";
        box.innerHTML = `<header class="tips-head"><h2>💡 Sugerencias para hoy</h2>
            <small>Toca una tarjeta para ver qué hacer. Basadas en reglas y estadística de tus datos, no en predicciones.</small></header>
            <div class="flip-grid"></div>`;
        const grid = box.querySelector(".flip-grid");
        ideas.forEach(({ idea, category }, index) => {
            const title = ((idea.querySelector("h3") || {}).textContent || "").trim();
            const impact = ((idea.querySelector(".idea-impact") || {}).textContent || "").trim();
            const emoji = ((idea.querySelector(".idea-icon") || {}).textContent || "💡").trim();
            const card = document.createElement("article");
            card.className = `flip-card tip-${category.toLowerCase()}`;
            card.tabIndex = 0;
            card.setAttribute("role", "button");
            card.setAttribute("aria-pressed", "false");
            card.setAttribute("aria-label", `${category}: ${title}. Toca para ver qué hacer.`);
            card.innerHTML = `<div class="flip-inner">
                <div class="flip-face flip-front"><span class="flip-emoji" aria-hidden="true">${esc(emoji)}</span><span class="tip-tag">${esc(category)}</span><h3 class="tip-title">${esc(title)}</h3>
                    ${impact ? `<p class="tip-impact">${esc(impact)}</p>` : ""}<span class="flip-hint">↻ Toca para ver qué hacer</span></div>
                <div class="flip-face flip-back"><span class="tip-tag">Qué hacer</span><div class="flip-content"></div><span class="flip-hint">↻ Volver</span></div>
            </div>`;
            const content = card.querySelector(".flip-content");
            ["idea-action", "idea-why"].forEach((cls) => { const el = idea.querySelector(`.${cls}`); if (el) content.appendChild(el); });
            const method = idea.querySelector(".idea-method");
            if (method) content.appendChild(method);
            const link = [...idea.querySelectorAll("a[href]")].pop();
            if (link) { link.classList.add("tip-link"); content.appendChild(link); }
            const flip = () => {
                const flipped = card.classList.toggle("is-flipped");
                card.setAttribute("aria-pressed", String(flipped));
            };
            card.addEventListener("click", (event) => { if (!event.target.closest("a, summary, details, button")) flip(); });
            card.addEventListener("keydown", (event) => {
                if ((event.key === "Enter" || event.key === " ") && event.target === card) { event.preventDefault(); flip(); }
            });
            if (index >= 8) card.hidden = true;
            grid.appendChild(card);
        });
        if (ideas.length > 8) {
            const more = document.createElement("button");
            more.type = "button";
            more.className = "btn btn-secondary tips-more";
            more.textContent = `Ver todas (${ideas.length})`;
            more.addEventListener("click", () => { grid.querySelectorAll(".flip-card").forEach((c) => { c.hidden = false; }); more.remove(); });
            box.appendChild(more);
        }
        const anchor = main.querySelector('[data-tabs="ideas"]') || sections[0];
        anchor.before(box);
        sections.forEach((s) => s.remove());
        const tabs = main.querySelector('[data-tabs="ideas"]');
        if (tabs) tabs.remove();
    }

    // 3. Accesos rápidos con ícono
    const ICONS = [[/abrir mesa|atenci/i, "🪑"], [/pedido/i, "🧾"], [/evaluaci/i, "⭐"], [/an[aá]lisis|visi/i, "👁️"],
                   [/dashboard/i, "📊"], [/correlaci/i, "📈"], [/reporte/i, "📄"], [/carta|men[uú]/i, "🍽️"]];
    main.querySelectorAll(".quick-actions a, .quick-actions .btn").forEach((tile) => {
        if (tile.querySelector(".qa-icon")) return;
        const match = ICONS.find(([pattern]) => pattern.test(tile.textContent));
        const icon = document.createElement("span");
        icon.className = "qa-icon";
        icon.textContent = match ? match[1] : "➜";
        tile.prepend(icon);
    });

    [...main.querySelectorAll("p")].filter((p) => /sugerencias se generan/i.test(p.textContent)).forEach((p) => { p.hidden = true; });
})();
