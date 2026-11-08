/* GastroInsight AI · Explorador de ventas con el comportamiento de Pedidos. */
(function () {
    "use strict";
    if (location.pathname !== "/reports/explorar/" || document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const money = (text) => parseInt((text || "").replace(/[^\d]/g, ""), 10) || 0;
    const clp = (value) => "$" + value.toLocaleString("es-CL");
    const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

    // ---------- Filtros compactos ----------
    const form = [...main.querySelectorAll("form")].find((f) => f.querySelector("input[type=date]"));
    if (form) {
        const submit = () => (form.requestSubmit ? form.requestSubmit() : form.submit());
        const dates = [...form.querySelectorAll("input[type=date]")];
        form.classList.add("ex-filters");
        const wrapperOf = (field) => { let el = field; while (el.parentElement && el.parentElement !== form) el = el.parentElement; return el; };
        const advanced = [...form.querySelectorAll("select, input[type=text], input[type=search], input:not([type])")].map(wrapperOf);
        const adv = document.createElement("div");
        adv.className = "ex-adv";
        adv.hidden = true;
        [...new Set(advanced)].forEach((el) => adv.appendChild(el));
        const active = [...adv.querySelectorAll("select, input")].filter((f) => f.value && f.selectedIndex !== 0).length;
        const presets = document.createElement("div");
        presets.className = "status-chips ex-presets";
        const today = new Date();
        [["Hoy", 0], ["7 días", 6], ["30 días", 29], ["Este mes", "mes"]].forEach(([label, back]) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "status-chip";
            chip.textContent = label;
            const start = back === "mes" ? new Date(today.getFullYear(), today.getMonth(), 1) : new Date(today.getFullYear(), today.getMonth(), today.getDate() - back);
            if (dates.length >= 2 && dates[0].value === iso(start) && dates[dates.length - 1].value === iso(today)) chip.classList.add("is-active");
            chip.addEventListener("click", () => { if (dates.length >= 2) { dates[0].value = iso(start); dates[dates.length - 1].value = iso(today); submit(); } });
            presets.appendChild(chip);
        });
        const more = document.createElement("button");
        more.type = "button";
        more.className = "btn btn-small btn-secondary ex-more";
        more.innerHTML = `⚙️ Más filtros${active ? ` <b>${active}</b>` : ""}`;
        more.addEventListener("click", () => { adv.hidden = !adv.hidden; more.classList.toggle("is-open", !adv.hidden); });
        form.prepend(presets);
        if (dates.length >= 2) {
            const arrow = document.createElement("span");
            arrow.className = "ex-arrow";
            arrow.textContent = "→";
            wrapperOf(dates[dates.length - 1]).before(arrow);
        }
        [...form.querySelectorAll("a, button")].filter((el) => /limpiar/i.test(el.textContent)).forEach((el) => el.classList.add("ex-clear"));
        form.appendChild(more);
        form.appendChild(adv);
        if (active) { adv.hidden = false; more.classList.add("is-open"); }
        form.querySelectorAll("button[type=submit], input[type=submit]").forEach((b) => b.classList.add("ex-submit"));
        form.querySelectorAll("select, input[type=date]").forEach((f) => f.addEventListener("change", submit));
        form.querySelectorAll("input[type=text], input[type=search], input:not([type])").forEach((f) => f.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }));
    }

    // ---------- Cifras en una franja delgada y «CSV» en la barra ----------
    const kpis = [...main.querySelectorAll(".kpi")];
    const table = main.querySelector("table");
    const leafNumber = (box) => {
        const leaf = [...box.querySelectorAll("*")].find((el) => !el.children.length && /\d/.test(el.textContent) && el.textContent.trim().length < 20
            && !/pagado|pedido/i.test(el.textContent));
        return leaf ? leaf.textContent.trim() : "—";
    };
    const leafLabel = (box) => {
        const leaf = [...box.querySelectorAll("*")].find((el) => !el.children.length && /[a-záéíóú]{4,}/i.test(el.textContent) && !/\d/.test(el.textContent));
        return leaf ? leaf.textContent.trim().toLowerCase() : "";
    };
    if (kpis.length) {
        const ICONS = ["🧾", "💰", "🎫", "🏷️"];
        const stats = document.createElement("div");
        stats.className = "ex-stats";
        stats.innerHTML = kpis.map((kpi, i) => `<span class="ex-stat"><span>${ICONS[i] || "📊"}</span><strong>${leafNumber(kpi)}</strong><small>${leafLabel(kpi)}</small></span>`).join("");
        const grid = kpis[0].parentElement;
        grid.before(stats);
        grid.hidden = true;
    }
    const exportLink = [...main.querySelectorAll(".page-header a")].find((a) => /csv|export/i.test(a.textContent + a.href));
    if (exportLink && form) {
        exportLink.className = "btn btn-small btn-secondary ex-csv";
        exportLink.textContent = "⬇️ CSV";
        exportLink.title = "Exportar los resultados a CSV";
        form.appendChild(exportLink);
    }
    if (!table) return;

    // ---------- Tabla: estados, buscador, grupos por día y filas que abren el pedido ----------
    const headers = [...table.querySelectorAll("thead th")].map((th) => norm(th.textContent.trim()));
    const col = (name) => headers.findIndex((h) => h.includes(name));
    const rows = [...table.querySelectorAll("tbody tr")].filter((tr) => tr.children.length > 1);
    const cell = (tr, i) => (i >= 0 && tr.children[i] ? tr.children[i].textContent.trim() : "");
    const stateI = col("estado"), dateI = col("fecha"), totalI = col("total"), dishI = col("plato");
    const stateOf = (tr) => cell(tr, stateI);
    rows.forEach((tr) => {
        const td = tr.children[stateI];
        if (td && !td.querySelector(".ex-badge")) td.innerHTML = `<span class="ex-badge state-${norm(td.textContent.trim()).slice(0, 5)}">${td.textContent.trim()}</span>`;
        const dish = tr.children[dishI];
        if (dish) { dish.classList.add("ex-dishes"); dish.title = dish.textContent.trim(); }
    });
    const states = [...new Set(rows.map(stateOf).filter(Boolean))];
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
        chip.addEventListener("click", () => { active = value; chips.querySelectorAll(".status-chip").forEach((c) => c.classList.toggle("is-active", c === chip)); paint(); });
        chips.appendChild(chip);
    });
    const search = document.createElement("input");
    search.type = "search";
    search.className = "orders-search";
    search.placeholder = "🔎 Buscar por mesa, número, plato o quién registró…";
    search.setAttribute("aria-label", "Buscar en los resultados");
    toolbar.append(chips, search);
    (table.closest(".table-responsive") || table).before(toolbar);

    const WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const year = new Date().getFullYear();
    const keyOf = (tr) => { const m = cell(tr, dateI).match(/(\d{2})[-/](\d{2})(?:[-/](\d{4}))?/); return m ? `${m[3] || year}-${m[2]}-${m[1]}` : "sin-fecha"; };
    const todayKey = iso(new Date());
    const yesterdayKey = iso(new Date(Date.now() - 86400000));
    const labelOf = (key) => {
        if (key === "sin-fecha") return "Sin fecha";
        const [y, m, d] = key.split("-").map(Number);
        const base = `${WEEKDAYS[new Date(y, m - 1, d).getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
        return key === todayKey ? `Hoy · ${base}` : key === yesterdayKey ? `Ayer · ${base}` : base;
    };
    const groups = new Map();
    rows.forEach((tr) => { const k = keyOf(tr); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(tr); });
    const open = new Set([...groups.keys()].slice(0, 1));
    const heads = new Map();
    groups.forEach((list, key) => {
        const head = document.createElement("tr");
        head.className = "day-row";
        head.innerHTML = `<td colspan="${headers.length}"><span class="day-chevron">▸</span><strong></strong><span class="day-meta"></span></td>`;
        head.querySelector("strong").textContent = labelOf(key);
        list[0].before(head);
        head.addEventListener("click", () => { if (open.has(key)) open.delete(key); else open.add(key); paint(); });
        heads.set(key, head);
    });
    const empty = document.createElement("tr");
    empty.className = "empty-row";
    empty.innerHTML = `<td colspan="${headers.length}"></td>`;
    (table.querySelector("tbody") || table).appendChild(empty);
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
            const paid = matches.filter((tr) => /pagad/i.test(stateOf(tr))).reduce((s, tr) => s + money(cell(tr, totalI)), 0);
            head.querySelector(".day-meta").textContent = `${matches.length} pedido${matches.length === 1 ? "" : "s"} · ${clp(paid)} pagados`;
            visible += matches.length;
        });
        empty.hidden = visible > 0;
        empty.querySelector("td").textContent = "No hay pedidos que coincidan con la búsqueda.";
    }
    search.addEventListener("input", paint);
    paint();
    rows.forEach((tr) => {
        const link = tr.querySelector("a[href]");
        if (!link) return;
        tr.classList.add("row-link");
        tr.addEventListener("click", (event) => { if (!event.target.closest("a, button, form, input, select")) location.href = link.href; });
    });
})();
