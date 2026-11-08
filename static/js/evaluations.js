/* GastroInsight AI · Evaluaciones: mosaicos, filtros instantáneos y grupos por día (sin tocar la plantilla). */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1" || !/^\/operations\/evaluations\/?$/.test(location.pathname)) return;
    const main = document.querySelector("main") || document.body;
    const table = [...main.querySelectorAll("table")].find((t) => t.tHead && /valoraci/i.test(t.tHead.textContent));
    if (!table || table.dataset.evalReady) return;
    table.dataset.evalReady = "1";

    const heads = [...table.tHead.rows[0].cells].map((th) => th.textContent.trim().toLowerCase());
    const col = (name) => heads.findIndex((h) => h.startsWith(name));
    const I = { id: col("id"), local: col("local"), mesa: col("mesa"), plato: col("plato"), val: col("valora"), com: col("coment"), fecha: col("fecha") };
    const body = table.tBodies[0];
    const rows = [...body.rows].filter((r) => r.cells.length === heads.length);

    // ---------- Encabezado centrado y botón como mosaico ----------
    const title = [...main.querySelectorAll("h1")].find((h) => /evaluaci/i.test(h.textContent));
    const hero = title && title.closest(".card");
    let action = null;
    if (hero) {
        action = hero.querySelector("a.btn, button.btn");
        const header = document.createElement("section");
        header.className = "page-header";
        const box = document.createElement("div");
        if (!/⭐/.test(title.textContent)) title.insertAdjacentText("afterbegin", "⭐ ");
        box.appendChild(title);
        const text = hero.querySelector("p");
        if (text) { text.classList.add("muted"); box.appendChild(text); }
        header.appendChild(box);
        hero.replaceWith(header);
    }
    const panel = table.closest(".card") || table.parentElement;
    panel.classList.add("page-panel", "eval-panel");

    // ---------- Datos de cada fila ----------
    const DAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    const data = rows.map((row) => {
        const cell = (i) => (i >= 0 ? row.cells[i] : null);
        const text = (i) => (cell(i) ? cell(i).textContent.trim() : "");
        const rating = parseInt(text(I.val), 10) || 0;
        const m = text(I.fecha).match(/(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})/);
        const date = m ? new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]) : null;
        return { row, rating, date, local: text(I.local), search: [text(I.mesa), text(I.plato), text(I.com), text(I.local)].join(" ").toLowerCase(),
                 dayKey: m ? `${m[3]}-${m[2]}-${m[1]}` : "sin-fecha" };
    });

    // ---------- Celdas más legibles ----------
    const singleLocal = new Set(data.map((d) => d.local)).size <= 1;
    data.forEach((d) => {
        const c = d.row.cells;
        if (I.val >= 0) {
            const label = (c[I.val].textContent.split("—")[1] || "").trim();
            c[I.val].innerHTML = `<span class="eval-stars" aria-label="${d.rating} de 5">${"★".repeat(d.rating)}<i>${"★".repeat(5 - d.rating)}</i></span>`
                + `<span class="eval-pill eval-r${d.rating}">${label || d.rating + "/5"}</span>`;
        }
        if (I.com >= 0) {
            const comment = c[I.com].textContent.trim();
            c[I.com].innerHTML = comment ? `<span class="eval-comment">“${comment.replace(/[<>&]/g, (ch) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[ch]))}”</span>` : '<span class="muted">Sin comentario</span>';
        }
        if (I.mesa >= 0) c[I.mesa].innerHTML = `<span class="eval-table">${c[I.mesa].textContent.trim()}</span>`;
        if (I.id >= 0) c[I.id].classList.add("eval-id");
        if (I.fecha >= 0 && d.date) {
            c[I.fecha].title = c[I.fecha].textContent.trim();
            c[I.fecha].textContent = d.date.toTimeString().slice(0, 5);
        }
        if (singleLocal && I.local >= 0) c[I.local].hidden = true;
    });
    if (singleLocal && I.local >= 0) table.tHead.rows[0].cells[I.local].hidden = true;
    if (I.fecha >= 0) table.tHead.rows[0].cells[I.fecha].textContent = "Hora";
    const colspan = heads.length - (singleLocal && I.local >= 0 ? 1 : 0);

    // ---------- Grupos por día (más recientes primero) ----------
    data.sort((a, b) => (b.date || 0) - (a.date || 0));
    const groups = new Map();
    data.forEach((d) => { if (!groups.has(d.dayKey)) groups.set(d.dayKey, []); groups.get(d.dayKey).push(d); });
    const today = new Date(); today.setHours(0, 0, 0, 0);
    let index = 0;
    groups.forEach((items, key) => {
        const head = document.createElement("tr");
        head.className = "eval-day";
        const date = items[0].date;
        let name = "Sin fecha";
        if (date) {
            const day = new Date(date); day.setHours(0, 0, 0, 0);
            const diff = Math.round((today - day) / 86400000);
            name = diff === 0 ? "Hoy" : diff === 1 ? "Ayer" : `${DAYS[date.getDay()]} ${date.getDate()} de ${MONTHS[date.getMonth()]}`;
        }
        head.innerHTML = `<td colspan="${colspan}"><span class="eval-caret">▾</span><strong>${name}</strong><span class="eval-day-meta"></span></td>`;
        head.dataset.collapsed = index >= 3 ? "1" : "0";
        head.addEventListener("click", () => { head.dataset.collapsed = head.dataset.collapsed === "1" ? "0" : "1"; apply(); });
        body.appendChild(head);
        items.forEach((d) => { d.head = head; body.appendChild(d.row); });
        head._items = items;
        index += 1;
    });

    // ---------- Mosaicos y barra de filtros ----------
    const top = document.createElement("div");
    top.className = "eval-top";
    top.innerHTML = `<div class="orders-summary eval-summary"></div>
        <div class="mgmt-toolbar eval-toolbar">
            <input type="search" class="orders-search mgmt-search" placeholder="🔎 Buscar plato, mesa o comentario" aria-label="Buscar evaluaciones">
            <div class="status-chips" data-eval="group"></div>
            <div class="status-chips" data-eval="period"></div>
            ${singleLocal ? "" : '<div class="status-chips" data-eval="local"></div>'}
        </div>`;
    panel.prepend(top);
    if (main.querySelector(".pagination, nav[aria-label*='agin']")) {
        top.insertAdjacentHTML("beforeend", '<p class="eval-note">ℹ️ Los filtros y cifras consideran las evaluaciones de esta página.</p>');
    }
    const summary = top.querySelector(".eval-summary");
    const search = top.querySelector("input");
    const state = { group: "all", period: "all", local: "all", text: "" };
    const GROUPS = [["all", "Todas", () => true], ["good", "😊 Satisfechas", (d) => d.rating >= 4],
                    ["mid", "😐 Neutrales", (d) => d.rating === 3], ["bad", "😞 Insatisfechas", (d) => d.rating > 0 && d.rating <= 2]];
    const PERIODS = [["all", "Todo", null], ["today", "Hoy", 0], ["7", "7 días", 6], ["30", "30 días", 29]];

    function chips(name, options) {
        const bar = top.querySelector(`[data-eval="${name}"]`);
        if (!bar) return;
        options.forEach(([value, label]) => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "status-chip" + (value === "all" ? " is-active" : "");
            b.dataset.value = value;
            b.dataset.label = label;
            b.textContent = label;
            bar.appendChild(b);
        });
        bar.addEventListener("click", (event) => {
            const b = event.target.closest("[data-value]");
            if (!b) return;
            bar.querySelectorAll("[data-value]").forEach((x) => x.classList.toggle("is-active", x === b));
            state[name] = b.dataset.value;
            apply();
        });
    }
    chips("group", GROUPS);
    chips("period", PERIODS);
    chips("local", [["all", "Todos los locales"], ...[...new Set(data.map((d) => d.local))].map((l) => [l, l])]);
    search.addEventListener("input", () => { state.text = search.value.trim().toLowerCase(); apply(); });

    const inPeriod = (d, period) => {
        if (period === "all") return true;
        if (!d.date) return false;
        const limit = new Date(today);
        limit.setDate(limit.getDate() - PERIODS.find((p) => p[0] === period)[2]);
        return d.date >= limit;
    };
    const matches = (d, skip) => (skip === "group" || GROUPS.find((g) => g[0] === state.group)[2](d))
        && (skip === "period" || inPeriod(d, state.period))
        && (state.local === "all" || d.local === state.local)
        && (!state.text || d.search.includes(state.text));
    const avg = (list) => (list.length ? (list.reduce((s, d) => s + d.rating, 0) / list.length) : 0);
    const fmt = (n) => n.toFixed(1).replace(".", ",");

    function apply() {
        const shown = data.filter((d) => matches(d));
        groups.forEach((items) => {
            const head = items[0].head;
            const visible = items.filter((d) => matches(d));
            head.hidden = !visible.length;
            head.querySelector(".eval-day-meta").textContent = visible.length
                ? ` · ${visible.length} evaluación${visible.length === 1 ? "" : "es"} · ⭐ ${fmt(avg(visible))}` : "";
            head.classList.toggle("is-collapsed", head.dataset.collapsed === "1");
            items.forEach((d) => { d.row.hidden = !visible.includes(d) || head.dataset.collapsed === "1"; });
        });
        top.querySelectorAll('[data-eval="group"] [data-value]').forEach((b) => {
            const n = data.filter((d) => matches(d, "group") && GROUPS.find((g) => g[0] === b.dataset.value)[2](d)).length;
            b.innerHTML = `${b.dataset.label} <b>${n}</b>`;
        });
        const good = shown.filter((d) => d.rating >= 4).length;
        const bad = shown.filter((d) => d.rating > 0 && d.rating <= 2).length;
        const href = action && (action.getAttribute("href") || "");
        summary.innerHTML = [
            ["📝", shown.length, "Evaluaciones", ""],
            ["⭐", shown.length ? fmt(avg(shown)) : "—", "Promedio", "de 5"],
            ["😊", shown.length ? Math.round(100 * good / shown.length) + " %" : "—", "Satisfechas", "4 y 5 estrellas"],
            ["😞", bad, "Insatisfechas", "1 y 2 estrellas"],
        ].map(([icon, value, label, note]) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span>${note ? `<small>${note}</small>` : ""}</div>`).join("")
            + (href ? `<a class="mini-kpi mini-kpi-action" href="${href}"><span class="mini-kpi-icon">＋</span><strong>Registrar</strong><span>Evaluación</span></a>` : "");
        let empty = body.querySelector(".eval-empty");
        if (!shown.length) {
            if (!empty) { empty = document.createElement("tr"); empty.className = "eval-empty"; empty.innerHTML = `<td colspan="${colspan}">Ninguna evaluación coincide con los filtros.</td>`; body.appendChild(empty); }
            empty.hidden = false;
        } else if (empty) empty.hidden = true;
    }
    apply();
})();