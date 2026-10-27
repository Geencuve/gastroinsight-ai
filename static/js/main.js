document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("assistant-widget-toggle");
    const panel = document.getElementById("assistant-widget-panel");
    const close = document.getElementById("assistant-widget-close");
    const form = document.getElementById("assistant-widget-form");
    const input = document.getElementById("assistant-widget-input");
    const messages = document.getElementById("assistant-widget-messages");
    const error = document.getElementById("assistant-widget-error");

    // Páginas sin widget (por ejemplo, sin sesión iniciada): no hay nada que hacer.
    if (!form || !input || !messages) {
        return;
    }

    const storageKey = `gastroinsight:staff-chat:${form.dataset.userId}`;
    let conversationId = null;
    let sending = false;

    function appendMessage(author, content, links) {
        const bubble = document.createElement("div");
        bubble.className = "widget-bubble " + (author === "Tú" ? "widget-bubble-user" : "widget-bubble-assistant");
        bubble.textContent = content;
        if (links && links.length) {
            const wrap = document.createElement("div");
            wrap.className = "chat-links";
            links.forEach((link) => {
                const anchor = document.createElement("a");
                anchor.href = link.url;
                anchor.className = "btn btn-small";
                anchor.textContent = `${link.label} →`;
                wrap.appendChild(anchor);
            });
            bubble.appendChild(wrap);
        }
        messages.appendChild(bubble);
        messages.scrollTop = messages.scrollHeight;
    }

    function showError(text) {
        if (!error) return;
        error.textContent = text;
        error.hidden = false;
    }

    async function restoreConversation() {
        const savedId = sessionStorage.getItem(storageKey);
        if (!savedId || !/^\d+$/.test(savedId)) return;
        try {
            const historyUrl = form.dataset.historyUrl.replace(/0\/$/, `${savedId}/`);
            const response = await fetch(historyUrl, { credentials: "same-origin" });
            if (!response.ok) throw new Error("No se pudo recuperar la conversación.");
            const result = await response.json();
            conversationId = result.conversation_id;
            messages.replaceChildren();
            result.messages.forEach((item) => {
                appendMessage(item.sender === "USER" ? "Tú" : "Asistente", item.content, item.links);
            });
        } catch (err) {
            conversationId = null;
            sessionStorage.removeItem(storageKey);
            showError(err.message);
        }
    }

    restoreConversation();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (sending || !input.value.trim()) return;
        sending = true;
        const button = form.querySelector('button[type="submit"]');
        button.disabled = true;
        if (error) error.hidden = true;

        const data = new FormData(form);
        if (conversationId !== null) data.set("conversation_id", String(conversationId));

        try {
            const response = await fetch(form.dataset.url, { method: "POST", body: data, credentials: "same-origin" });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "No se pudo enviar la consulta.");
            conversationId = result.conversation_id;
            sessionStorage.setItem(storageKey, String(conversationId));
            appendMessage("Tú", result.user_message);
            appendMessage("Asistente", result.assistant_message, result.links);
            input.value = "";
        } catch (err) {
            showError(err.message);
        } finally {
            sending = false;
            button.disabled = false;
        }
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    if (!toggle || !panel || !close) return;

    function setOpen(isOpen) {
        panel.hidden = !isOpen;
        toggle.setAttribute("aria-expanded", String(isOpen));
        (isOpen ? input : toggle).focus();
    }

    toggle.addEventListener("click", () => setOpen(panel.hidden));
    close.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) setOpen(false);
    });
});
