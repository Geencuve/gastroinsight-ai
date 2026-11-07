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
