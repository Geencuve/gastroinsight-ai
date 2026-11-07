/* GastroInsight AI · Interfaz de consultas de Sazón: preguntas de seguimiento, autocompletado,
   historial con la flecha ↑ y botón para copiar respuestas. */
(function () {
    "use strict";
    let prompts = [];
    try { prompts = JSON.parse((document.getElementById("gi-sazon-prompts") || {}).textContent || "[]"); } catch (e) { prompts = []; }
    const HISTORY = "gi-sazon-history";
    const strip = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

    function send(container, text) {
        const area = container && container.querySelector("textarea[name=message]");
        if (!area || !area.form) return;
        area.value = text;
        area.dispatchEvent(new Event("input", { bubbles: true }));
        if (area.form.requestSubmit) area.form.requestSubmit(); else area.form.submit();
    }

    document.addEventListener("click", (event) => {
        const chip = event.target.closest(".followup-chip");
        if (chip) {
            event.preventDefault();
            send(chip.closest("form, .assistant-widget, .assistant-shell, main") || document, chip.dataset.prompt);
            return;
        }
        const copy = event.target.closest(".sazon-copy");
        if (copy) {
            const bubble = copy.closest(".bubble, .chat-bubble, .message, article") || copy.parentElement;
            const text = (bubble.querySelector(".bubble-text, p") || bubble).innerText.trim();
            navigator.clipboard && navigator.clipboard.writeText(text).then(() => { copy.textContent = "✓ Copiado"; setTimeout(() => { copy.textContent = "📋 Copiar"; }, 1500); });
        }
    });

    function attach(area) {
        if (area.dataset.sazonPlus) return;
        area.dataset.sazonPlus = "1";
        const list = document.createElement("ul");
        list.className = "sazon-suggest";
        list.hidden = true;
        list.setAttribute("role", "listbox");
        area.parentElement.style.position = "relative";
        area.parentElement.appendChild(list);
        let index = -1, historyIndex = -1;

        const close = () => { list.hidden = true; index = -1; };
        const pick = (text) => { area.value = text; close(); area.focus(); };
        function render() {
            const query = strip(area.value.trim());
            if (query.length < 2) { close(); return; }
            const words = query.split(/\s+/);
            const matches = prompts.filter((p) => words.every((w) => strip(p.prompt + " " + p.label).includes(w))).slice(0, 6);
            if (!matches.length) { close(); return; }
            list.innerHTML = "";
            matches.forEach((p) => {
                const item = document.createElement("li");
                item.setAttribute("role", "option");
                item.textContent = p.prompt;
                item.addEventListener("mousedown", (e) => { e.preventDefault(); pick(p.prompt); });
                list.appendChild(item);
            });
            index = -1;
            list.hidden = false;
        }
        area.addEventListener("input", render);
        area.addEventListener("blur", () => setTimeout(close, 120));
        area.addEventListener("keydown", (event) => {
            const items = [...list.querySelectorAll("li")];
            if (!list.hidden && items.length && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
                event.preventDefault();
                index = (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
                items.forEach((li, i) => li.classList.toggle("is-active", i === index));
                return;
            }
            if (!list.hidden && index >= 0 && event.key === "Enter") { event.preventDefault(); pick(items[index].textContent); return; }
            if (event.key === "Escape") { close(); return; }
            if (event.key === "ArrowUp" && !area.value.trim()) {
                let history = [];
                try { history = JSON.parse(sessionStorage.getItem(HISTORY) || "[]"); } catch (e) { history = []; }
                if (history.length) { historyIndex = Math.min(history.length - 1, historyIndex + 1); area.value = history[history.length - 1 - historyIndex]; event.preventDefault(); }
            }
        });
        if (area.form) area.form.addEventListener("submit", () => {
            const text = area.value.trim();
            if (!text) return;
            let history = [];
            try { history = JSON.parse(sessionStorage.getItem(HISTORY) || "[]"); } catch (e) { history = []; }
            history.push(text);
            try { sessionStorage.setItem(HISTORY, JSON.stringify(history.slice(-30))); } catch (e) { /* sin almacenamiento */ }
            historyIndex = -1;
            close();
        });
    }
    document.querySelectorAll("textarea[name=message]").forEach(attach);
})();
