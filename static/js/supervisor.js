/* GastroInsight AI · Panel del supervisor: resumen del journey y de la correlación en la misma página. */
(function () {
    "use strict";
    if (location.pathname !== "/supervisor/" || document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    const links = [...main.querySelectorAll(".page-header a[href]")];
    const journey = links.find((a) => /journey/i.test(a.getAttribute("href")));
    const correlation = links.find((a) => /correlation|correlaci/i.test(a.getAttribute("href") + a.textContent));
    if (!journey && !correlation) return;
    const journeyHref = journey ? journey.getAttribute("href") : "/supervisor/journey/";
    const correlationHref = correlation ? correlation.getAttribute("href") : "/analytics/correlation/";
    [journey, correlation].forEach((a) => { if (a) a.remove(); });
    main.querySelectorAll(".page-header .page-actions").forEach((row) => { if (!row.children.length) row.remove(); });

    const section = document.createElement("section");
    section.className = "card sup-summary";
    section.innerHTML = `<h2>Recorrido y calidad del servicio</h2>
        <div class="sup-grid">
            <article class="sup-card"><header><span>🛤️</span><h3>Journey del cliente</h3></header>
                <div class="sup-body" data-kind="journey"><p class="muted">Cargando…</p></div>
                <a class="btn btn-secondary" href="${journeyHref}">Ver journey completo →</a></article>
            <article class="sup-card"><header><span>📈</span><h3>Panel de correlación</h3></header>
                <div class="sup-body" data-kind="correlation"><p class="muted">Cargando…</p></div>
                <a class="btn btn-secondary" href="${correlationHref}">Ver correlación completa →</a></article>
        </div>`;
    const tabs = main.querySelector("[data-tabs]");
    if (tabs) tabs.after(section); else main.appendChild(section);

    const parse = async (url) => {
        const response = await fetch(url, { credentials: "same-origin" });
        if (!response.ok) throw new Error(String(response.status));
        return new DOMParser().parseFromString(await response.text(), "text/html");
    };
    const tile = (icon, value, label) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span></div>`;

    parse(journeyHref).then((doc) => {
        const body = section.querySelector('[data-kind="journey"]');
        const summary = doc.querySelector(".journey-summary");
        const pain = doc.querySelector(".journey-pain");
        if (!summary) { body.innerHTML = '<p class="muted">Aún no hay atenciones con análisis visual en este período.</p>'; return; }
        body.innerHTML = summary.outerHTML;
        if (pain) {
            const action = pain.querySelector("p");
            if (action) body.insertAdjacentHTML("beforeend", `<p class="sup-action">💡 ${action.textContent.trim()}</p>`);
        }
    }).catch(() => { section.querySelector('[data-kind="journey"]').innerHTML = '<p class="muted">No se pudo cargar el resumen.</p>'; });

    parse(correlationHref).then((doc) => {
        const body = section.querySelector('[data-kind="correlation"]');
        const kpis = [...doc.querySelectorAll("main .kpi")].slice(0, 4);
        const icons = ["📊", "⭐", "⏱️", "🔗"];
        if (kpis.length) {
            body.innerHTML = `<div class="orders-summary">${kpis.map((kpi, i) => tile(icons[i],
                ((kpi.querySelector(".kpi-value") || {}).textContent || "—").trim(),
                ((kpi.querySelector(".kpi-label") || {}).textContent || "").trim())).join("")}</div>`;
        } else {
            const text = [...doc.querySelectorAll("main p")].map((p) => p.textContent.trim()).find((t) => /correlaci|relaci/i.test(t));
            body.innerHTML = `<p>${text || "Cruza el IEO con las evaluaciones de los clientes y los tiempos de servicio."}</p>`;
        }
    }).catch(() => { section.querySelector('[data-kind="correlation"]').innerHTML = '<p class="muted">No se pudo cargar el resumen.</p>'; });
})();
