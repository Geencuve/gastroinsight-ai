/* GastroInsight AI · Caja: recuadro de fondo, indicadores centrados, estado vacío y pagos recientes en tarjetas. */
(function () {
    "use strict";
    if (location.pathname !== "/caja/" || document.body.dataset.embed === "1") return;
    const main = document.querySelector("main");
    if (!main) return;
    const clp = (value) => "$" + Math.round(value).toLocaleString("es-CL");
    const grid = main.querySelector(".cashier-grid");
    const recent = main.querySelector(".recent-paid");
    const live = main.querySelector(".checkout-live");

    // Montos de los pagos recientes en pesos chilenos
    let paidCount = 0;
    let paidTotal = 0;
    if (recent) {
        recent.querySelectorAll(".setting-row").forEach((row) => {
            paidCount += 1;
            row.classList.add("paid-card");
            const small = row.querySelector("small");
            if (!small) return;
            small.innerHTML = small.innerHTML.replace(/(\d{3,})(?:[.,]\d{2})?(?=\s|$|<|·)/, (match, digits) => {
                paidTotal += parseInt(digits, 10);
                return clp(parseInt(digits, 10));
            });
        });
    }

    // Estado vacío
    const cards = grid ? [...grid.children].filter((el) => !el.matches("p, .muted")) : [];
    if (grid && !cards.length) {
        grid.innerHTML = '<div class="cash-empty"><span>✅</span><strong>Sin cuentas pendientes</strong><small>Cuando una mesa tenga pedidos por cobrar, aparecerá aquí con su termómetro de experiencia.</small></div>';
    }

    // Indicadores centrados
    const tiles = [["🧾", cards.length, "Mesas por cobrar", ""], ["✅", paidCount, "Pagados en la última hora", paidCount ? clp(paidTotal) : ""]];
    if (live) {
        const ieo = (live.querySelector(".checkout-ieo") || {}).textContent;
        tiles.push(["🎥", ieo ? ieo.trim() : "—", "IEO en caja ahora", ""]);
    }
    const summary = document.createElement("div");
    summary.className = "orders-summary";
    summary.innerHTML = tiles.map(([icon, value, label, note]) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span>${note ? `<small>${note}</small>` : ""}</div>`).join("");

    // Recuadro de fondo con todo el contenido de la caja
    const panel = document.createElement("section");
    panel.className = "card page-panel cash-panel";
    const first = live || grid || recent;
    if (!first) return;
    first.before(panel);
    panel.appendChild(summary);
    [live, grid, recent].forEach((el) => { if (el) panel.appendChild(el); });
})();
