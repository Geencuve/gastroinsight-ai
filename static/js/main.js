document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("assistant-widget-toggle");
    const panel = document.getElementById("assistant-widget-panel");
    const close = document.getElementById("assistant-widget-close");
    const form = document.getElementById("assistant-widget-form");
    const input = document.getElementById("assistant-widget-input");
    const messages = document.getElementById("assistant-widget-messages");
    const error = document.getElementById("assistant-widget-error");
    const empty = document.getElementById("aw-empty");
    if (!form || !input || !messages) return;

    const send = form.querySelector(".composer-send");
    const storageKey = `gastroinsight:staff-chat:${form.dataset.userId}`;
    let conversationId = null;
    let sending = false;

    const el = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };

    function appendMessage(isUser, content, extra = {}) {
        if (empty) empty.hidden = true;
        const bubble = el("div", "widget-bubble " + (isUser ? "widget-bubble-user" : "widget-bubble-assistant"), content);
        if (!isUser && extra.metrics && extra.metrics.length) {
            const wrap = el("div", "chat-metrics");
            extra.metrics.forEach((m) => {
                const box = el("div", "chat-metric");
                box.appendChild(el("span", "", m.label));
                box.appendChild(el("strong", m.tone ? `tone-${m.tone}` : "", m.value));
                wrap.appendChild(box);
            });
            bubble.appendChild(wrap);
        }
        if (!isUser && extra.bars && extra.bars.length) {
            const wrap = el("div", "chat-bars");
            extra.bars.forEach((b) => {
                const row = el("div", "chat-bar");
                row.appendChild(el("span", "chat-bar-label", b.label));
                const track = el("span", "chat-bar-track");
                const fill = el("span", "chat-bar-fill");
                fill.style.width = `${b.pct}%`;
                track.appendChild(fill);
                row.appendChild(track);
                row.appendChild(el("span", "chat-bar-value", b.value));
                wrap.appendChild(row);
            });
            bubble.appendChild(wrap);
        }
        if (!isUser && extra.thumbs && extra.thumbs.length && window.GIThumb) {
            const wrap = el("div", "chat-thumbs");
            wrap.innerHTML = extra.thumbs.map(window.GIThumb.mini).join("");
            bubble.appendChild(wrap);
        }
        if (!isUser && extra.links && extra.links.length) {
            const wrap = el("div", "chat-links");
            extra.links.forEach((link) => {
                const anchor = el("a", "btn btn-small", `${link.label} →`);
                anchor.href = link.url;
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

    const grow = () => {
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 140) + "px";
        if (send) send.disabled = !input.value.trim() || sending;
    };

    async function restoreConversation() {
        const savedId = sessionStorage.getItem(storageKey);
        if (!savedId || !/^\d+$/.test(savedId)) return;
        try {
            const historyUrl = form.dataset.historyUrl.replace(/0\/$/, `${savedId}/`);
            const response = await fetch(historyUrl, { credentials: "same-origin" });
            if (!response.ok) throw new Error("No se pudo recuperar la conversación.");
            const result = await response.json();
            conversationId = result.conversation_id;
            result.messages.forEach((item) => appendMessage(item.sender === "USER", item.content));
        } catch (err) {
            conversationId = null;
            sessionStorage.removeItem(storageKey);
        }
    }

    async function submit() {
        if (sending || !input.value.trim()) return;
        sending = true;
        grow();
        if (error) error.hidden = true;
        const data = new FormData(form);
        if (conversationId !== null) data.set("conversation_id", String(conversationId));
        const question = input.value.trim();
        appendMessage(true, question);
        input.value = "";
        grow();
        try {
            const response = await fetch(form.dataset.url, { method: "POST", body: data, credentials: "same-origin" });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "No se pudo enviar la consulta.");
            conversationId = result.conversation_id;
            sessionStorage.setItem(storageKey, String(conversationId));
            appendMessage(false, result.assistant_message, result);
        } catch (err) {
            showError(err.message);
        } finally {
            sending = false;
            grow();
        }
    }

    restoreConversation();
    form.addEventListener("submit", (event) => { event.preventDefault(); submit(); });
    input.addEventListener("input", grow);
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
    });
    document.querySelectorAll("[data-aw-prompt]").forEach((chip) => {
        chip.addEventListener("click", () => { input.value = chip.dataset.awPrompt; submit(); });
    });

    if (!toggle || !panel || !close) return;
    function setOpen(isOpen) {
        panel.hidden = !isOpen;
        toggle.setAttribute("aria-expanded", String(isOpen));
        toggle.hidden = isOpen;
        (isOpen ? input : toggle).focus();
    }
    toggle.addEventListener("click", () => setOpen(true));
    close.addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) setOpen(false);
    });
});
