/* GastroInsight AI · Reportes: dos columnas, períodos rápidos y actualización automática. */
(function () {
    "use strict";
    if (location.pathname !== "/reports/" || document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    const cards = [...main.children].filter((el) => el.matches(".card, section, article, div") && !el.matches(".messages"));

    // Encabezado: título limpio (la explicación queda en el ícono ⓘ)
    const head = cards.find((card) => card.querySelector("h1"));
    if (head) {
        head.classList.add("reports-head");
        head.querySelectorAll("p").forEach((p) => { if (!p.classList.contains("page-help")) p.hidden = true; });
    }

    // Tarjetas de reportes en dos columnas
    const reportCards = cards.filter((card) => card !== head && card.querySelector("form"));
    if (reportCards.length >= 2) {
        const grid = document.createElement("div");
        grid.className = "reports-grid";
        reportCards[0].before(grid);
        reportCards.forEach((card) => { card.classList.add("reports-card"); grid.appendChild(card); });
    } else {
        reportCards.forEach((card) => card.classList.add("reports-card"));
    }

    const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    const shift = (days) => { const d = new Date(); d.setDate(d.getDate() + days); return d; };
    const monday = (weeksBack) => { const d = new Date(); const day = (d.getDay() + 6) % 7; d.setDate(d.getDate() - day - 7 * weeksBack); return d; };
    const firstOfMonth = (monthsBack) => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth() - monthsBack, 1); };

    reportCards.forEach((card) => {
        const form = card.querySelector("form");
        const date = form.querySelector("input[type=date]");
        const select = form.querySelector("select");
        const submit = () => (form.requestSubmit ? form.requestSubmit() : form.submit());
        form.classList.add("reports-form");
        form.querySelectorAll("input[type=date], select").forEach((input) => input.addEventListener("change", submit));
        form.querySelectorAll("button[type=submit], input[type=submit]").forEach((b) => b.classList.add("reports-apply"));
        if (!date) return;

        const presets = select ? [
            ["Esta semana", /seman/i, () => monday(0)],
            ["Semana pasada", /seman/i, () => monday(1)],
            ["Este mes", /mens|mes/i, () => firstOfMonth(0)],
            ["Mes pasado", /mens|mes/i, () => firstOfMonth(1)],
        ] : [["Hoy", null, () => shift(0)], ["Ayer", null, () => shift(-1)]];
        const bar = document.createElement("div");
        bar.className = "reports-presets";
        presets.forEach(([label, pattern, value]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-small btn-secondary";
            button.textContent = label;
            button.addEventListener("click", () => {
                if (select && pattern) {
                    const option = [...select.options].find((o) => pattern.test(o.textContent) || pattern.test(o.value));
                    if (option) select.value = option.value;
                }
                date.value = iso(value());
                submit();
            });
            bar.appendChild(button);
        });
        form.after(bar);
    });
})();

/* GastroInsight AI · Reportes con el estilo de la plataforma (página principal y reportes abiertos). */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    const path = location.pathname;

    if (path === "/reports/") {
        const grid = main.querySelector(".reports-grid") || main.querySelector(".reports-card");
        if (!grid || grid.closest(".page-panel")) return;
        const panel = document.createElement("section");
        panel.className = "card page-panel reports-panel";
        grid.before(panel);
        panel.appendChild(grid.classList.contains("reports-grid") ? grid : grid.parentElement);
        main.querySelectorAll(".reports-card").forEach((card) => {
            const title = card.querySelector("h2, h3");
            const daily = !card.querySelector("select");
            if (title && !card.querySelector(".reports-icon")) {
                const icon = document.createElement("span");
                icon.className = "reports-icon";
                icon.textContent = daily ? "📅" : "🗓️";
                title.before(icon);
                const note = document.createElement("p");
                note.className = "reports-note";
                note.textContent = daily ? "Ventas, operación, evaluaciones y métricas visuales de un día." : "El mismo análisis para una semana o un mes completo.";
                title.after(note);
            }
            card.querySelectorAll("p, strong").forEach((el) => { if (/per[ií]odo seleccionado/i.test(el.textContent)) (el.closest("p") || el).classList.add("reports-period"); });
            card.querySelectorAll("a.btn").forEach((link) => {
                const box = link.parentElement;
                if (!box || box === card || box.classList.contains("reports-venue")) return;
                box.classList.add("reports-venue");
                if (!/→/.test(link.textContent)) link.textContent = "Ver reporte →";
            });
        });
        return;
    }

    // Reportes abiertos (diario, semanal o mensual)
    if (/^\/reports\/(?!explorar)/.test(path)) {
        const header = main.querySelector(".page-header");
        main.querySelectorAll("a.btn, a[href*='pdf'], a[href*='csv']").forEach((link) => {
            const text = link.textContent;
            if (/pdf/i.test(text + link.href) && !/📄/.test(text)) link.textContent = `📄 ${text.trim()}`;
            else if (/csv/i.test(text + link.href) && !/📊/.test(text)) link.textContent = `📊 ${text.trim()}`;
        });
        const blocks = [...main.children].filter((el) => el !== header && !el.matches("script, .messages"));
        if (!blocks.length || main.querySelector(".report-panel")) return;
        const panel = document.createElement("section");
        panel.className = "card page-panel report-panel";
        blocks[0].before(panel);
        blocks.forEach((el) => panel.appendChild(el));
    }
})();

