/* GastroInsight AI · Pedidos: indicadores con «Crear pedido», filtro por estado instantáneo, buscador y grupos por día. */
(function () {
    "use strict";
    if (location.pathname !== "/sales/" || document.body.dataset.embed === "1") return;
    const KEY = "gi-orders-status";
    const params = new URLSearchParams(location.search);
    if (params.get("status")) {
        try { sessionStorage.setItem(KEY, params.get("status")); } catch (e) { /* sin almacenamiento */ }
        location.replace("/sales/");
        return;
    }
    const main = document.querySelector("main");
    const table = main && main.querySelector("table");
    if (!table) return;
    const tableCard = table.closest(".card") || table.parentElement;
    const headers = [...table.querySelectorAll("thead th")].map((th) => th.textContent.trim().toLowerCase());
    const col = (name) => headers.findIndex((h) => h.includes(name));
    const rows = [...table.querySelectorAll("tbody tr")].filter((tr) => tr.children.length > 1);
    const cell = (tr, index) => (index >= 0 && tr.children[index] ? tr.children[index].textContent.trim() : "");
    const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const money = (text) => parseInt((text || "").replace(/[^\d]/g, ""), 10) || 0;
    const clp = (value) => "$" + value.toLocaleString("es-CL");
    const stateIndex = col("estado");
    const totalIndex = col("total");
    const dateIndex = col("cread");
    const stateOf = (tr) => norm(cell(tr, stateIndex));
    const isPaid = (tr) => stateOf(tr).includes("pagad");
    const sameState = (tr, label) => !label || stateOf(tr).slice(0, 5) === norm(label).slice(0, 5);

    // Título centrado (directamente sobre el elemento) y sin la frase de los últimos 100
    const title = tableCard.querySelector("h2, h3");
    if (title) {
        title.classList.add("card-title-center");
        title.style.cssText += ";display:block;width:100%;text-align:center;align-self:stretch;";
        if (title.parentElement !== tableCard) {
            title.parentElement.classList.add("card-head-center");
            title.parentElement.style.cssText += ";display:block;width:100%;text-align:center;";
        }
    }
    tableCard.querySelectorAll("p").forEach((p) => { if (/se muestran/i.test(p.textContent)) p.hidden = true; });

    // Columna «Local» oculta si todos los pedidos son del mismo local
    const localIndex = col("local");
    if (localIndex >= 0 && rows.length && new Set(rows.map((tr) => cell(tr, localIndex))).size === 1) {
        table.querySelectorAll("tr").forEach((tr) => { if (tr.children[localIndex]) tr.children[localIndex].hidden = true; });
    }

    // Indicadores + mosaico «Crear pedido»
    const paid = rows.filter(isPaid);
    const summary = document.createElement("div");
    summary.className = "orders-summary";
    summary.innerHTML = [
        ["🧾", "Pedidos listados", rows.length, ""],
        ["✅", "Pagados", paid.length, clp(paid.reduce((sum, tr) => sum + money(cell(tr, totalIndex)), 0))],
        ["⏳", "En curso", rows.filter((tr) => /abiert|confirm/.test(stateOf(tr))).length, ""],
        ["✖️", "Anulados", rows.filter((tr) => /anulad|cancel/.test(stateOf(tr))).length, ""],
    ].map(([icon, label, value, note]) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span>${note ? `<small>${note}</small>` : ""}</div>`).join("");
    const create = [...main.querySelectorAll(".page-header a, .page-header .btn")].find((a) => /crear pedido/i.test(a.textContent));
    if (create) {
        const tile = document.createElement("a");
        tile.href = create.getAttribute("href");
        tile.className = "mini-kpi mini-kpi-action";
        tile.innerHTML = '<span class="mini-kpi-icon">＋</span><strong>Crear</strong><span>Nuevo pedido</span>';
        summary.appendChild(tile);
        create.remove();
    }

    // Filtro por estado instantáneo (sin recargar) y buscador
    const filterCard = [...main.querySelectorAll(".card")].find((card) => card !== tableCard && card.querySelector("form select"));
    const select = filterCard ? filterCard.querySelector("select") : null;
    if (filterCard) filterCard.hidden = true;
    let activeLabel = "";
    const toolbar = document.createElement("div");
    toolbar.className = "orders-toolbar";
    const chips = document.createElement("div");
    chips.className = "status-chips";
    const options = select ? [...select.options] : [{ value: "", textContent: "Todos" }];
    let remembered = "";
    try { remembered = sessionStorage.getItem(KEY) || ""; sessionStorage.removeItem(KEY); } catch (e) { remembered = ""; }
    options.forEach((option) => {
        const label = option.value ? option.textContent.trim() : "";
        const count = label ? rows.filter((tr) => sameState(tr, label)).length : rows.length;
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = `status-chip state-${(option.value || "todos").toLowerCase()}`;
        chip.innerHTML = `${label || "Todos"} <b>${count}</b>`;
        chip.addEventListener("click", () => {
            activeLabel = label;
            chips.querySelectorAll(".status-chip").forEach((c) => c.classList.toggle("is-active", c === chip));
            paint();
        });
        if ((remembered && option.value === remembered) || (!remembered && !option.value)) {
            chip.classList.add("is-active");
            activeLabel = label;
        }
        chips.appendChild(chip);
    });
    toolbar.appendChild(chips);
    const search = document.createElement("input");
    search.type = "search";
    search.className = "orders-search";
    search.placeholder = "🔎 Buscar por mesa o número de pedido…";
    search.setAttribute("aria-label", "Buscar pedido");
    toolbar.appendChild(search);
    const wrapper = table.closest(".table-responsive") || table;
    wrapper.before(summary);
    summary.after(toolbar);

    // Grupos por día: solo el más reciente queda abierto
    const WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const dayOf = (tr) => { const m = cell(tr, dateIndex).match(/(\d{2})\/(\d{2})\/(\d{4})/); return m ? `${m[3]}-${m[2]}-${m[1]}` : "sin-fecha"; };
    const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    const today = new Date();
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    const labelOf = (key) => {
        if (key === "sin-fecha") return "Sin fecha";
        const [y, m, d] = key.split("-").map(Number);
        const base = `${WEEKDAYS[new Date(y, m - 1, d).getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
        return key === iso(today) ? `Hoy · ${base}` : key === iso(yesterday) ? `Ayer · ${base}` : base;
    };
    const groups = new Map();
    rows.forEach((tr) => { const key = dayOf(tr); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(tr); });
    const open = new Set([...groups.keys()].slice(0, 1));
    const dayRows = new Map();
    const span = headers.length;
    groups.forEach((list, key) => {
        const header = document.createElement("tr");
        header.className = "day-row";
        header.innerHTML = `<td colspan="${span}"><span class="day-chevron">▸</span><strong>${labelOf(key)}</strong><span class="day-meta"></span></td>`;
        list[0].before(header);
        header.addEventListener("click", () => { if (open.has(key)) open.delete(key); else open.add(key); paint(); });
        dayRows.set(key, header);
    });
    const empty = document.createElement("tr");
    empty.className = "empty-row";
    empty.innerHTML = `<td colspan="${span}"></td>`;
    (table.querySelector("tbody") || table).appendChild(empty);

    function paint() {
        const query = norm(search.value.trim());
        const filtering = Boolean(query) || Boolean(activeLabel);
        let visible = 0;
        groups.forEach((list, key) => {
            const matches = list.filter((tr) => sameState(tr, activeLabel) && (!query || norm(tr.textContent).includes(query)));
            const expanded = matches.length > 0 && (filtering || open.has(key));
            list.forEach((tr) => { tr.hidden = !expanded || !matches.includes(tr); });
            const header = dayRows.get(key);
            header.hidden = !matches.length;
            header.classList.toggle("is-open", expanded);
            header.querySelector(".day-chevron").textContent = expanded ? "▾" : "▸";
            const paidTotal = matches.filter(isPaid).reduce((sum, tr) => sum + money(cell(tr, totalIndex)), 0);
            header.querySelector(".day-meta").textContent = `${matches.length} pedido${matches.length === 1 ? "" : "s"} · ${clp(paidTotal)} pagados`;
            visible += matches.length;
        });
        empty.hidden = visible > 0;
        empty.querySelector("td").textContent = activeLabel
            ? `No hay pedidos «${activeLabel}» entre los últimos ${rows.length}.`
            : "No hay pedidos que coincidan con la búsqueda.";
    }
    search.addEventListener("input", paint);
    paint();

    // Toda la fila abre el pedido
    rows.forEach((tr) => {
        const link = tr.querySelector("a[href]");
        if (!link) return;
        tr.classList.add("row-link");
        tr.addEventListener("click", (event) => { if (!event.target.closest("a, button, form, input, select")) location.href = link.href; });
    });
})();
