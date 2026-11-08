/* GastroInsight AI · Visión IA: mosaicos de resumen de las cámaras. */
(function () {
    "use strict";
    const grid = document.getElementById("thumb-grid");
    if (location.pathname !== "/vision/" || !grid || document.body.dataset.embed === "1") return;
    const summary = document.createElement("div");
    summary.className = "orders-summary vision-summary";
    grid.before(summary);
    const tile = (icon, value, label) => `<div class="mini-kpi"><span class="mini-kpi-icon">${icon}</span><strong>${value}</strong><span>${label}</span></div>`;
    async function refresh() {
        try {
            const response = await fetch(grid.dataset.url, { credentials: "same-origin" });
            if (!response.ok) return;
            const cameras = (await response.json()).cameras || [];
            const live = cameras.filter((c) => c.live);
            const ieos = live.map((c) => c.ieo).filter((v) => v !== null && v !== undefined);
            summary.innerHTML = [
                tile("📷", cameras.length, "Cámaras"),
                tile("🟢", live.length, "En vivo"),
                tile("📊", ieos.length ? Math.round(ieos.reduce((a, b) => a + b, 0) / ieos.length) : "—", "IEO promedio"),
                tile("🚶", cameras.filter((c) => c.is_entrance).length, "De entrada"),
                tile("💵", cameras.filter((c) => c.is_checkout).length, "De caja"),
            ].join("");
        } catch (e) { /* se reintenta */ }
    }
    refresh();
    setInterval(refresh, 10000);
})();
