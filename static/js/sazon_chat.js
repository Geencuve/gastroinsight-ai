/* GastroInsight AI · Chat de Sazón: fila de preguntas con flechas y botón ⓘ «¿Cómo lo obtuve?» en cada respuesta. */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1") return;
    if (location.pathname.startsWith("/assistant/")) document.body.classList.add("on-sazon-page");

    const SOURCES = [
        [/medios? de pago/i, "Pedidos pagados del período, agrupados por medio de pago (efectivo, débito, crédito, transferencia)."],
        [/ticket/i, "Pedidos pagados del período. Ticket por pedido = ventas ÷ número de pedidos; por comensal = ventas ÷ comensales registrados en las atenciones."],
        [/m[aá]s vendid|platos? (que )?(m[aá]s|menos)|unidades/i, "Platos de los pedidos pagados, agrupados por plato y ordenados por unidades vendidas."],
        [/ventas? de|vendimos|vendido|ventas/i, "Suma de los totales de los pedidos pagados en el período consultado; se compara con el mismo tramo del período anterior."],
        [/d[ií]a m[aá]s flojo|por d[ií]a de la semana|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo/i, "Promedio de ventas por día de la semana en las últimas semanas (estadística descriptiva)."],
        [/promoc|combo|estrella/i, "Reglas de negocio sobre tus ventas: día más flojo, plato estrella y combinaciones frecuentes de platos (análisis de canasta). No es una predicción."],
        [/etapa|journey|recorrido/i, "IEO promedio de cada etapa de la atención (llegada, espera de platos, consumo, cuenta y pago), calculado con lecturas de cámaras agregadas por mesa."],
        [/c[aá]mara/i, "Estado de las cámaras registradas y sus lecturas de los últimos minutos (solo números agregados, nunca imágenes)."],
        [/infraestructura|ambiente|ocupaci/i, "Lecturas agregadas de ocupación y actividad por mesa, enviadas por el análisis visual."],
        [/mesa|sala|esperando/i, "Estado actual de las mesas (atenciones abiertas, pedidos y cuentas) y lecturas de cámaras de los últimos 2 minutos."],
        [/evaluaci|nota|satisf|csat/i, "Evaluaciones voluntarias que dejan los clientes con el QR de la boleta (nota de 1 a 5)."],
    ];
    const NOTE = "Sazón entiende tu pregunta con reglas propias (NLIDB) y consulta directamente la base de datos del local. No usa servicios externos ni tiene costo por consulta.";

    function addInfo(bubble) {
        if (bubble.dataset.sazonInfo) return;
        bubble.dataset.sazonInfo = "1";
        const text = bubble.textContent || "";
        if (text.trim().length < 12) return;
        const match = SOURCES.find(([pattern]) => pattern.test(text));
        const button = document.createElement("button");
        button.type = "button";
        button.className = "sazon-info-btn";
        button.textContent = "i";
        button.title = "¿Cómo lo obtuve?";
        button.setAttribute("aria-label", "¿Cómo obtuvo Sazón esta información?");
        const pop = document.createElement("div");
        pop.className = "sazon-info-pop";
        pop.hidden = true;
        pop.innerHTML = "<strong>¿Cómo lo obtuve?</strong><p></p><small></small>";
        pop.querySelector("p").textContent = match ? match[1] : "Datos registrados del local (pedidos, atenciones, evaluaciones y lecturas agregadas de cámaras).";
        pop.querySelector("small").textContent = NOTE;
        button.addEventListener("click", (event) => { event.stopPropagation(); pop.hidden = !pop.hidden; });
        bubble.classList.add("has-sazon-info");
        bubble.append(button, pop);
    }

    function scan(root) {
        root.querySelectorAll('[class*="bubble"]:not([class*="user"]):not([class*="typing"]):not([class*="bubbles"])').forEach((bubble) => {
            if (bubble.querySelector('[class*="bubble"]') || bubble.closest(".sazon-info-pop")) return;
            const row = bubble.closest('[class*="message"], [class*="msg"], [class*="row"]');
            if (row && /user|mine|outgoing/i.test(row.className)) return;
            addInfo(bubble);
        });
        enhanceStrips(root);
    }

    // Fila de preguntas: flechas, desvanecido y rueda del mouse (sin barra de desplazamiento)
    function enhanceStrips(root) {
        root.querySelectorAll("div, nav").forEach((strip) => {
            if (strip.dataset.sazonStrip || strip.closest(".sazon-strip-wrap")) return;
            const chips = strip.querySelectorAll(":scope > .chip, :scope > button.chip, :scope > .followup-chip");
            if (chips.length < 4) return;
            const style = getComputedStyle(strip);
            if (!/auto|scroll/.test(style.overflowX) && style.flexWrap !== "nowrap") return;
            strip.dataset.sazonStrip = "1";
            strip.classList.add("sazon-strip");
            const wrap = document.createElement("div");
            wrap.className = "sazon-strip-wrap";
            strip.before(wrap);
            const left = document.createElement("button");
            left.type = "button"; left.className = "sazon-strip-arrow is-left"; left.textContent = "‹"; left.setAttribute("aria-label", "Ver preguntas anteriores");
            const right = document.createElement("button");
            right.type = "button"; right.className = "sazon-strip-arrow is-right"; right.textContent = "›"; right.setAttribute("aria-label", "Ver más preguntas");
            wrap.append(left, strip, right);
            const update = () => {
                const max = strip.scrollWidth - strip.clientWidth - 2;
                left.hidden = strip.scrollLeft <= 2;
                right.hidden = strip.scrollLeft >= max;
                wrap.classList.toggle("fade-left", !left.hidden);
                wrap.classList.toggle("fade-right", !right.hidden);
            };
            left.addEventListener("click", () => strip.scrollBy({ left: -260, behavior: "smooth" }));
            right.addEventListener("click", () => strip.scrollBy({ left: 260, behavior: "smooth" }));
            strip.addEventListener("scroll", update, { passive: true });
            strip.addEventListener("wheel", (event) => {
                if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) { strip.scrollLeft += event.deltaY; event.preventDefault(); }
            }, { passive: false });
            window.addEventListener("resize", update);
            setTimeout(update, 50);
        });
    }

    document.addEventListener("click", (event) => {
        if (!event.target.closest(".sazon-info-pop, .sazon-info-btn")) document.querySelectorAll(".sazon-info-pop").forEach((p) => { p.hidden = true; });
    });
    let busy = false;
    const run = () => { if (busy) return; busy = true; try { scan(document); } finally { busy = false; } };
    run();
    const logs = document.querySelectorAll('#assistant-widget-panel, main [class*="chat"], main [class*="conversation"], main [class*="messages"]');
    const observer = new MutationObserver(() => { clearTimeout(window.__sazonScan); window.__sazonScan = setTimeout(run, 60); });
    (logs.length ? logs : [document.body]).forEach((log) => observer.observe(log, { childList: true, subtree: true }));
})();

