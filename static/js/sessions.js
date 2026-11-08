/* GastroInsight AI · Sesiones de análisis con el mismo comportamiento que Pedidos. */
(function () {
    "use strict";
    if (location.pathname !== "/ai/sessions/") return;
    const main = document.querySelector("main");
    if (!main) return;
    const cards = [...main.querySelectorAll(".card")];
    const historyCard = cards.find((c) => /historial/i.test((c.querySelector("h2, h3") || {}).textContent || ""));
    const camerasCard = cards.find((c) => /c[aá]maras registradas/i.test((c.querySelector("h2, h3") || {}).textContent || ""));
    const table = historyCard && historyCard.querySelector("table");
    const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

    // Cámaras registradas plegadas (abiertas si aún no hay sesiones)
    if (camerasCard) {
        const title = camerasCard.querySelector("h2, h3");
        const count = camerasCard.querySelectorAll("tbody tr").length;
        const details = document.createElement("details");
        details.className = "cams-fold";
        details.innerHTML = `<summary>📷 <strong>Cámaras registradas · ${count}</strong><span>toca para crear una sesión nueva</span></summary>`;
        [...camerasCard.childNodes].forEach((node) => { if (node !== title) details.appendChild(node); });
        if (title) title.remove();
        camerasCard.appendChild(details);
        if (!table || !table.querySelectorAll("tbody tr").length) details.open = true;
    }
    if (!table) return;

    const headers = [...table.querySelectorAll("thead th")].map((th) => norm(th.textContent.trim()));
    const col = (name) => headers.findIndex((h) => h.includes(name));
    const rows = [...table.querySelectorAll("tbody tr")].filter((tr) => tr.children.length > 1);
    const cell = (tr, index) => (index >= 0 && tr.children[index] ? tr.children[index].textContent.trim() : "");
    const stateIndex = col("estado");
    const startIndex = col("inicio");
    const eventsIndex = col("evento");
    const stateOf = (tr) => cell(tr, stateIndex);
    const events = (tr) => parseInt(cell(tr, eventsIndex), 10) || 0;

    // Título centrado
    const title = historyCard.querySelector("h2, h3");
    if (title) title.style.cssText += ";display:block;width:100%;text-align:center;";

    // Indicadores + mosaico «Correlación»
    const states = [...new Set(rows.map(stateOf).filter(Boolean))];
    const done = rows.filter((tr) => /complet/i.test(norm(stateOf(tr)))).length;
    const pending = rows.filter((tr) => /pendien|curso|ejecut|running/i.test(norm(stateOf(tr)))).length;
    const summary = document.createElement("div");
    summary.className = "orders-summary";
    const tile = (icon, value, label) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span></div>`;
    summary.innerHTML = tile("🎥", rows.length, "Sesiones") + tile("✅", done, "Completadas") + tile("⏳", pending, "Pendientes o en curso")
        + tile("📊", rows.reduce((sum, tr) => sum + events(tr), 0).toLocaleString("es-CL"), "Eventos registrados");
    const correlation = [...main.querySelectorAll(".page-header a, .page-header .btn")].find((a) => /correlaci/i.test(a.textContent));
    if (correlation) {
        const action = document.createElement("a");
        action.href = correlation.getAttribute("href");
        action.className = "mini-kpi mini-kpi-action";
        action.innerHTML = '<span class="mini-kpi-icon">📈</span><strong>Ver</strong><span>Correlación</span>';
        summary.appendChild(action);
        correlation.remove();
    }

    // Píldoras de estado con contador y buscador
    let active = "";
    const toolbar = document.createElement("div");
    toolbar.className = "orders-toolbar";
    const chips = document.createElement("div");
    chips.className = "status-chips";
    [["", "Todos", rows.length], ...states.map((s) => [s, s, rows.filter((tr) => stateOf(tr) === s).length])].forEach(([value, label, count], i) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "status-chip" + (i === 0 ? " is-active" : "");
        chip.innerHTML = `${label} <b>${count}</b>`;
        chip.addEventListener("click", () => {
            active = value;
            chips.querySelectorAll(".status-chip").forEach((c) => c.classList.toggle("is-active", c === chip));
            paint();
        });
        chips.appendChild(chip);
    });
    const search = document.createElement("input");
    search.type = "search";
    search.className = "orders-search";
    search.placeholder = "🔎 Buscar por cámara, mesa o número de sesión…";
    search.setAttribute("aria-label", "Buscar sesión");
    toolbar.append(chips, search);
    const wrapper = table.closest(".table-responsive") || table;
    wrapper.before(summary);
    summary.after(toolbar);

    // Grupos por día («Pendientes de iniciar» primero)
    const WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    const today = new Date();
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    const dayOf = (tr) => { const m = cell(tr, startIndex).match(/(\d{2})\/(\d{2})\/(\d{4})/); return m ? `${m[3]}-${m[2]}-${m[1]}` : "pendiente"; };
    const labelOf = (key) => {
        if (key === "pendiente") return "⏳ Pendientes de iniciar";
        const [y, m, d] = key.split("-").map(Number);
        const base = `${WEEKDAYS[new Date(y, m - 1, d).getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
        return key === iso(today) ? `Hoy · ${base}` : key === iso(yesterday) ? `Ayer · ${base}` : base;
    };
    const groups = new Map();
    rows.filter((tr) => dayOf(tr) === "pendiente").concat(rows.filter((tr) => dayOf(tr) !== "pendiente")).forEach((tr) => {
        const key = dayOf(tr);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(tr);
    });
    const tbody = table.querySelector("tbody");
    const open = new Set([...groups.keys()].slice(0, groups.has("pendiente") ? 2 : 1));
    const heads = new Map();
    groups.forEach((list, key) => {
        const head = document.createElement("tr");
        head.className = "day-row";
        head.innerHTML = `<td colspan="${headers.length}"><span class="day-chevron">▸</span><strong></strong><span class="day-meta"></span></td>`;
        head.querySelector("strong").textContent = labelOf(key);
        tbody.appendChild(head);
        list.forEach((tr) => tbody.appendChild(tr));
        head.addEventListener("click", () => { if (open.has(key)) open.delete(key); else open.add(key); paint(); });
        heads.set(key, head);
    });
    const empty = document.createElement("tr");
    empty.className = "empty-row";
    empty.innerHTML = `<td colspan="${headers.length}"></td>`;
    tbody.appendChild(empty);

    function paint() {
        const query = norm(search.value.trim());
        const filtering = Boolean(query || active);
        let visible = 0;
        groups.forEach((list, key) => {
            const matches = list.filter((tr) => (!active || stateOf(tr) === active) && (!query || norm(tr.textContent).includes(query)));
            const expanded = matches.length > 0 && (filtering || open.has(key));
            list.forEach((tr) => { tr.hidden = !expanded || !matches.includes(tr); });
            const head = heads.get(key);
            head.hidden = !matches.length;
            head.querySelector(".day-chevron").textContent = expanded ? "▾" : "▸";
            const total = matches.reduce((sum, tr) => sum + events(tr), 0);
            head.querySelector(".day-meta").textContent = `${matches.length} sesi${matches.length === 1 ? "ón" : "ones"} · ${total.toLocaleString("es-CL")} eventos`;
            visible += matches.length;
        });
        empty.hidden = visible > 0;
        empty.querySelector("td").textContent = active ? `No hay sesiones «${active}».` : "No hay sesiones que coincidan con la búsqueda.";
    }
    search.addEventListener("input", paint);
    paint();

    // Toda la fila abre «Ver resultado»
    rows.forEach((tr) => {
        const link = [...tr.querySelectorAll("a[href]")].find((a) => /resultado/i.test(a.textContent)) || tr.querySelector("a[href]");
        if (!link) return;
        tr.classList.add("row-link");
        tr.addEventListener("click", (event) => { if (!event.target.closest("a, button, form, input, select, label")) location.href = link.href; });
    });
})();
