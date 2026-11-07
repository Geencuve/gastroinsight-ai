/* GastroInsight AI · Punto de venta: buscador, pedido fijo y ventana flotante para agregar platos sin recargar. */
(function () {
    "use strict";
    const picker = document.querySelector(".dish-picker");
    if (!picker || document.body.dataset.embed === "1") return;
    const pickerCard = picker.closest(".card") || picker.parentElement;
    const normalize = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const pathOf = (form) => new URL(form.getAttribute("action") || location.pathname, location.href).pathname;
    const isSummaryCard = (card) => card !== pickerCard && !card.contains(picker) && card.querySelector("table");

    // Buscador instantáneo
    const search = document.createElement("input");
    search.type = "search";
    search.className = "pos-search";
    search.placeholder = "🔎 Buscar plato…";
    search.setAttribute("aria-label", "Buscar plato");
    picker.before(search);
    search.addEventListener("input", () => {
        const query = normalize(search.value.trim());
        picker.querySelectorAll(".dish-pick").forEach((card) => {
            card.hidden = Boolean(query) && !normalize((card.querySelector(".dish-pick-name") || card).textContent).includes(query);
        });
    });

    // Pedido fijo a la derecha
    let summary = [...document.querySelectorAll("main .card")].find(isSummaryCard);
    if (summary && pickerCard) {
        const layout = document.createElement("div");
        layout.className = "pos-layout";
        pickerCard.before(layout);
        layout.appendChild(pickerCard);
        layout.appendChild(summary);
        summary.classList.add("pos-summary");
        pickerCard.classList.add("pos-menu");
    }

    // Aviso breve
    function notify(text, bad) {
        const toast = document.createElement("div");
        toast.className = "pos-toast" + (bad ? " is-bad" : "");
        toast.textContent = text;
        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add("is-leaving"), 2200);
        setTimeout(() => toast.remove(), 2600);
    }

    // Envía un formulario sin recargar y refresca el pedido de la derecha
    async function sendWithoutReload(form, submitter) {
        const response = await fetch(form.action || location.href, {
            method: "POST", body: new FormData(form, submitter), credentials: "same-origin",
            headers: { "X-Requested-With": "fetch" },
        });
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        const fresh = [...doc.querySelectorAll("main .card")].find((card) => !card.querySelector(".dish-picker") && card.querySelector("table"));
        if (fresh && summary) {
            summary.innerHTML = fresh.innerHTML;
            wireSummary();
        }
        const error = doc.querySelector(".alert-error, .messages .error, .alert-danger");
        return { ok: response.ok && !error, message: error ? error.textContent.trim() : "" };
    }

    function wireSummary() {
        if (!summary) return;
        summary.querySelectorAll("form").forEach((form) => {
            if (!/\/items\//.test(pathOf(form))) return;
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const result = await sendWithoutReload(form, event.submitter);
                notify(result.ok ? "✓ Pedido actualizado" : result.message || "No se pudo actualizar el pedido", !result.ok);
            });
        });
    }
    wireSummary();

    // Ventana flotante para agregar un plato
    const addForm = [...document.querySelectorAll("main form")].find((form) => /\/items\/add\/?$/.test(pathOf(form)));
    if (!addForm) return;
    const quantityInput = addForm.querySelector("input[name=quantity]");
    const sheet = document.createElement("dialog");
    sheet.className = "gi-modal pos-sheet";
    sheet.innerHTML = `<div class="gi-modal-bar"><strong>Agregar al pedido</strong><button type="button" class="gi-modal-close" aria-label="Cerrar">✕</button></div>
        <div class="pos-sheet-body"><div class="pos-sheet-photo"></div><div><h3></h3><p class="pos-sheet-price"></p>
        <div class="pos-stepper"><button type="button" data-step="-1" aria-label="Menos">−</button><span>1</span><button type="button" data-step="1" aria-label="Más">+</button></div>
        <button type="button" class="btn btn-primary pos-sheet-add">Agregar al pedido</button></div></div>`;
    document.body.appendChild(sheet);
    const count = sheet.querySelector(".pos-stepper span");
    sheet.querySelector(".gi-modal-close").addEventListener("click", () => sheet.close());
    sheet.addEventListener("click", (event) => { if (event.target === sheet) sheet.close(); });
    sheet.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
        count.textContent = String(Math.max(1, Math.min(50, parseInt(count.textContent, 10) + parseInt(b.dataset.step, 10))));
    }));

    let currentName = "";
    picker.addEventListener("click", (event) => {
        const card = event.target.closest(".dish-pick");
        if (!card) return;
        // Evita que la selección original desplace la página hasta el formulario
        const original = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function () {};
        setTimeout(() => { Element.prototype.scrollIntoView = original; }, 120);
        setTimeout(() => {
            currentName = (card.querySelector(".dish-pick-name") || card).textContent.trim();
            const image = card.querySelector("img");
            sheet.querySelector(".pos-sheet-photo").innerHTML = image ? `<img src="${image.src}" alt="">` : (card.querySelector(".dish-pick-ph") || {}).outerHTML || "";
            sheet.querySelector("h3").textContent = currentName;
            sheet.querySelector(".pos-sheet-price").textContent = (card.querySelector(".dish-pick-price") || {}).textContent || "";
            count.textContent = "1";
            sheet.showModal();
        }, 30);
    }, true);

    sheet.querySelector(".pos-sheet-add").addEventListener("click", async () => {
        if (quantityInput) quantityInput.value = count.textContent;
        const button = sheet.querySelector(".pos-sheet-add");
        button.disabled = true;
        try {
            const result = await sendWithoutReload(addForm);
            notify(result.ok ? `✓ ${count.textContent} × ${currentName} agregado` : result.message || "No se pudo agregar el plato", !result.ok);
            if (result.ok) sheet.close();
        } catch (error) {
            addForm.submit();
        } finally {
            button.disabled = false;
        }
    });
})();
