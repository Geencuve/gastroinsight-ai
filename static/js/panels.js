/* GastroInsight AI · Recuadro de fondo para Salón y Mis alertas (igual que Pedidos). */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const target = location.pathname === "/sala/" ? document.getElementById("floor-board")
        : location.pathname === "/garzon/" ? document.getElementById("waiter-panel") : null;
    if (!target || target.parentElement.classList.contains("page-panel")) return;
    const panel = document.createElement("section");
    panel.className = "card page-panel";
    target.before(panel);
    panel.appendChild(target);
})();
