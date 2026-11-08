/* GastroInsight AI · Tutorial de la API: ejemplos con tu clave, lenguaje elegido, copiar y probar. */
(function () {
    "use strict";
    const root = document.querySelector("[data-api-tutorial]");
    if (!root) return;
    const PLACEHOLDER_KEY = "gi_TU_CLAVE";
    const originalBase = root.dataset.apiBase;
    const keyInput = root.querySelector("[data-tut-key]");
    const baseInput = root.querySelector("[data-tut-base]");
    const blocks = [...root.querySelectorAll(".tut-code code")];
    blocks.forEach((code) => { code.dataset.tpl = code.textContent; });

    // Botón «Copiar» en cada ejemplo
    root.querySelectorAll(".tut-code").forEach((box) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-small tut-copy";
        button.textContent = "📋 Copiar";
        box.appendChild(button);
        button.addEventListener("click", () => copy(box.querySelector("code").textContent, button));
    });

    function copy(text, button) {
        const done = () => { button.textContent = "✓ Copiado"; setTimeout(() => { button.textContent = "📋 Copiar"; }, 1500); };
        if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done, () => legacy(text, done)); return; }
        legacy(text, done);
    }
    function legacy(text, done) {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.cssText = "position:fixed;opacity:0";
        document.body.appendChild(area);
        area.select();
        try { document.execCommand("copy"); done(); } catch (e) { /* se puede copiar a mano */ }
        area.remove();
    }

    // Completa los ejemplos con la clave y la dirección escritas
    function base() {
        let value = (baseInput.value || originalBase).trim();
        if (!value.endsWith("/")) value += "/";
        return value;
    }
    function render() {
        const key = keyInput.value.trim() || PLACEHOLDER_KEY;
        const url = base();
        blocks.forEach((code) => { code.textContent = code.dataset.tpl.split(PLACEHOLDER_KEY).join(key).split(originalBase).join(url); });
    }
    keyInput.addEventListener("input", render);
    baseInput.addEventListener("input", render);

    // Lenguaje de los ejemplos (se recuerda en este navegador; la clave nunca se guarda)
    const langs = root.querySelector("[data-tut-langs]");
    function setLang(lang) {
        langs.querySelectorAll("[data-lang]").forEach((b) => b.classList.toggle("is-active", b.dataset.lang === lang));
        root.querySelectorAll(".tut-code").forEach((box) => { box.hidden = box.dataset.lang !== lang; });
        try { localStorage.setItem("gi-tut-lang", lang); } catch (e) { /* sin almacenamiento */ }
    }
    langs.addEventListener("click", (event) => { const b = event.target.closest("[data-lang]"); if (b) setLang(b.dataset.lang); });
    try { const saved = localStorage.getItem("gi-tut-lang"); if (saved) setLang(saved); } catch (e) { /* sin almacenamiento */ }

    // Probar ahora: GET /estado/ desde el navegador
    const tryButton = root.querySelector("[data-tut-try]");
    const result = root.querySelector("[data-tut-result]");
    tryButton.addEventListener("click", async () => {
        const key = keyInput.value.trim();
        result.hidden = false;
        result.className = "tut-result";
        if (!key) {
            result.textContent = "Primero pega tu clave en el campo «🔑 Tu clave» de arriba.";
            result.classList.add("is-error");
            keyInput.focus();
            return;
        }
        result.textContent = "Probando…";
        try {
            const response = await fetch(base() + "estado/", { headers: { Authorization: `Bearer ${key}` } });
            const data = await response.json().catch(() => ({}));
            result.textContent = `${response.status} → ${JSON.stringify(data, null, 1)}`;
            result.classList.add(response.ok ? "is-ok" : "is-error");
            if (response.ok) result.textContent += `\n\n✅ Conexión correcta con «${data.local}». Ya puedes seguir con el paso 3 o 4.`;
        } catch (error) {
            result.textContent = "No se pudo conectar con esa dirección. Revisa el campo «🌐 Dirección del servidor» (desde el navegador debe ser la misma dirección de esta página).";
            result.classList.add("is-error");
        }
    });

    // «Ir a Integraciones» abre directamente esa pestaña
    const goto = root.querySelector("[data-tut-goto-integrations]");
    if (goto) goto.addEventListener("click", () => {
        try { sessionStorage.setItem("gi-tab-/gestion/-gestion", "4"); } catch (e) { /* sin almacenamiento */ }
    });
})();
