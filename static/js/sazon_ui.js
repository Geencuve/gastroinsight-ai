/* GastroInsight AI · Sazón en toda la plataforma: alertas urgentes, preguntas por pantalla, sugerencias y avisos. */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    const widget = document.getElementById("assistant-widget");
    const toggle = document.getElementById("assistant-widget-toggle");
    const area = document.getElementById("assistant-widget-input");
    const path = location.pathname;
    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    const Q = {
        mesas: ["📡 Mesas ahora", "¿Cómo están las mesas ahora?"],
        ventas: ["💰 Ventas de hoy", "¿Cuánto vendimos hoy?"],
        semana: ["📈 Ventas de la semana", "¿Cómo van las ventas esta semana?"],
        promo: ["📣 Qué promociono", "¿Qué debería promocionar?"],
        platos: ["🍽️ Platos más vendidos", "¿Qué platos se venden más?"],
        ticket: ["🧾 Ticket promedio", "¿Cuál es el ticket promedio?"],
        pagos: ["💳 Medios de pago", "¿Qué medios de pago usan más?"],
        dia: ["📅 Día más flojo", "¿Qué día vendo menos?"],
        etapa: ["🛤️ Etapa más débil", "¿En qué etapa cae la experiencia?"],
        sazon: ["🧠 Cómo funciona Sazón", "¿Cómo funciona Sazón?"],
    };
    const CONTEXT = [
        [/^\/$/, "el inicio", ["ventas", "promo", "etapa"]],
        [/^\/sala\//, "el salón", ["mesas", "etapa"]],
        [/^\/garzon\//, "tus mesas", ["mesas", "etapa"]],
        [/^\/sales\//, "los pedidos", ["platos", "ticket", "pagos"]],
        [/^\/caja\//, "la caja", ["ventas", "pagos", "ticket"]],
        [/^\/(cocina|barra)\//, "la cocina", ["platos"]],
        [/^\/analytics\//, "el dashboard", ["semana", "dia", "promo"]],
        [/^\/reports\//, "los reportes", ["semana", "platos", "dia"]],
        [/^\/supervisor\/journey/, "el journey", ["etapa", "mesas"]],
        [/^\/supervisor\//, "la supervisión", ["mesas", "etapa", "ventas"]],
        [/^\/(vision|ai)\//, "la visión IA", ["mesas", "sazon"]],
        [/^\/promociones\//, "las promociones", ["promo", "dia", "platos"]],
        [/^\/gestion\//, "la gestión", ["sazon", "ventas"]],
    ];
    const context = CONTEXT.find(([pattern]) => pattern.test(path));
    const contextName = context ? context[1] : "esta pantalla";
    const contextQs = (context ? context[2] : ["ventas", "promo"]).map((k) => Q[k]);

    function open() {
        if (toggle && toggle.getAttribute("aria-expanded") !== "true") toggle.click();
    }
    function ask(text) {
        const fullArea = document.querySelector("main textarea[name=message]");
        const target = path.startsWith("/assistant/") && fullArea ? fullArea : area;
        if (!target || !target.form) return;
        if (target === area) open();
        setTimeout(() => {
            target.value = text;
            target.dispatchEvent(new Event("input", { bubbles: true }));
            if (target.form.requestSubmit) target.form.requestSubmit(); else target.form.submit();
        }, 180);
    }
    window.GISazon = { open, ask };

    // Preguntas «Para esta pantalla» dentro del widget
    const chips = widget && widget.querySelector(".aw-chips");
    if (chips && !widget.querySelector(".sazon-ctx")) {
        const box = document.createElement("div");
        box.className = "sazon-ctx";
        box.innerHTML = `<p class="sazon-ctx-title">Para ${esc(contextName)}</p><div class="sazon-ctx-chips"></div>`;
        const row = box.querySelector(".sazon-ctx-chips");
        contextQs.forEach(([label, prompt]) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "chip";
            chip.textContent = label;
            chip.addEventListener("click", () => ask(prompt));
            row.appendChild(chip);
        });
        chips.before(box);
    }

    // Alertas urgentes: tarjeta al abrir, contador en el botón y aviso
    let urgent = [];
    const feed = document.body.dataset.alertsUrl;
    function paintUrgent() {
        if (toggle) {
            let badge = toggle.querySelector(".sazon-badge");
            if (!badge) { badge = document.createElement("b"); badge.className = "sazon-badge"; toggle.appendChild(badge); }
            badge.hidden = !urgent.length;
            badge.textContent = String(urgent.length);
        }
        document.querySelectorAll(".sazon-urgent").forEach((el) => el.remove());
        if (!urgent.length) return;
        const card = document.createElement("div");
        card.className = "sazon-urgent";
        card.innerHTML = `<strong>🚨 Tienes ${urgent.length} alerta${urgent.length === 1 ? "" : "s"} urgente${urgent.length === 1 ? "" : "s"}</strong>
            <ul>${urgent.slice(0, 3).map((a) => `<li>${esc(a.icon)} ${esc(a.title)}</li>`).join("")}</ul>
            <a class="btn btn-small btn-primary" href="/garzon/">Ir a Mis alertas</a>`;
        const welcome = widget && (widget.querySelector(".sazon-ctx") || widget.querySelector(".aw-chips"));
        if (welcome) welcome.before(card);
        const full = path.startsWith("/assistant/") && document.querySelector("main textarea[name=message]");
        if (full) { const copy = card.cloneNode(true); (full.form.closest("section, .card") || full.form).before(copy); }
    }
    async function loadAlerts() {
        if (!feed) return;
        try {
            const response = await fetch(feed, { credentials: "same-origin" });
            if (!response.ok) return;
            urgent = ((await response.json()).items || []).filter((a) => a.level === "danger");
            paintUrgent();
        } catch (e) { /* se reintenta */ }
    }
    loadAlerts();
    setInterval(loadAlerts, 20000);

    // Resumen de la pantalla actual: para qué sirve y las cifras que muestra ahora
    function pageBrief() {
        const title = ((document.querySelector("main h1") || {}).textContent || "Esta pantalla").replace(/[ⓘ]/g, "").replace(/\s+/g, " ").trim();
        const help = ((document.querySelector("main .page-help") || {}).textContent || "").trim();
        const figures = [];
        document.querySelectorAll("main .mini-kpi:not(.mini-kpi-action), main .kpi, main .page-panel .floor-chip").forEach((k) => {
            if (k.hidden || k.closest("[hidden]")) return;
            const value = ((k.querySelector("strong, .kpi-value") || {}).textContent || "").trim();
            let label = ((k.querySelector(".kpi-label, span:not(.mini-kpi-icon):not(.kpi-icon)") || {}).textContent || "").trim();
            if (!label && k.classList.contains("floor-chip")) label = k.textContent.replace(value, "").trim();
            if (value && label && !figures.some(([l]) => l === label)) figures.push([label, value]);
        });
        return `<section class="sn-brief"><p class="sn-title">📍 ${esc(title)}</p>${help ? `<p class="sn-help">${esc(help)}</p>` : ""}
            ${figures.length ? `<p class="sn-title">Lo que muestra ahora</p><ul class="sn-figures">${figures.slice(0, 6).map(([l, v]) => `<li><span>${esc(l)}</span><strong>${esc(v)}</strong></li>`).join("")}</ul>` : ""}</section>`;
    }
    function showBrief() {
        document.querySelectorAll(".sazon-nudge").forEach((n) => n.remove());
        const nudge = document.createElement("div");
        nudge.className = "sazon-nudge";
        document.body.appendChild(nudge);
        expandNudge(nudge, true);
    }

    // La burbuja se agranda y muestra las sugerencias
    async function loadIdeas() {
        const KEY = "gi-sazon-ideas";
        try {
            const cached = JSON.parse(sessionStorage.getItem(KEY) || "null");
            if (cached && Date.now() - cached.at < 120000) return cached.ideas;
        } catch (e) { /* sin caché */ }
        try {
            const response = await fetch("/", { credentials: "same-origin" });
            if (!response.ok) return [];
            const doc = new DOMParser().parseFromString(await response.text(), "text/html");
            const ideas = [...doc.querySelectorAll(".idea")].slice(0, 3).map((idea) => ({
                icon: ((idea.querySelector(".idea-icon") || {}).textContent || "💡").trim(),
                title: ((idea.querySelector("h3") || {}).textContent || "").trim(),
                action: ((idea.querySelector(".idea-action") || {}).textContent || "").replace(/^\s*💡?\s*Qué hacer:\s*/i, "").trim(),
                href: ([...idea.querySelectorAll("a[href]")].pop() || {}).getAttribute ? [...idea.querySelectorAll("a[href]")].pop().getAttribute("href") : "",
            })).filter((i) => i.title);
            try { sessionStorage.setItem(KEY, JSON.stringify({ at: Date.now(), ideas })); } catch (e) { /* sin almacenamiento */ }
            return ideas;
        } catch (e) { return []; }
    }
    async function expandNudge(nudge, isBrief) {
        nudge.classList.add("is-expanded");
        nudge.innerHTML = `<header class="sn-head"><span class="sazon-orb-mini" aria-hidden="true"></span><strong>Sazón sugiere</strong>
            <button type="button" class="sazon-nudge-close" aria-label="Cerrar">✕</button></header>
            <div class="sn-body"><p class="muted">Pensando…</p></div>
            <footer class="sn-foot"><button type="button" class="btn btn-small btn-primary sn-chat">Abrir chat</button></footer>`;
        nudge.querySelector(".sazon-nudge-close").addEventListener("click", () => nudge.remove());
        nudge.querySelector(".sn-chat").addEventListener("click", () => { nudge.remove(); open(); });
        const body = nudge.querySelector(".sn-body");
        let html = isBrief ? pageBrief() : "";
        if (urgent.length) {
            html += `<section class="sn-urgent"><p class="sn-title">🚨 Urgente</p><ul>${urgent.slice(0, 3).map((a) => `<li>${esc(a.icon)} ${esc(a.title)}</li>`).join("")}</ul>
                <a class="btn btn-small btn-secondary" href="/garzon/">Ir a Mis alertas</a></section>`;
        }
        const ideas = isBrief && path !== "/" ? [] : await loadIdeas();
        if (ideas.length) {
            html += `<section><p class="sn-title">💡 Ideas para hoy</p>${ideas.map((i) => `<article class="sn-idea"><strong>${esc(i.icon)} ${esc(i.title)}</strong>
                ${i.action ? `<p>${esc(i.action)}</p>` : ""}${i.href ? `<a href="${esc(i.href)}">Ver detalle →</a>` : ""}</article>`).join("")}</section>`;
        }
        html += `<section><p class="sn-title">Pregúntale a Sazón</p><div class="sn-chips"></div></section>`;
        body.innerHTML = html;
        const row = body.querySelector(".sn-chips");
        contextQs.forEach(([label, prompt]) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "chip";
            chip.textContent = label;
            chip.addEventListener("click", () => { nudge.remove(); ask(prompt); });
            row.appendChild(chip);
        });
    }

    // Aviso amable sobre el botón de Sazón (una vez por pantalla y sesión)
    const nudgeKey = `gi-sazon-nudge-${path}`;
    let shown = false;
    try { shown = sessionStorage.getItem(nudgeKey) === "1"; } catch (e) { shown = false; }
    if (toggle && !shown && !path.startsWith("/assistant/")) {
        setTimeout(() => {
            if (toggle.getAttribute("aria-expanded") === "true") return;
            const nudge = document.createElement("div");
            nudge.className = "sazon-nudge";
            const text = urgent.length ? `🚨 ${urgent.length} alerta${urgent.length === 1 ? "" : "s"} urgente${urgent.length === 1 ? "" : "s"}: toca para verlas` : `💡 Tengo ideas para ${contextName}`;
            nudge.innerHTML = `<button type="button" class="sazon-nudge-text"></button><button type="button" class="sazon-nudge-close" aria-label="Cerrar">✕</button>`;
            nudge.querySelector(".sazon-nudge-text").textContent = text;
            nudge.querySelector(".sazon-nudge-text").addEventListener("click", () => expandNudge(nudge));
            nudge.querySelector(".sazon-nudge-close").addEventListener("click", () => nudge.remove());
            document.body.appendChild(nudge);
            try { sessionStorage.setItem(nudgeKey, "1"); } catch (e) { /* sin almacenamiento */ }
            setTimeout(() => { if (!nudge.classList.contains("is-expanded")) nudge.remove(); }, 12000);
        }, 3500);
    }

    // «✨ Pregúntale a Sazón» en el encabezado de cada pantalla
    const header = document.querySelector("main .page-header");
    if (header && toggle && path !== "/" && !path.startsWith("/assistant/") && !header.querySelector(".sazon-ask")) {
        let row = header.querySelector(".page-actions");
        if (!row) { row = document.createElement("div"); row.className = "page-actions"; header.appendChild(row); }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-secondary sazon-ask";
        button.textContent = "✨ Pregúntale a Sazón";
        button.addEventListener("click", showBrief);
        row.appendChild(button);
    }

    // Inicio: Sazón presenta las sugerencias
    const tipsTitle = document.querySelector(".home-tips .tips-head h2");
    if (tipsTitle && !tipsTitle.querySelector(".sazon-orb-mini")) {
        tipsTitle.innerHTML = '<span class="sazon-orb-mini" aria-hidden="true"></span> Sazón te sugiere hoy';
        const CATEGORY = { venta: Q.platos[1], marketing: Q.promo[1], experiencia: Q.etapa[1] };
        document.querySelectorAll(".flip-card").forEach((card) => {
            const back = card.querySelector(".flip-back");
            if (!back || back.querySelector(".sazon-tip-ask")) return;
            const kind = ["venta", "marketing", "experiencia"].find((k) => card.classList.contains(`tip-${k}`)) || "venta";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-small btn-secondary sazon-tip-ask";
            button.textContent = "✨ Pregúntale a Sazón";
            button.addEventListener("click", (event) => { event.stopPropagation(); ask(CATEGORY[kind]); });
            const hint = back.querySelector(".flip-hint");
            if (hint) hint.before(button); else back.appendChild(button);
        });
    }
})();
