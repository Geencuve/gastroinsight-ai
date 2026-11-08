/* GastroInsight AI · Centro de gestión: advertencias de seguridad con filtros y ficha de solución. */
(function () {
    "use strict";
    const panel = document.getElementById("sec-panel");
    if (!panel || document.body.dataset.embed === "1") return;
    const items = [...panel.querySelectorAll(".sec-item")];
    const grid = panel.querySelector(".sec-grid");
    const chips = panel.querySelector(".sec-chips");
    const toggle = panel.querySelector(".sec-toggle");
    const KEY = "gi-sec-collapsed";

    // Píldoras con contador que filtran al instante
    const LEVELS = [["all", "Todas"], ["danger", "🔴 Críticas"], ["warning", "🟠 Importantes"], ["info", "🔵 Informativas"]];
    LEVELS.forEach(([level, label]) => {
        const count = level === "all" ? items.length : items.filter((i) => i.dataset.secLevel === level).length;
        if (!count) return;
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "status-chip" + (level === "all" ? " is-active" : "");
        chip.dataset.secFilter = level;
        chip.innerHTML = `${label} <b>${count}</b>`;
        chips.appendChild(chip);
    });
    chips.addEventListener("click", (event) => {
        const chip = event.target.closest("[data-sec-filter]");
        if (!chip) return;
        chips.querySelectorAll(".status-chip").forEach((c) => c.classList.toggle("is-active", c === chip));
        const level = chip.dataset.secFilter;
        items.forEach((i) => { i.hidden = level !== "all" && i.dataset.secLevel !== level; });
        setCollapsed(false);
    });

    // Plegar / desplegar (se recuerda en este navegador)
    function setCollapsed(collapsed) {
        grid.hidden = collapsed;
        panel.classList.toggle("is-collapsed", collapsed);
        toggle.textContent = collapsed ? "Mostrar ▾" : "Ocultar ▴";
        toggle.setAttribute("aria-expanded", String(!collapsed));
        try { localStorage.setItem(KEY, collapsed ? "1" : "0"); } catch (e) { /* sin almacenamiento */ }
    }
    toggle.addEventListener("click", () => setCollapsed(!grid.hidden));
    try { if (localStorage.getItem(KEY) === "1") setCollapsed(true); } catch (e) { /* sin almacenamiento */ }

    // Ficha flotante con la solución sugerida
    const dialog = document.createElement("dialog");
    dialog.className = "gi-modal sec-modal";
    dialog.innerHTML = '<div class="gi-modal-bar"><strong>🛡️ Cómo resolverlo</strong><button type="button" class="gi-modal-close" aria-label="Cerrar">✕</button></div><div class="gi-modal-body"></div>';
    document.body.appendChild(dialog);
    const body = dialog.querySelector(".gi-modal-body");
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog || event.target.closest(".gi-modal-close, [data-sec-close]")) { dialog.close(); return; }
        // Los enlaces cierran esta ficha; si corresponde, la ventana flotante de la plataforma abre el destino
        if (event.target.closest("a[href]")) { dialog.close(); return; }
        const copy = event.target.closest("[data-sec-copy]");
        if (copy) {
            const text = copy.parentElement.querySelector("code").textContent;
            const done = () => { copy.textContent = "✓ Copiado"; setTimeout(() => { copy.textContent = "📋 Copiar"; }, 1600); };
            if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, () => fallback(text, done));
            else fallback(text, done);
            return;
        }
        const tab = event.target.closest("[data-sec-tab]");
        if (tab) { dialog.close(); goToTab(parseInt(tab.dataset.secTab, 10), tab.dataset.secMark); }
    });

    function fallback(text, done) {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        dialog.appendChild(area);
        area.select();
        try { document.execCommand("copy"); done(); } catch (e) { /* el usuario puede copiar a mano */ }
        area.remove();
    }

    function goToTab(index, mark) {
        const tabs = document.querySelector('[data-tabs="gestion"]');
        if (!tabs) return;
        const button = tabs.querySelectorAll(":scope > .tab-bar [data-tab-button]")[index];
        if (button) button.click();
        tabs.scrollIntoView({ behavior: "smooth", block: "start" });
        if (mark === "sin-local") {
            const rows = [...tabs.querySelectorAll("tbody tr")].filter((tr) => tr.querySelector(".table-alert") && !tr.classList.contains("muted"));
            rows.forEach((tr) => {
                tr.classList.remove("sec-flash");
                void tr.offsetWidth; // reinicia la animación
                tr.classList.add("sec-flash");
            });
            const box = rows[0] && rows[0].closest(".mgmt-scroll");
            if (box) box.scrollTop += rows[0].getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 3;
        }
    }

    grid.addEventListener("click", (event) => {
        const item = event.target.closest(".sec-item");
        if (!item) return;
        const tpl = document.getElementById(`sec-fix-${item.dataset.secIndex}`);
        if (!tpl) return;
        body.replaceChildren(tpl.content.cloneNode(true));
        dialog.showModal();
    });
})();