/* GastroInsight AI · «Herramientas de mejora» plegable en la página de Sazón. */
(function () {
    "use strict";
    if (!location.pathname.startsWith("/assistant/")) return;
    const label = [...document.querySelectorAll("main h2, main h3, main h4, main p, main span, main div, main strong")]
        .find((el) => !el.children.length && /^herramientas de mejora$/i.test(el.textContent.trim()));
    if (!label) return;
    const card = label.closest(".card, section, aside > div, .sidebar-card") || label.parentElement;
    if (!card || card.querySelector(".sazon-tools-fold")) return;
    const count = card.querySelectorAll("a[href]").length;
    const details = document.createElement("details");
    details.className = "sazon-tools-fold";
    details.innerHTML = `<summary>🛠️ <strong>Herramientas de mejora</strong><span class="stf-count">${count}</span></summary>`;
    [...card.childNodes].forEach((node) => { if (node !== label && !(node.contains && node.contains(label))) details.appendChild(node); });
    label.replaceWith(details);
})();

/* GastroInsight AI · Herramientas de mejora como caja de aplicaciones. */
(function () {
    "use strict";
    const fold = document.querySelector(".sazon-tools-fold");
    if (!fold) return;
    const links = [...fold.querySelectorAll("a[href]")];
    if (!links.length) return;
    links[0].parentElement.classList.add("stf-grid");
    links.forEach((link) => {
        link.classList.add("stf-app");
        const parts = [...link.querySelectorAll("small, p, span")].filter((el) => !el.children.length && el.textContent.trim().length > 12);
        if (parts.length) link.title = parts[parts.length - 1].textContent.trim();
    });
})();