/* GastroInsight AI · Reportes: adelanto de estadísticas, encabezado ordenado y secciones plegables. */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    const path = location.pathname;
    const tile = (icon, value, label) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span></div>`;

    // Página de Reportes: adelanto de las cifras en cada local
    if (path === "/reports/") {
        main.querySelectorAll(".reports-venue").forEach(async (venue) => {
            const link = venue.querySelector("a[href]");
            if (!link || venue.querySelector(".report-preview")) return;
            const preview = document.createElement("div");
            preview.className = "orders-summary report-preview";
            preview.innerHTML = '<p class="muted">Calculando…</p>';
            link.before(preview);
            try {
                const response = await fetch(link.href, { credentials: "same-origin" });
                const doc = new DOMParser().parseFromString(await response.text(), "text/html");
                // Busca cada cifra por su etiqueta visible y toma el número de la misma tarjeta
                const leaves = [...doc.querySelectorAll("main *")].filter((el) => !el.children.length);
                const pick = (pattern) => {
                    for (const label of leaves.filter((el) => pattern.test(el.textContent.trim()) && el.textContent.trim().length < 40)) {
                        let box = label.parentElement;
                        for (let depth = 0; depth < 3 && box; depth += 1, box = box.parentElement) {
                            const number = [...box.querySelectorAll("*")].find((el) => !el.children.length && el !== label
                                && /\d/.test(el.textContent) && el.textContent.trim().length < 20);
                            if (number) return number.textContent.trim();
                        }
                    }
                    return "—";
                };
                preview.innerHTML = tile("💰", pick(/^ventas totales$/i), "Ventas") + tile("🧾", pick(/^pedidos pagados$/i), "Pedidos")
                    + tile("🎫", pick(/^ticket promedio$/i), "Ticket") + tile("✖️", pick(/^pedidos anulados$/i), "Anulados");
            } catch (e) { preview.innerHTML = '<p class="muted">No se pudo calcular el adelanto.</p>'; }
        });
        return;
    }

    // Reporte abierto: encabezado ordenado y secciones plegables
    const panel = main.querySelector(".report-panel");
    if (!/^\/reports\/(?!explorar)/.test(path) || !panel) return;
    const cards = [...panel.querySelectorAll(":scope > .card, :scope > section")];
    const head = cards.find((c) => c.querySelector("h1") || [...c.querySelectorAll("a")].some((a) => /volver/i.test(a.textContent)));
    if (head) {
        head.classList.add("report-head");
        const back = [...head.querySelectorAll("a")].find((a) => /volver/i.test(a.textContent));
        if (back) { back.classList.add("report-back"); back.textContent = "← Reportes"; head.prepend(back); }
        head.querySelectorAll("p").forEach((p) => { if (/^(local|fecha|per[ií]odo)\s*:/i.test(p.textContent.trim())) p.classList.add("report-chip"); });
        const downloads = [...head.querySelectorAll("a.btn")];
        if (downloads.length) {
            const row = document.createElement("div");
            row.className = "page-actions report-downloads";
            downloads[0].before(row);
            downloads.forEach((a) => row.appendChild(a));
        }
    }
    const sections = cards.filter((c) => c !== head && c.querySelector(":scope > h2"));
    if (sections.length < 2) return;
    sections.forEach((section, index) => {
        const title = section.querySelector(":scope > h2");
        const body = document.createElement("div");
        body.className = "report-body";
        [...section.childNodes].forEach((node) => { if (node !== title) body.appendChild(node); });
        section.appendChild(body);
        section.classList.add("report-section");
        const hint = (body.querySelector("p") || {}).textContent || "";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "report-toggle";
        button.innerHTML = `<span class="rt-chevron">▸</span><span class="rt-title"></span><small class="rt-hint"></small>`;
        button.querySelector(".rt-title").textContent = title.textContent.trim();
        button.querySelector(".rt-hint").textContent = hint.length > 70 ? `${hint.slice(0, 70).trim()}…` : hint;
        title.replaceWith(button);
        const set = (open) => {
            body.hidden = !open;
            section.classList.toggle("is-open", open);
            button.querySelector(".rt-chevron").textContent = open ? "▾" : "▸";
            if (open) window.dispatchEvent(new Event("resize"));
        };
        button.addEventListener("click", () => set(body.hidden));
        set(index === 0);
    });
    const controls = document.createElement("div");
    controls.className = "report-controls";
    controls.innerHTML = '<button type="button" class="btn btn-small btn-secondary" data-all="1">Expandir todo</button><button type="button" class="btn btn-small btn-secondary" data-all="0">Contraer todo</button>';
    controls.addEventListener("click", (event) => {
        const button = event.target.closest("[data-all]");
        if (!button) return;
        sections.forEach((s) => {
            const body = s.querySelector(".report-body");
            const open = button.dataset.all === "1";
            body.hidden = !open;
            s.classList.toggle("is-open", open);
            s.querySelector(".rt-chevron").textContent = open ? "▾" : "▸";
        });
        window.dispatchEvent(new Event("resize"));
    });
    sections[0].before(controls);
})();

/* GastroInsight AI · Reportes: «Ver reporte» junto al calendario cuando hay un solo local. */
(function () {
    "use strict";
    if (location.pathname !== "/reports/" || document.body.dataset.embed === "1") return;
    document.querySelectorAll(".reports-card").forEach((card) => {
        const venues = card.querySelectorAll(".reports-venue");
        const form = card.querySelector(".reports-form");
        if (venues.length !== 1 || !form || form.querySelector(".reports-open")) return;
        const link = venues[0].querySelector("a.btn[href]");
        if (!link) return;
        link.classList.add("reports-open");
        link.classList.remove("btn-secondary");
        link.classList.add("btn-primary");
        form.appendChild(link);
    });
})();

/* GastroInsight AI · Tarjetas de Reportes en dos columnas: calendario a la izquierda, cifras a la derecha. */
(function () {
    "use strict";
    if (location.pathname !== "/reports/" || document.body.dataset.embed === "1") return;
    document.querySelectorAll(".reports-card").forEach((card) => {
        if (card.querySelector(".rc-body")) return;
        const form = card.querySelector(".reports-form");
        const venues = [...card.querySelectorAll(".reports-venue")];
        if (!form || !venues.length) return;
        const body = document.createElement("div");
        body.className = "rc-body";
        const left = document.createElement("div");
        left.className = "rc-left";
        const right = document.createElement("div");
        right.className = "rc-right";
        form.before(body);
        body.append(left, right);
        [form, card.querySelector(".reports-presets"), card.querySelector(".reports-period")].forEach((el) => { if (el) left.appendChild(el); });
        venues.forEach((venue) => right.appendChild(venue));
    });
})();

/* GastroInsight AI · Reportes: vista de fecha con flechas, control segmentado y encabezado compacto. */
(function () {
    "use strict";
    if (location.pathname !== "/reports/" || document.body.dataset.embed === "1") return;
    const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    const parse = (value) => { const [y, m, d] = (value || "").split("-").map(Number); return y ? new Date(y, m - 1, d) : new Date(); };
    const fmt = (d, options) => d.toLocaleDateString("es-CL", options);
    const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

    document.querySelectorAll(".reports-card").forEach((card) => {
        if (card.querySelector(".date-widget")) return;
        // Encabezado compacto en una fila
        const icon = card.querySelector(".reports-icon");
        const title = card.querySelector("h2, h3");
        const note = card.querySelector(".reports-note");
        if (icon && title) {
            const head = document.createElement("div");
            head.className = "rc-head";
            icon.before(head);
            const text = document.createElement("div");
            text.className = "rc-head-text";
            head.append(icon, text);
            text.appendChild(title);
            if (note) text.appendChild(note);
        }

        const left = card.querySelector(".rc-left");
        const form = card.querySelector(".reports-form");
        const input = form && form.querySelector("input[type=date]");
        if (!left || !input) return;
        const select = form.querySelector("select");
        const submit = () => (form.requestSubmit ? form.requestSubmit() : form.submit());
        form.querySelectorAll("label, input[type=date], select").forEach((el) => el.classList.add("dw-hidden"));

        // Control segmentado Semanal | Mensual
        let monthly = false;
        if (select) {
            const segment = document.createElement("div");
            segment.className = "dw-segment";
            [...select.options].forEach((option) => {
                const button = document.createElement("button");
                button.type = "button";
                button.textContent = option.textContent.trim();
                if (select.value === option.value) { button.classList.add("is-active"); monthly = /mens|month/i.test(option.textContent + option.value); }
                button.addEventListener("click", () => {
                    if (select.value === option.value) return;
                    select.value = option.value;
                    if (/mens|month/i.test(option.textContent + option.value)) { const d = parse(input.value); input.value = iso(new Date(d.getFullYear(), d.getMonth(), 1)); }
                    submit();
                });
                segment.appendChild(button);
            });
            left.prepend(segment);
        }

        // Tarjeta de fecha o período con flechas
        const date = parse(input.value);
        const widget = document.createElement("div");
        widget.className = "date-widget";
        let face;
        if (!select) {
            face = `<strong>${String(date.getDate()).padStart(2, "0")}</strong><span>${cap(fmt(date, { weekday: "long" }))}</span><small>${cap(fmt(date, { month: "long", year: "numeric" }))}</small>`;
        } else if (monthly) {
            face = `<span class="dw-kicker">Mes</span><strong class="dw-wide">${cap(fmt(date, { month: "long" }))}</strong><small>${date.getFullYear()}</small>`;
        } else {
            const end = new Date(date); end.setDate(date.getDate() + 6);
            face = `<span class="dw-kicker">Semana</span><strong class="dw-wide">${String(date.getDate()).padStart(2, "0")} al ${String(end.getDate()).padStart(2, "0")}</strong><small>${cap(fmt(end, { month: "short", year: "numeric" }))}</small>`;
        }
        widget.innerHTML = `<button type="button" class="dw-arrow" data-step="-1" aria-label="Anterior">‹</button>
            <button type="button" class="dw-face" title="Elegir en el calendario">${face}</button>
            <button type="button" class="dw-arrow" data-step="1" aria-label="Siguiente">›</button>`;
        widget.querySelectorAll(".dw-arrow").forEach((arrow) => arrow.addEventListener("click", () => {
            const step = parseInt(arrow.dataset.step, 10);
            const d = parse(input.value);
            if (!select) d.setDate(d.getDate() + step);
            else if (monthly) { d.setDate(1); d.setMonth(d.getMonth() + step); }
            else d.setDate(d.getDate() + 7 * step);
            input.value = iso(d);
            submit();
        }));
        widget.querySelector(".dw-face").addEventListener("click", () => {
            if (input.showPicker) { try { input.showPicker(); return; } catch (e) { /* sin selector nativo */ } }
            input.focus();
        });
        (left.querySelector(".dw-segment") || form).after(widget);
        if (!select) left.prepend(widget);
    });
})();

/* GastroInsight AI · Barra del reporte: descargas a la derecha y expandir/contraer como íconos. */
(function () {
    "use strict";
    if (!/^\/reports\/(?!explorar)/.test(location.pathname) || document.body.dataset.embed === "1") return;
    const head = document.querySelector(".report-head");
    if (!head || head.querySelector(".report-tools")) return;
    const DOWN = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M7 7l5 5 5-5M7 13l5 5 5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const UP = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M7 11l5-5 5 5M7 17l5-5 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const tools = document.createElement("div");
    tools.className = "report-tools";
    head.appendChild(tools);
    const downloads = document.querySelector(".report-downloads");
    if (downloads) {
        downloads.querySelectorAll("a").forEach((a) => { a.className = "btn btn-small btn-secondary report-dl"; });
        tools.appendChild(downloads);
    }
    const controls = document.querySelector(".report-controls");
    if (controls) {
        controls.querySelectorAll("[data-all]").forEach((button) => {
            const expand = button.dataset.all === "1";
            button.className = "report-icon-btn";
            button.innerHTML = expand ? DOWN : UP;
            button.title = expand ? "Expandir todas las secciones" : "Contraer todas las secciones";
            button.setAttribute("aria-label", button.title);
        });
        tools.appendChild(controls);
    }
    head.querySelectorAll("div, p").forEach((el) => {
        if (!el.closest(".report-tools") && !el.classList.contains("page-help") && !el.textContent.trim() && !el.querySelector("a, button, img, svg")) el.remove();
    });
})();
