/* GastroInsight AI · Ventanas flotantes: las acciones secundarias se abren sobre la pantalla actual. */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const PATTERNS = [
        /\/create\/$/,
        /^\/gestion\/personal\/\d+\/(qr\/)?$/,
        /^\/caja\/boleta\/\d+\/$/,
        /^\/garzon\/conectar\/$/,
        /^\/supervisor\/journey\/\d+\/$/,
    ];
    const dialog = document.createElement("dialog");
    dialog.className = "gi-modal";
    dialog.innerHTML = '<div class="gi-modal-bar"><strong></strong><button type="button" class="gi-modal-close" aria-label="Cerrar">✕</button></div><div class="gi-modal-body"></div>';
    document.body.appendChild(dialog);
    const body = dialog.querySelector(".gi-modal-body");
    const title = dialog.querySelector("strong");
    dialog.querySelector(".gi-modal-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

    function extract(html) {
        const doc = new DOMParser().parseFromString(html, "text/html");
        const main = doc.querySelector("main");
        if (!main) return null;
        main.querySelectorAll("script, .page-help, .page-help-toggle").forEach((el) => el.remove());
        const heading = main.querySelector("h1");
        const text = heading ? heading.textContent.trim() : "";
        if (heading) (heading.closest(".page-header") || heading).remove();
        main.querySelectorAll('a[href]').forEach((a) => {
            if (/^(←|Volver|Cancelar)/.test(a.textContent.trim())) a.remove();
        });
        return { title: text, html: main.innerHTML };
    }

    function show(content, url) {
        title.textContent = content.title;
        body.innerHTML = content.html;
        body.dataset.url = url;
        body.querySelectorAll("form").forEach((form) => form.addEventListener("submit", (event) => submit(event, form)));
        if (!dialog.open) dialog.showModal();
    }

    async function open(url) {
        try {
            const response = await fetch(url, { credentials: "same-origin" });
            const requested = new URL(url, location.href).pathname;
            if (!response.ok || new URL(response.url).pathname !== requested) { location.href = url; return; }
            const content = extract(await response.text());
            if (!content) { location.href = url; return; }
            show(content, url);
        } catch (error) {
            location.href = url;
        }
    }

    async function submit(event, form) {
        if ((form.method || "get").toLowerCase() !== "post") return;
        event.preventDefault();
        const target = form.getAttribute("action") || body.dataset.url;
        try {
            const response = await fetch(target, { method: "POST", body: new FormData(form, event.submitter), credentials: "same-origin" });
            const finalPath = new URL(response.url).pathname;
            const html = await response.text();
            if (response.ok && finalPath === new URL(target, location.href).pathname) {
                const content = extract(html);
                if (content) { show(content, body.dataset.url); return; }
            }
            dialog.close();
            if (finalPath === location.pathname) location.reload(); else location.href = response.url;
        } catch (error) {
            form.submit();
        }
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[href]");
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || link.target === "_blank") return;
        if (link.closest(".app-sidebar")) return;
        const url = new URL(link.href, location.href);
        if (url.origin !== location.origin || !PATTERNS.some((p) => p.test(url.pathname))) return;
        event.preventDefault();
        open(url.pathname + url.search);
    });

    // Botón «↑ Arriba» en páginas largas
    const top = document.createElement("button");
    top.type = "button";
    top.className = "gi-to-top";
    top.textContent = "↑ Arriba";
    top.hidden = true;
    document.body.appendChild(top);
    top.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
    window.addEventListener("scroll", () => { top.hidden = window.scrollY < 600; }, { passive: true });
})();
