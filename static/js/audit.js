/* GastroInsight AI · Auditoría: filtros instantáneos, períodos rápidos, mosaicos y grupos por día (sin tocar la plantilla). */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const main = document.querySelector("main") || document.body;
    const title = [...main.querySelectorAll("h1")].find((h) => /auditor/i.test(h.textContent));
    if (!title) return;
    const table = [...main.querySelectorAll("table")].find((t) => t.tHead && /acci/i.test(t.tHead.textContent) && /descrip/i.test(t.tHead.textContent));
    const form = [...main.querySelectorAll("form")].find((f) => f.querySelector("select") && f.method.toLowerCase() === "get");

    // ---------- Filtros: barra delgada e instantánea ----------
    if (form && !form.dataset.auditReady) {
        form.dataset.auditReady = "1";
        form.classList.add("audit-filters");
        const card = form.closest(".card");
        if (card) card.classList.add("audit-filter-card");
        const submitBtn = [...form.querySelectorAll("button, input[type=submit]")].find((b) => /filtrar/i.test(b.textContent || b.value));
        if (submitBtn) submitBtn.hidden = true;
        const clear = [...form.querySelectorAll("a, button")].find((b) => /limpiar/i.test(b.textContent));
        const active = [...form.elements].some((el) => el.name && el.type !== "submit" && el.value);
        if (clear) { clear.textContent = "✕ Limpiar"; clear.classList.add("status-chip", "chip-warn"); clear.hidden = !active; }
        const send = () => { try { sessionStorage.setItem("gi-audit-focus", document.activeElement && document.activeElement.name || ""); } catch (e) { /* sin almacenamiento */ } form.requestSubmit ? form.requestSubmit() : form.submit(); };
        form.querySelectorAll("select, input[type=date]").forEach((el) => el.addEventListener("change", send));
        const search = form.querySelector("input[type=search], input[type=text]");
        if (search) {
            search.placeholder = "🔎 Buscar en la descripción";
            let timer;
            search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(send, 700); });
            try {
                if (sessionStorage.getItem("gi-audit-focus") === search.name) {
                    search.focus();
                    search.setSelectionRange(search.value.length, search.value.length);
                }
                sessionStorage.removeItem("gi-audit-focus");
            } catch (e) { /* sin almacenamiento */ }
        }
        // Períodos rápidos
        const dates = [...form.querySelectorAll("input[type=date]")];
        if (dates.length >= 2) {
            const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
            const today = new Date();
            const bar = document.createElement("div");
            bar.className = "status-chips audit-periods";
            const periods = [["Hoy", 0], ["7 días", 6], ["30 días", 29], ["Todo", null]];
            periods.forEach(([label, days]) => {
                const b = document.createElement("button");
                b.type = "button";
                b.className = "status-chip";
                b.textContent = label;
                const from = days === null ? "" : iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - days));
                const to = days === null ? "" : iso(today);
                if (dates[0].value === from && dates[1].value === to) b.classList.add("is-active");
                b.addEventListener("click", () => { dates[0].value = from; dates[1].value = to; send(); });
                bar.appendChild(b);
            });
            form.prepend(bar);
        }
    }

    if (!table || table.dataset.auditReady) return;
    table.dataset.auditReady = "1";
    const heads = [...table.tHead.rows[0].cells].map((th) => th.textContent.trim().toLowerCase());
    const col = (re) => heads.findIndex((h) => re.test(h));
    const I = { fecha: col(/^fecha/), user: col(/^usuario/), action: col(/^acci/), mod: col(/^m[oó]dulo/), local: col(/^local/), desc: col(/^descrip/), ip: col(/^ip/) };
    const body = table.tBodies[0];
    const rows = [...body.rows].filter((r) => r.cells.length === heads.length);
    const text = (row, i) => (i >= 0 && row.cells[i] ? row.cells[i].textContent.trim() : "");
    const panel = table.closest(".card") || table.parentElement;
    panel.classList.add("page-panel", "eval-panel", "audit-panel");

    const MODULES = { ai_vision: "📷 Visión IA", cameras: "🎥 Cámaras", operations: "🍽️ Operación", sales: "💵 Ventas", menus: "📖 Carta",
                      analytics: "📊 Analítica", reports: "📄 Reportes", authentication: "👥 Cuentas", privacy: "🔒 Privacidad",
                      monitoring: "🛠️ Monitoreo", assistant_chat: "✨ Sazón", chatbot: "✨ Sazón", api: "🔌 API", venues: "🏠 Locales", feedback: "⭐ Opiniones" };
    const kindOf = (a) => (/elimin|borr|revoc/i.test(a) ? "bad" : /actualiz|edit|modific|cambi/i.test(a) ? "warn" : /cre|registr|alta/i.test(a) ? "done"
        : /inicio de sesi|login/i.test(a) ? "login" : /cierre|logout/i.test(a) ? "logout" : /export|descarg/i.test(a) ? "export" : "info");
    const DAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
    const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

    const data = rows.map((row) => {
        const m = text(row, I.fecha).match(/(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})/);
        return { row, user: text(row, I.user), action: text(row, I.action), local: text(row, I.local), kind: kindOf(text(row, I.action)),
                 date: m ? new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]) : null, dayKey: m ? `${m[3]}${m[2]}${m[1]}` : "0" };
    });
    const singleLocal = new Set(data.map((d) => d.local).filter((l) => l && l !== "—")).size <= 1;
    data.forEach((d) => {
        const c = d.row.cells;
        if (I.action >= 0) c[I.action].innerHTML = `<span class="inc-pill audit-${d.kind}">${d.action}</span>`;
        if (I.mod >= 0) { const mod = text(d.row, I.mod); c[I.mod].innerHTML = `<span class="eval-table" title="${mod}">${MODULES[mod] || mod}</span>`; }
        if (I.user >= 0) c[I.user].innerHTML = `<span class="audit-user"><span class="mgmt-avatar">${(d.user[0] || "?").toUpperCase()}</span>${d.user}</span>`;
        if (I.ip >= 0) c[I.ip].classList.add("audit-ip");
        if (I.fecha >= 0 && d.date) { c[I.fecha].title = c[I.fecha].textContent.trim(); c[I.fecha].textContent = d.date.toTimeString().slice(0, 5); }
        if (singleLocal && I.local >= 0) c[I.local].hidden = true;
    });
    if (singleLocal && I.local >= 0) table.tHead.rows[0].cells[I.local].hidden = true;
    if (I.fecha >= 0) table.tHead.rows[0].cells[I.fecha].textContent = "Hora";
    const colspan = heads.length - (singleLocal && I.local >= 0 ? 1 : 0);

    // ---------- Grupos por día ----------
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
            name = diff === 0 ? "Hoy" : diff === 1 ? "Ayer" : `${DAYS[date.getDay()]} ${date.getDate()} de ${MONTHS[date.getMonth()]}`;
        }
        const users = new Set(items.map((d) => d.user)).size;
        head.innerHTML = `<td colspan="${colspan}"><span class="eval-caret">▾</span><strong>${name}</strong><span class="eval-day-meta"> · ${items.length} registro${items.length === 1 ? "" : "s"} · ${users} persona${users === 1 ? "" : "s"}</span></td>`;
        const collapse = (on) => { head.classList.toggle("is-collapsed", on); items.forEach((d) => { d.row.hidden = on; }); };
        head.addEventListener("click", () => collapse(!head.classList.contains("is-collapsed")));
        body.appendChild(head);
        items.forEach((d) => body.appendChild(d.row));
        collapse(index >= 3);
        index += 1;
    });

    // ---------- Mosaicos ----------
    const countText = [...panel.querySelectorAll("p, div, span")].find((el) => el.children.length === 0 && /\d+\s+registro/.test(el.textContent));
    const total = countText ? countText.textContent.match(/(\d[\d.]*)/)[1] : String(data.length);
    if (countText) countText.hidden = true;
    const n = (k) => data.filter((d) => d.kind === k).length;
    const summary = document.createElement("div");
    summary.className = "orders-summary eval-summary";
    summary.innerHTML = [
        ["📋", total, "Registros", "con los filtros"],
        ["👥", new Set(data.map((d) => d.user)).size, "Personas", "en pantalla"],
        ["🔑", n("login"), "Inicios de sesión", "en pantalla"],
        ["✏️", n("done") + n("warn") + n("bad"), "Cambios", "crear, editar o borrar"],
        ["⬇️", n("export"), "Exportaciones", "en pantalla"],
    ].map(([icon, value, label, note]) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span><small>${note}</small></div>`).join("");
    // «Exportar CSV» pasa del encabezado a un mosaico de acción junto al resumen
    const exportLink = [...document.querySelectorAll("main a")].find((a) => /exportar/i.test(a.textContent) && !a.closest(".orders-summary"));
    if (exportLink) {
        const tile = document.createElement("a");
        tile.className = "mini-kpi mini-kpi-action";
        tile.href = exportLink.href;
        tile.title = "Descarga los registros con los filtros aplicados";
        tile.innerHTML = '<span class="mini-kpi-icon">⬇️</span><strong>Exportar</strong><span>CSV con los filtros</span>';
        summary.appendChild(tile);
        const holder = exportLink.parentElement;
        exportLink.remove();
        if (holder && !holder.children.length && !holder.textContent.trim()) holder.remove();
    }
    panel.prepend(summary);
    if (!data.length) {
        const empty = document.createElement("tr");
        empty.className = "eval-empty";
        empty.innerHTML = `<td colspan="${colspan}">No hay registros con estos filtros.</td>`;
        body.appendChild(empty);
    }
})();