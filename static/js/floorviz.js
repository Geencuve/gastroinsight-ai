/* GastroInsight AI · Salón visual: mesas dibujadas, selector de comensales y zonas en pestañas horizontales. */
(function () {
    "use strict";
    const board = document.getElementById("floor-board");
    if (!board || document.body.dataset.embed === "1") return;
    const SVG = "http://www.w3.org/2000/svg";
    const ZONE_KEY = "gi-floor-zone";

    function drawTable(capacity, guests) {
        const seats = Math.max(1, Math.min(capacity || 2, 10));
        const round = seats <= 4;
        const svg = document.createElementNS(SVG, "svg");
        svg.setAttribute("viewBox", "0 0 140 90");
        svg.setAttribute("class", "table-visual");
        svg.setAttribute("aria-hidden", "true");
        const table = document.createElementNS(SVG, round ? "circle" : "rect");
        if (round) { table.setAttribute("cx", 70); table.setAttribute("cy", 45); table.setAttribute("r", 22); }
        else { table.setAttribute("x", 30); table.setAttribute("y", 28); table.setAttribute("width", 80); table.setAttribute("height", 34); table.setAttribute("rx", 9); }
        table.setAttribute("class", "tv-table");
        svg.appendChild(table);
        for (let i = 0; i < seats; i += 1) {
            const angle = (2 * Math.PI * i) / seats - Math.PI / 2;
            const chair = document.createElementNS(SVG, "circle");
            chair.setAttribute("cx", (70 + (round ? 36 : 55) * Math.cos(angle)).toFixed(1));
            chair.setAttribute("cy", (45 + (round ? 36 : 33) * Math.sin(angle)).toFixed(1));
            chair.setAttribute("r", 7);
            chair.setAttribute("class", "tv-chair" + (i < guests ? " is-taken" : ""));
            svg.appendChild(chair);
        }
        return svg;
    }

    function enhanceTables() {
        board.querySelectorAll(".table-card:not([data-visual])").forEach((card) => {
            card.dataset.visual = "1";
            const text = card.textContent;
            const capacity = parseInt((text.match(/Capacidad\s+(\d+)/i) || [])[1], 10) || 4;
            const guests = parseInt((text.match(/👥\s*(\d+)/) || [])[1], 10) || 0;
            const header = card.querySelector("header");
            const name = header && header.querySelector("strong");
            if (name && /^Mesa\s+/i.test(name.textContent)) name.innerHTML = `<small>Mesa</small>${name.textContent.replace(/^Mesa\s+/i, "")}`;
            if (header) header.before(drawTable(capacity, guests));
            card.querySelectorAll(".table-meta").forEach((meta) => { if (/Capacidad/i.test(meta.textContent)) meta.textContent = `👥 Hasta ${capacity} personas`; });
            const input = card.querySelector(".quick-open input[type=number]");
            if (input && !input.closest(".qo-stepper")) {
                const stepper = document.createElement("div");
                stepper.className = "qo-stepper";
                input.before(stepper);
                const minus = document.createElement("button");
                minus.type = "button"; minus.textContent = "−"; minus.setAttribute("aria-label", "Menos comensales");
                const plus = document.createElement("button");
                plus.type = "button"; plus.textContent = "+"; plus.setAttribute("aria-label", "Más comensales");
                stepper.append(minus, input, plus);
                const step = (delta) => { input.value = Math.max(1, Math.min(30, (parseInt(input.value, 10) || 2) + delta)); };
                minus.addEventListener("click", () => step(-1));
                plus.addEventListener("click", () => step(1));
            }
        });
    }

    // Zonas en pestañas horizontales: «Todas» o una zona a la vez
    function selectZone(zones, bar, name) {
        zones.forEach((z) => {
            const show = name === "__todas__" || z.name === name;
            z.grid.hidden = !show;
            z.header.hidden = name !== "__todas__";
        });
        bar.querySelectorAll(".zone-tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.zone === name));
    }

    function enhanceZones() {
        const column = board.querySelector(".floor-layout > div") || board;
        const zones = [...column.querySelectorAll(".floor-zone")].map((header) => ({ header, grid: header.nextElementSibling, name: header.textContent.trim() }))
            .filter((z) => z.grid && z.grid.classList.contains("floor-grid"));
        if (!zones.length || column.querySelector(".zone-bar")) return;
        const bar = document.createElement("div");
        bar.className = "zone-bar";
        bar.setAttribute("role", "tablist");
        const all = document.createElement("button");
        all.type = "button";
        all.className = "zone-tab";
        all.dataset.zone = "__todas__";
        all.innerHTML = '<span class="zone-name">Todas</span>';
        bar.appendChild(all);
        let busiest = null;
        zones.forEach((z) => {
            const cards = [...z.grid.querySelectorAll(".table-card")];
            const free = cards.filter((c) => /libre/i.test((c.querySelector(".state-pill") || {}).textContent || "")).length;
            const busy = cards.length - free;
            if (busy && !busiest) busiest = z.name;
            const tab = document.createElement("button");
            tab.type = "button";
            tab.className = "zone-tab";
            tab.dataset.zone = z.name;
            tab.setAttribute("role", "tab");
            tab.innerHTML = `<span class="zone-name"></span><span class="zone-meta">${cards.length} · ${free} libre${free === 1 ? "" : "s"}${busy ? ` · ${busy} ocup.` : ""}</span>`;
            tab.querySelector(".zone-name").textContent = z.name;
            bar.appendChild(tab);
        });
        bar.addEventListener("click", (event) => {
            const tab = event.target.closest(".zone-tab");
            if (!tab) return;
            try { localStorage.setItem(ZONE_KEY, tab.dataset.zone); } catch (e) { /* sin almacenamiento */ }
            selectZone(zones, bar, tab.dataset.zone);
        });
        column.prepend(bar);
        let saved = "";
        try { saved = localStorage.getItem(ZONE_KEY) || ""; } catch (e) { saved = ""; }
        const valid = saved === "__todas__" || zones.some((z) => z.name === saved);
        selectZone(zones, bar, valid ? saved : (busiest || "__todas__"));
    }

    // Solo reacciona cuando el tablero completo se reemplaza (actualización cada 10 s) y nunca se llama a sí mismo
    let running = false;
    function run() {
        if (running) return;
        running = true;
        try { enhanceTables(); enhanceZones(); } finally { running = false; }
    }
    run();
    new MutationObserver(run).observe(board, { childList: true });
})();
