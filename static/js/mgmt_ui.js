/* GastroInsight AI · Centro de gestión y Detectar cámaras: filtros, ventanas flotantes y ayudas. */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;

    // ---------- Ventanas flotantes propias (Agregar persona, mesa, cámara, clave) ----------
    document.addEventListener("click", (event) => {
        const opener = event.target.closest("[data-open-dialog]");
        if (opener) {
            const dialog = document.getElementById(opener.dataset.openDialog);
            if (dialog && !dialog.open) { dialog.showModal(); fillHints(dialog); }
            return;
        }
        const closer = event.target.closest("[data-close-dialog]");
        if (closer) { const dialog = closer.closest("dialog"); if (dialog) dialog.close(); return; }
        if (event.target.matches("dialog.mgmt-dialog")) event.target.close();
    });

    // ---------- Píldoras con contador + buscador (personal, mesas, cámaras) ----------
    const EXTRA = { "sin-local": "⚠️ Sin local", inactiva: "💤 Inactivas" };
    document.querySelectorAll("[data-mgmt-chips]").forEach((bar) => {
        const name = bar.dataset.mgmtChips;
        const list = document.querySelector(`[data-mgmt-list="${name}"]`);
        if (!list) return;
        const items = [...list.querySelectorAll(":scope > [data-filter]")];
        if (items.length < 2) return;
        const counts = new Map();
        items.forEach((item) => {
            const tokens = item.dataset.filter.split(" ").filter(Boolean);
            tokens.forEach((token, i) => {
                const label = i === 0 ? (item.dataset.label || token) : (EXTRA[token] || token);
                const entry = counts.get(token) || { label, n: 0 };
                entry.n += 1;
                counts.set(token, entry);
            });
        });
        if (counts.size < 2) return;
        const make = (token, label, n) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "status-chip" + (token === "*" ? " is-active" : "") + (token === "sin-local" ? " chip-warn" : "");
            chip.dataset.chip = token;
            chip.innerHTML = `${label} <b>${n}</b>`;
            bar.appendChild(chip);
        };
        make("*", "Todas", items.length);
        counts.forEach((entry, token) => make(token, entry.label, entry.n));
        bar.addEventListener("click", (event) => {
            const chip = event.target.closest("[data-chip]");
            if (!chip) return;
            bar.querySelectorAll("[data-chip]").forEach((c) => c.classList.toggle("is-active", c === chip));
            bar.dataset.active = chip.dataset.chip;
            apply(name);
        });
    });

    document.querySelectorAll("[data-mgmt-search]").forEach((input) => {
        input.addEventListener("input", () => apply(input.dataset.mgmtSearch));
    });

    function apply(name) {
        const list = document.querySelector(`[data-mgmt-list="${name}"]`);
        if (!list) return;
        const bar = document.querySelector(`[data-mgmt-chips="${name}"]`);
        const input = document.querySelector(`[data-mgmt-search="${name}"]`);
        const token = (bar && bar.dataset.active) || "*";
        const text = input ? input.value.trim().toLowerCase() : "";
        let visible = 0;
        list.querySelectorAll(":scope > [data-filter]").forEach((item) => {
            const okChip = token === "*" || item.dataset.filter.split(" ").includes(token);
            const okText = !text || (item.dataset.search || item.textContent.toLowerCase()).includes(text);
            item.hidden = !(okChip && okText);
            if (!item.hidden) visible += 1;
        });
        const empty = document.querySelector(`[data-mgmt-empty="${name}"]`);
        if (empty) empty.hidden = visible > 0;
    }

    // ---------- Descripción del rol elegido ----------
    let guide = [];
    try { guide = JSON.parse((document.getElementById("mgmt-role-guide") || {}).textContent || "[]"); } catch (e) { guide = []; }
    function roleText(key) {
        const role = guide.find((r) => r.key === key);
        return role && role.caps.length ? "Podrá: " + role.caps.join(" · ") + "." : "";
    }
    function fillHints(root) {
        root.querySelectorAll("[data-role-hint]").forEach((hint) => {
            const select = hint.closest("form").querySelector('select[name="role"]');
            if (select) { hint.textContent = roleText(select.value); hint.hidden = !hint.textContent; }
        });
        root.querySelectorAll("[data-source-hint]").forEach((hint) => {
            const select = hint.closest("form").querySelector('select[name="source_type"]');
            if (select) hint.textContent = SOURCE_HINTS[select.value] || "";
        });
        root.querySelectorAll(".mgmt-check-chips").forEach((box) => {
            const boxes = box.querySelectorAll('input[type="checkbox"]');
            if (boxes.length === 1 && box.closest("#dlg-staff") && !box.closest("form").dataset.touched) boxes[0].checked = true; // un solo local: marcado
        });
        root.querySelectorAll(".mgmt-uso").forEach((group) => syncUso(group));
    }
    const SOURCE_HINTS = {
        webcam: "Número del dispositivo: 0 = cámara integrada, 1 = segunda cámara USB.",
        ip_camera: "Dirección de la cámara, por ejemplo rtsp://usuario:clave@192.168.1.50:554/stream1",
        video_file: "Ruta de un archivo de video (.mp4) para pruebas.",
        demo: "Usa datos de demostración; la fuente puede ser cualquier texto.",
    };
    document.addEventListener("change", (event) => {
        const form = event.target.closest("form");
        if (form) form.dataset.touched = "1";
        if (event.target.matches('select[name="role"], select[name="source_type"]')) fillHints(form);
        if (event.target.matches('.mgmt-uso input[type="radio"]')) syncUso(event.target.closest(".mgmt-uso"));
    });

    // ---------- Uso de la cámara: mesa, entrada o caja ----------
    function syncUso(group) {
        const form = group.closest("form");
        const checked = group.querySelector("input:checked");
        const value = checked ? checked.value : "mesa";
        const mesa = form.querySelector("[data-uso-mesa]");
        if (mesa) mesa.hidden = value !== "mesa";
        const entrance = form.querySelector('input[name="is_entrance"]');
        const checkout = form.querySelector('input[name="is_checkout"]');
        if (entrance) entrance.checked = value === "entrada";
        if (checkout) checkout.checked = value === "caja";
        const flags = form.querySelector("[data-uso-flags]");
        if (flags) flags.hidden = true; // la elección de arriba ya las marca
        if (value !== "mesa") { const table = form.querySelector('select[name="table"]'); if (table) table.value = ""; }
    }

    // ---------- Contraseña segura ----------
    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-pass-generate]");
        if (!button) return;
        const input = button.parentElement.querySelector("input");
        const sets = ["ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnopqrstuvwxyz", "23456789", "#$%&*+?"];
        const pick = (s) => s[crypto.getRandomValues(new Uint32Array(1))[0] % s.length];
        const chars = sets.map(pick);
        while (chars.length < 12) chars.push(pick(sets.join("")));
        chars.sort(() => crypto.getRandomValues(new Uint8Array(1))[0] - 128);
        input.type = "text";
        input.value = chars.join("");
        input.select();
        button.textContent = "🎲 Otra";
    });

    // ---------- Mesas: elegir una zona existente ----------
    document.addEventListener("click", (event) => {
        const pick = event.target.closest("[data-zone-pick]");
        if (!pick) return;
        const input = pick.closest("form").querySelector('input[name="zone_name"]');
        if (input) input.value = pick.dataset.zonePick;
    });

    // ---------- Alertas: valores recomendados ----------
    const DEFAULTS = { impatience_pct: 70, impatience_minutes: 8, discomfort_ieo: 45, discomfort_minutes: 0, waiting_minutes: 20, approval_ieo: 80 };
    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-alert-defaults]");
        if (!button) return;
        const form = button.closest("form");
        Object.entries(DEFAULTS).forEach(([field, value]) => {
            const input = form.querySelector(`input[name$="-${field}"], input[name="${field}"]`);
            if (input) input.value = value;
        });
        button.textContent = "✓ Restablecidos: falta guardar";
    });

    // ---------- Detectar cámaras ----------
    const search = document.querySelector("[data-discover-search]");
    const loading = document.querySelector("[data-discover-loading]");
    if (search && loading) search.addEventListener("click", () => { loading.hidden = false; });
    const probe = document.querySelector("[data-discover-probe]");
    if (probe && loading) probe.addEventListener("submit", () => {
        loading.hidden = false;
        loading.lastChild.textContent = "Probando la conexión… espera como máximo 4 segundos.";
    });
    document.addEventListener("click", (event) => {
        const example = event.target.closest("[data-url-example]");
        if (!example) return;
        const input = document.getElementById("cam-url");
        if (!input) return;
        input.value = example.dataset.urlExample;
        input.focus();
    });

    // Con la ficha flotante de «Editar» (float.js) el contenido llega después: completar sus ayudas
    new MutationObserver(() => {
        document.querySelectorAll(".gi-modal[open] [data-role-hint]:not([data-filled])").forEach((hint) => {
            hint.dataset.filled = "1";
            fillHints(hint.closest("form"));
        });
    }).observe(document.body, { childList: true, subtree: true });
    fillHints(document);
})();
