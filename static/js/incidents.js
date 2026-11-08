/* GastroInsight AI · Incidencias: mosaicos, filtros instantáneos y grupos por día (sin tocar la plantilla). */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const main = document.querySelector("main") || document.body;
    const table = [...main.querySelectorAll("table")].find((t) => t.tHead && /severidad/i.test(t.tHead.textContent) && /m[oó]dulo/i.test(t.tHead.textContent));
    if (!table || table.dataset.incReady) return;
    table.dataset.incReady = "1";

    const heads = [...table.tHead.rows[0].cells].map((th) => th.textContent.trim().toLowerCase());
    const col = (name) => heads.findIndex((h) => h.startsWith(name));
    const I = { fecha: col("fecha"), local: col("local"), mod: col("m"), titulo: col("t"), sev: col("sever"), estado: col("estado"), rev: col("revis") };
    const body = table.tBodies[0];
    const rows = [...body.rows].filter((r) => r.cells.length === heads.length);
    const text = (row, i) => (i >= 0 && row.cells[i] ? row.cells[i].textContent.trim() : "");

    // ---------- Encabezado centrado ----------
    const title = [...main.querySelectorAll("h1")].find((h) => /incidencia/i.test(h.textContent));
    const hero = title && title.closest(".card");
    if (hero) {
        const header = document.createElement("section");
        header.className = "page-header";
        const box = document.createElement("div");
        if (!/🛠/.test(title.textContent)) title.insertAdjacentText("afterbegin", "🛠️ ");
        box.appendChild(title);
        const p = hero.querySelector("p");
        if (p) { p.classList.add("muted"); box.appendChild(p); }
        const extra = [...hero.querySelectorAll("a.btn, button.btn")];
        header.appendChild(box);
        if (extra.length) { const actions = document.createElement("div"); extra.forEach((b) => actions.appendChild(b)); header.appendChild(actions); }
        hero.replaceWith(header);
    }
    const panel = table.closest(".card") || table.parentElement;
    panel.classList.add("page-panel", "eval-panel", "inc-panel");

    // ---------- Clasificación ----------
    const MODULES = { ai_vision: "📷 Visión IA", cameras: "🎥 Cámaras", operations: "🍽️ Operación", sales: "💵 Ventas", menus: "📖 Carta",
                      analytics: "📊 Analítica", reports: "📄 Reportes", authentication: "👥 Cuentas", privacy: "🔒 Privacidad",
                      monitoring: "🛠️ Monitoreo", assistant_chat: "✨ Sazón", chatbot: "✨ Sazón", api: "🔌 API", venues: "🏠 Locales" };
    const sevKind = (s) => (/cr[ií]t|error|grave/i.test(s) ? "bad" : /advert|warn/i.test(s) ? "warn" : "info");
    const stateKind = (s) => (/resuel|cerrad|solucion/i.test(s) ? "done" : /revis|progres|curso/i.test(s) ? "review" : "open");
    const DAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

    const data = rows.map((row) => {
        const m = text(row, I.fecha).match(/(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})/);
        const sev = text(row, I.sev), estado = text(row, I.estado), mod = text(row, I.mod);
        return { row, sev, estado, mod, local: text(row, I.local), sevKind: sevKind(sev), stateKind: stateKind(estado),
                 date: m ? new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]) : null, dayKey: m ? `${m[3]}${m[2]}${m[1]}` : "0",
                 search: heads.map((_, i) => text(row, i)).join(" ").toLowerCase() };
    });

    // ---------- Celdas legibles ----------
    const singleLocal = new Set(data.map((d) => d.local)).size <= 1;
    data.forEach((d) => {
        const c = d.row.cells;
        if (I.sev >= 0) c[I.sev].innerHTML = `<span class="inc-pill inc-${d.sevKind}">${d.sevKind === "bad" ? "🔴" : d.sevKind === "warn" ? "🟠" : "🔵"} ${d.sev}</span>`;
        if (I.estado >= 0) c[I.estado].innerHTML = `<span class="inc-pill inc-${d.stateKind}">${d.stateKind === "done" ? "✅" : d.stateKind === "review" ? "🔎" : "⏳"} ${d.estado}</span>`;
        if (I.mod >= 0) c[I.mod].innerHTML = `<span class="eval-table" title="${d.mod}">${MODULES[d.mod] || d.mod}</span>`;
        if (I.titulo >= 0) c[I.titulo].classList.add("inc-title");
        if (I.rev >= 0 && !text(d.row, I.rev)) c[I.rev].innerHTML = '<span class="muted">—</span>';
        if (I.fecha >= 0 && d.date) { c[I.fecha].title = c[I.fecha].textContent.trim(); c[I.fecha].textContent = d.date.toTimeString().slice(0, 5); }
        if (singleLocal && I.local >= 0) c[I.local].hidden = true;
    });
    if (singleLocal && I.local >= 0) table.tHead.rows[0].cells[I.local].hidden = true;
    if (I.fecha >= 0) table.tHead.rows[0].cells[I.fecha].textContent = "Hora";
    const colspan = heads.length - (singleLocal && I.local >= 0 ? 1 : 0);
    [...body.rows].filter((r) => !rows.includes(r)).forEach((r) => r.remove()); // fila «sin datos» original

    // ---------- Grupos por día ----------
    data.sort((a, b) => (b.date || 0) - (a.date || 0));
    const groups = new Map();
    data.forEach((d) => { if (!groups.has(d.dayKey)) groups.set(d.dayKey, []); groups.get(d.dayKey).push(d); });
    const today = new Date(); today.setHours(0, 0, 0, 0);
    let index = 0;
    groups.forEach((items) => {
        const head = document.createElement("tr");
        head.className = "eval-day";
        const date = items[0].date;
        let name = "Sin fecha";
        if (date) {
            const day = new Date(date); day.setHours(0, 0, 0, 0);
            const diff = Math.round((today - day) / 86400000);
            name = diff === 0 ? "Hoy" : diff === 1 ? "Ayer" : `${DAYS[date.getDay()]} ${date.getDate()} de ${MONTHS[date.getMonth()]} ${date.getFullYear() !== today.getFullYear() ? date.getFullYear() : ""}`;
        }
        head.innerHTML = `<td colspan="${colspan}"><span class="eval-caret">▾</span><strong>${name}</strong><span class="eval-day-meta"></span></td>`;
        head.dataset.collapsed = index >= 3 ? "1" : "0";
        head.addEventListener("click", () => { head.dataset.collapsed = head.dataset.collapsed === "1" ? "0" : "1"; apply(); });
        body.appendChild(head);
        items.forEach((d) => { d.head = head; body.appendChild(d.row); });
        index += 1;
    });

    // ---------- Mosaicos y filtros ----------
    const top = document.createElement("div");
    top.innerHTML = `<div class="orders-summary eval-summary"></div>
        <div class="mgmt-toolbar eval-toolbar">
            <input type="search" class="orders-search mgmt-search" placeholder="🔎 Buscar incidencia" aria-label="Buscar incidencias">
            <div class="status-chips" data-inc="state"></div>
            <div class="status-chips" data-inc="sev"></div>
        </div>
        <div class="mgmt-toolbar"><div class="status-chips" data-inc="mod"></div></div>`;
    panel.prepend(top);
    const state = { state: "*", sev: "*", mod: "*", text: "" };
    const FILTERS = {
        state: [["*", "Todas"], ["open", "⏳ Abiertas"], ["review", "🔎 En revisión"], ["done", "✅ Resueltas"]],
        sev: [["*", "Toda severidad"], ["bad", "🔴 Error o crítica"], ["warn", "🟠 Advertencia"], ["info", "🔵 Informativa"]],
        mod: [["*", "Todos los módulos"], ...[...new Set(data.map((d) => d.mod))].map((m) => [m, MODULES[m] || m])],
    };
    const keyOf = { state: (d) => d.stateKind, sev: (d) => d.sevKind, mod: (d) => d.mod };
    const matches = (d, skip) => Object.keys(keyOf).every((k) => k === skip || state[k] === "*" || keyOf[k](d) === state[k])
        && (!state.text || d.search.includes(state.text));
    Object.entries(FILTERS).forEach(([name, options]) => {
        const bar = top.querySelector(`[data-inc="${name}"]`);
        options.forEach(([value, label]) => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "status-chip" + (value === "*" ? " is-active" : "");
            b.dataset.value = value;
            b.dataset.label = label;
            bar.appendChild(b);
        });
        bar.addEventListener("click", (e) => {
            const b = e.target.closest("[data-value]");
            if (!b) return;
            bar.querySelectorAll("[data-value]").forEach((x) => x.classList.toggle("is-active", x === b));
            state[name] = b.dataset.value;
            apply();
        });
    });
    top.querySelector("input").addEventListener("input", (e) => { state.text = e.target.value.trim().toLowerCase(); apply(); });

    function apply() {
        const shown = data.filter((d) => matches(d));
        groups.forEach((items) => {
            const head = items[0].head;
            const visible = items.filter((d) => matches(d));
            head.hidden = !visible.length;
            head.classList.toggle("is-collapsed", head.dataset.collapsed === "1");
            head.querySelector(".eval-day-meta").textContent = visible.length ? ` · ${visible.length} incidencia${visible.length === 1 ? "" : "s"}` : "";
            items.forEach((d) => { d.row.hidden = !visible.includes(d) || head.dataset.collapsed === "1"; });
        });
        Object.keys(FILTERS).forEach((name) => {
            top.querySelectorAll(`[data-inc="${name}"] [data-value]`).forEach((b) => {
                const n = data.filter((d) => matches(d, name) && (b.dataset.value === "*" || keyOf[name](d) === b.dataset.value)).length;
                b.innerHTML = `${b.dataset.label} <b>${n}</b>`;
                b.hidden = n === 0 && b.dataset.value !== "*" && !b.classList.contains("is-active");
            });
        });
        const count = (fn) => shown.filter(fn).length;
        top.querySelector(".eval-summary").innerHTML = [
            ["🛠️", shown.length, "Incidencias"],
            ["⏳", count((d) => d.stateKind !== "done"), "Abiertas"],
            ["🔴", count((d) => d.sevKind === "bad"), "Errores o críticas"],
            ["🟠", count((d) => d.sevKind === "warn"), "Advertencias"],
            ["✅", count((d) => d.stateKind === "done"), "Resueltas"],
        ].map(([icon, value, label]) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span></div>`).join("");
        let empty = body.querySelector(".eval-empty");
        if (!shown.length) {
            if (!empty) { empty = document.createElement("tr"); empty.className = "eval-empty"; body.appendChild(empty); }
            empty.innerHTML = `<td colspan="${colspan}">${data.length ? "Ninguna incidencia coincide con los filtros." : "✅ Sin incidencias: la plataforma funciona sin advertencias ni errores registrados."}</td>`;
            empty.hidden = false;
        } else if (empty) empty.hidden = true;
    }
    apply();
})();