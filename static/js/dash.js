/* GastroInsight AI · Dashboard en pestañas y botones rápidos de fecha. */
(function () {
    "use strict";
    if (!/^\/analytics\/(dashboard\/)?$/.test(location.pathname) || document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;

    // Botones rápidos de fecha junto al filtro
    const filter = main.querySelector("form[method=get], form:not([method])");
    const dates = filter ? [...filter.querySelectorAll("input[type=date]")] : [];
    if (dates.length) {
        const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
        const today = new Date();
        const daysAgo = (n) => { const d = new Date(today); d.setDate(d.getDate() - n); return iso(d); };
        const presets = dates.length >= 2
            ? [["Hoy", 0, 0], ["7 días", 6, 0], ["30 días", 29, 0]]
            : [["Hoy", 0], ["Ayer", 1]];
        const bar = document.createElement("div");
        bar.className = "date-presets";
        presets.forEach(([label, start, end]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-small btn-secondary";
            button.textContent = label;
            button.addEventListener("click", () => {
                if (dates.length >= 2) { dates[0].value = daysAgo(start); dates[dates.length - 1].value = daysAgo(end); }
                else dates[0].value = daysAgo(start);
                if (filter.requestSubmit) filter.requestSubmit(); else filter.submit();
            });
            bar.appendChild(button);
        });
        filter.appendChild(bar);
    }

    // Pestañas: cada bloque va a la pestaña que corresponde a su título
    const RULES = [
        ["💰 Ventas", /venta|plato|ticket|ingreso|hora/i],
        ["👁️ Visión IA", /visual|c[aá]mara|detecci|expresi|emoci|tendencia|ieo|an[aá]lisis/i],
        ["🧾 Operación", /operaci|mesa|evaluaci|servicio|pedido|atenci/i],
        ["📋 Detalle", /sesi[oó]n|[uú]ltim|historial|detalle|resumen/i],
    ];
    const blocks = [...main.children].filter((el) => !el.matches("script, .page-header, .messages, .alert, form") && !(el.querySelector("form") && !el.querySelector("h2")));
    const groups = new Map();
    let current = null;
    blocks.forEach((el) => {
        const heading = el.matches("h2") ? el : el.querySelector("h2");
        const rule = heading ? RULES.find(([, pattern]) => pattern.test(heading.textContent)) : null;
        const tab = rule ? rule[0] : current;
        if (!tab) return;
        current = tab;
        if (!groups.has(tab)) groups.set(tab, []);
        groups.get(tab).push(el);
    });
    if (groups.size < 2) return;

    const container = document.createElement("div");
    container.className = "dash-tabs";
    const bar = document.createElement("div");
    bar.className = "tab-bar";
    container.appendChild(bar);
    blocks.find((el) => [...groups.values()].flat().includes(el)).before(container);
    const order = RULES.map(([name]) => name).filter((name) => groups.has(name));
    const panels = order.map((name) => {
        const panel = document.createElement("div");
        panel.className = "dash-panel";
        groups.get(name).forEach((el) => panel.appendChild(el));
        container.appendChild(panel);
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = name;
        bar.appendChild(button);
        return { button, panel };
    });
    const KEY = "gi-dash-tab";
    function activate(index) {
        panels.forEach((p, i) => { p.panel.hidden = i !== index; p.button.classList.toggle("is-active", i === index); });
        try { sessionStorage.setItem(KEY, String(index)); } catch (e) { /* sin almacenamiento */ }
        window.dispatchEvent(new Event("resize"));
    }
    panels.forEach((p, i) => p.button.addEventListener("click", () => activate(i)));
    let saved = 0;
    try { saved = parseInt(sessionStorage.getItem(KEY) || "0", 10); } catch (e) { saved = 0; }
    activate(saved < panels.length ? saved : 0);
})();
