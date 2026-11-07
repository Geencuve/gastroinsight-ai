/* GastroInsight AI · Punto de venta: grilla de platos con buscador y pedido fijo a la derecha. */
(function () {
    "use strict";
    const picker = document.querySelector(".dish-picker");
    if (!picker || document.body.dataset.embed === "1") return;
    const pickerCard = picker.closest(".card") || picker.parentElement;

    // Buscador instantáneo
    const search = document.createElement("input");
    search.type = "search";
    search.className = "pos-search";
    search.placeholder = "🔎 Buscar plato…";
    search.setAttribute("aria-label", "Buscar plato");
    picker.before(search);
    const normalize = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    search.addEventListener("input", () => {
        const query = normalize(search.value.trim());
        picker.querySelectorAll(".dish-pick").forEach((card) => {
            const name = normalize((card.querySelector(".dish-pick-name") || card).textContent);
            card.hidden = Boolean(query) && !name.includes(query);
        });
    });

    // Pedido fijo a la derecha: la primera tarjeta con la tabla de platos del pedido
    const summary = [...document.querySelectorAll("main .card")].find((card) => card !== pickerCard && !card.contains(picker) && card.querySelector("table"));
    if (summary && pickerCard) {
        const layout = document.createElement("div");
        layout.className = "pos-layout";
        pickerCard.before(layout);
        layout.appendChild(pickerCard);
        layout.appendChild(summary);
        summary.classList.add("pos-summary");
        pickerCard.classList.add("pos-menu");
    }

    // Mantener la posición al agregar o quitar platos
    const KEY = `gi-pos-scroll-${location.pathname}`;
    try {
        const saved = sessionStorage.getItem(KEY);
        if (saved) { window.scrollTo(0, parseInt(saved, 10)); sessionStorage.removeItem(KEY); }
    } catch (e) { /* sin almacenamiento */ }
    document.querySelectorAll("main form").forEach((form) => form.addEventListener("submit", () => {
        try { sessionStorage.setItem(KEY, String(window.scrollY)); } catch (e) { /* sin almacenamiento */ }
    }));
})();
