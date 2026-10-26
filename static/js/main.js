document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("assistant-widget-toggle");
    const panel = document.getElementById("assistant-widget-panel");
    const close = document.getElementById("assistant-widget-close");
    const form = document.getElementById("assistant-widget-form");
    const input = document.getElementById("assistant-widget-input");
    const messages = document.getElementById("assistant-widget-messages");
    const error = document.getElementById("assistant-widget-error");
    const storageKey = `gastroinsight:staff-chat:${form.dataset.userId}`;
    let conversationId = null;
    let sending = false;

    function appendMessage(author, content) {
        const paragraph = document.createElement("p");
        const label = document.createElement("strong");

        label.textContent = `${author}: `;
        paragraph.appendChild(label);
        paragraph.appendChild(document.createTextNode(content));
        messages.appendChild(paragraph);
        messages.scrollTop = messages.scrollHeight;
    }
        async function restoreConversation() {
            const savedId = sessionStorage.getItem(storageKey);

            if (!savedId || !/^\d+$/.test(savedId)) {
                return;
            }

            const button = form.querySelector('button[type="submit"]');
            button.disabled = true;

            try {
                const historyUrl = form.dataset.historyUrl.replace(
                    /0\/$/,
                    `${savedId}/`
                );

                const response = await fetch(historyUrl, {
                    credentials: "same-origin",
                });

                if (!response.ok) {
                    throw new Error("No se pudo recuperar la conversación.");
                }

                const result = await response.json();
                conversationId = result.conversation_id;
                messages.replaceChildren();

                if (result.messages.length === 0) {
                    appendMessage("Sistema", "Esta conversación aún no tiene mensajes.");
                } else {
                    result.messages.forEach((item) => {
                        const author = item.sender === "USER" ? "Tú" : "Asistente";
                        appendMessage(author, item.content);
                    });
                }
            } catch (err) {
                conversationId = null;
                sessionStorage.removeItem(storageKey);
                error.textContent = err.message;
                error.hidden = false;
            } finally {
                button.disabled = false;
            }
        }

        restoreConversation();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (sending || !input.value.trim()) {
            return;
        }

        sending = true;
        const button = form.querySelector('button[type="submit"]');
        button.disabled = true;
        error.hidden = true;

        const data = new FormData(form);

        if (conversationId !== null) {
            data.set("conversation_id", String(conversationId));
        }

        try {
            const response = await fetch(form.dataset.url, {
                method: "POST",
                body: data,
                credentials: "same-origin",
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || "No se pudo enviar la consulta.");
            }

            conversationId = result.conversation_id;
            sessionStorage.setItem(storageKey, String(conversationId));
            appendMessage("Tú", result.user_message);
            appendMessage("Asistente", result.assistant_message);
            input.value = "";
        } catch (err) {
            error.textContent = err.message;
            error.hidden = false;
        } finally {
            sending = false;
            button.disabled = false;
        }
    });
    
    if (!toggle || !panel || !close) {
        return;
    }

    function setOpen(isOpen) {
        panel.hidden = !isOpen;
        toggle.setAttribute("aria-expanded", String(isOpen));

        if (isOpen) {
            close.focus();
        } else {
            toggle.focus();
        }
    }

    toggle.addEventListener("click", () => {
        setOpen(panel.hidden);
    });

    close.addEventListener("click", () => {
        setOpen(false);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) {
            setOpen(false);
        }
    });
});