/* GastroInsight AI · Leyendas de ayuda (2 s sobre una función) y tour guiado. */
(function () {
    "use strict";

    const HOVER_DELAY = 2000;
    const FOCUS_DELAY = 900;
    const TIPS_KEY = "gi-tips";

    const HREF_TIPS = {
        "/operations/sessions/": "Abre y cierra la atención de cada mesa. Una mesa no se puede cerrar con pedidos sin pagar.",
        "/operations/sessions/create/": "Abre una nueva atención en una mesa libre.",
        "/sales/": "Crea pedidos, agrega platos, aplica descuentos y registra pagos.",
        "/sales/create/": "Crea un pedido para una mesa con atención abierta.",
        "/operations/evaluations/": "Valoraciones de clientes registradas por el personal o por código QR.",
        "/operations/evaluations/create/": "Registra la valoración de un cliente.",
        "/opinion/qr/": "Imprime un código QR por mesa para que los clientes califiquen sin crear una cuenta.",
        "/operations/tables/": "Mesas del local: código, capacidad y zona.",
        "/cocina/": "Comandas de cocina por tiempo de espera, con aceptación de cada plato.",
        "/barra/": "Fila de bebidas con temporizadores de despacho y su aceptación.",
        "/sala/": "Mapa de sala: estado de cada mesa por colores, lista de espera y alertas de atención.",
        "/caja/": "Caja: mesas por cobrar con su termómetro de experiencia y una sugerencia para el cierre.",
        "/ai/entrenamiento/": "Sube imágenes etiquetadas con consentimiento para medir la precisión del modelo (matriz de confusión) y calibrarlo.",
        "/ai/monitor/": "Estado en tiempo real de cada mesa: Índice de Experiencia Observable y alertas.",
        "/ai/sessions/": "Crea e inicia análisis con la cámara. Los fotogramas se procesan en memoria y no se guardan.",
        "/cameras/": "Cámaras registradas y la mesa que monitorea cada una.",
        "/analytics/correlation/": "Prueba estadística: relación entre tiempo de servicio, expresiones y satisfacción.",
        "/analytics/": "Dashboard del día: ventas, atención, evaluaciones y análisis visual.",
        "/reports/": "Reportes diarios y por período, descargables en PDF y CSV.",
        "/promociones/": "Genera imágenes para redes sociales a partir de tu carta.",
        "/venues/": "Locales registrados en la plataforma.",
        "/menus/": "Carta visual: platos, precios, fotos y los más pedidos.",
        "/monitoring/incidents/": "Problemas técnicos detectados por el sistema.",
        "/privacy/": "Políticas de privacidad y autorizaciones del análisis visual.",
        "/monitoring/audit/": "Registro de todas las acciones realizadas en el sistema.",
        "/assistant/staff/": "Sazón: pregunta en lenguaje natural por ventas, platos, mesas o ideas para vender más.",
        "/auth/profile/": "Tus datos, permisos, seguridad y preferencias.",
        "/auth/password/change/": "Cambia la contraseña de tu cuenta.",
        "/admin/": "Panel de administración: usuarios, roles y datos maestros.",
    };

    const NAV_TIPS = {
        "Operación": "Mesas, atención, pedidos, cobros y evaluaciones.",
        "Visión IA": "Monitor en vivo, análisis con cámara y panel de correlación.",
        "Análisis": "Dashboard, reportes y generador de promociones.",
        "Gestión": "Locales, carta y fotos, incidencias y privacidad.",
    };

    const CARD_TIPS = {
        "Vendido hoy": "Suma de los pedidos pagados hoy.",
        "Ticket promedio hoy": "Monto promedio por pedido pagado hoy.",
        "Mesas atendiéndose": "Mesas con una atención abierta en este momento.",
        "Por cobrar": "Pedidos abiertos o confirmados que aún no se pagan.",
        "Clientes satisfechos": "Porcentaje de evaluaciones con nota 4 o 5 en los últimos 7 días.",
        "Ventas totales del día": "Suma de los pedidos pagados en la fecha seleccionada.",
        "Pedidos pagados": "Pedidos cerrados con pago registrado.",
        "Ticket promedio": "Monto promedio por pedido pagado.",
        "Pedidos en curso": "Pedidos abiertos o confirmados que aún no se pagan.",
        "Latencia promedio": "Tiempo de análisis por fotograma. El objetivo del proyecto es menos de 200 ms.",
        "Eventos bajo 200 ms": "Porcentaje de eventos procesados dentro del umbral de latencia.",
        "Confianza del detector": "Seguridad promedio de YuNet al detectar rostros (umbral 0,70).",
        "Confianza de expresión (FER+)": "Probabilidad promedio que FER+ asigna a la expresión estimada.",
        "Índice de experiencia observable": "IEO 0-100: 60% valencia, 25% búsqueda de atención (invertida) y 15% tiempo sin atención.",
        "Valencia de expresiones": "Balance de expresiones entre -1 (negativas) y +1 (positivas).",
        "Búsqueda de atención": "Porcentaje de rostros con la cabeza girada, como buscando al personal.",
        "Ocupación promedio": "Mediana de personas visibles en la mesa.",
        "Presencia": "Porcentaje del tiempo con al menos una persona visible.",
        "Actividad promedio": "Cuánto cambia la imagen entre fotogramas, de 0 a 100.",
        "Fotogramas procesados": "Imágenes de la cámara analizadas en memoria durante la sesión.",
        "Rostros acumulados": "Suma de rostros detectados en todos los fotogramas. No equivale a personas distintas.",
    };

    const TH_TIPS = {
        "Pearson r": "Correlación lineal entre -1 y 1. Cerca de 0 significa sin relación lineal.",
        "Spearman ρ": "Correlación por rangos: detecta relaciones que suben o bajan aunque no sean lineales.",
        "p": "Valor p: si es menor que 0,05, la relación es estadísticamente significativa.",
        "n": "Cantidad de atenciones incluidas en el análisis.",
        "Interpretación": "Lectura del resultado: fuerza, dirección y si se rechaza la hipótesis nula (H0).",
        "Ts (min)": "Tiempo de servicio: minutos entre que se abre y se cierra la atención de la mesa.",
    };

    const SELECTOR_TIPS = [
        ["#theme-toggle", "Cambia entre tema oscuro y claro."],
        ["#assistant-widget-toggle", "Abre a Sazón, tu copiloto de gestión."],
        [".user-menu > summary", "Tu perfil, configuración de cuenta, tour guiado y cierre de sesión."],
        [".composer-send", "Enviar la pregunta (también con Enter)."],
        [".idea-impact", "Estimación simple para orientar decisiones; no es una proyección financiera."],
        [".gauge", "Índice de Experiencia Observable de la mesa: verde ≥ 65, ámbar 45-64, rojo < 45."],
        [".dish-badge", "Uno de los 3 platos más vendidos en las últimas 4 semanas."],
        [".chip[data-filter]", "Filtra la carta por categoría."],
        [".tag-synthetic", "Lectura de la simulación de demostración, no de una cámara real."],
        [".reason", "Motivo de la alerta de esta mesa."],
        ["[data-start-tour]", "Recorre las funciones principales en un minuto."],
    ];

    const clean = (node) => (node.textContent || "").replace(/\s+/g, " ").trim();
    const tipsEnabled = () => { try { return localStorage.getItem(TIPS_KEY) !== "off"; } catch (e) { return true; } };

    function tipFor(start) {
        let el = start;
        for (let depth = 0; el && el.nodeType === 1 && el !== document.body && depth < 6; depth += 1, el = el.parentElement) {
            if (el.closest(".gi-tour-card, .gi-tooltip")) return [null, null];
            if (el.dataset && el.dataset.tip) return [el, el.dataset.tip];
            for (const [selector, tip] of SELECTOR_TIPS) if (el.matches(selector)) return [el, tip];
            if (el.matches(".nav-group > summary") && NAV_TIPS[clean(el)]) return [el, NAV_TIPS[clean(el)]];
            if (el.matches("th") && TH_TIPS[clean(el)]) return [el, TH_TIPS[clean(el)]];
            if (el.matches(".kpi, .metric-card")) {
                const label = el.querySelector(".kpi-label, .metric-label");
                if (label && CARD_TIPS[clean(label)]) return [el, CARD_TIPS[clean(label)]];
            }
            if (el.matches("a[href]")) {
                const url = new URL(el.getAttribute("href"), location.origin);
                if (url.origin === location.origin && !url.search && HREF_TIPS[url.pathname]) return [el, HREF_TIPS[url.pathname]];
            }
        }
        return [null, null];
    }

    /* ---------------- Leyendas ---------------- */
    const tooltip = document.createElement("div");
    tooltip.className = "gi-tooltip";
    tooltip.setAttribute("role", "tooltip");
    let timer = null;
    let current = null;

    function hideTip() {
        clearTimeout(timer);
        timer = null;
        current = null;
        tooltip.classList.remove("is-visible");
    }

    function showTip(el, text) {
        if (!document.body.contains(el)) return;
        tooltip.textContent = text;
        if (!tooltip.isConnected) document.body.appendChild(tooltip);
        const r = el.getBoundingClientRect();
        const width = tooltip.offsetWidth;
        const height = tooltip.offsetHeight;
        let top = r.bottom + 10;
        if (top + height > window.innerHeight - 8) top = r.top - height - 10;
        const left = Math.min(Math.max(8, r.left + r.width / 2 - width / 2), window.innerWidth - width - 8);
        tooltip.style.top = `${Math.max(8, top)}px`;
        tooltip.style.left = `${left}px`;
        tooltip.classList.add("is-visible");
    }

    function arm(target, delay) {
        if (!tipsEnabled() || document.body.classList.contains("gi-touring")) return;
        const [el, text] = tipFor(target);
        if (el === current) return;
        hideTip();
        if (!el) return;
        current = el;
        timer = setTimeout(() => showTip(el, text), delay);
    }

    document.addEventListener("mouseover", (event) => arm(event.target, HOVER_DELAY));
    document.addEventListener("mouseout", (event) => {
        if (current && !(event.relatedTarget && current.contains(event.relatedTarget))) hideTip();
    });
    document.addEventListener("focusin", (event) => arm(event.target, FOCUS_DELAY));
    document.addEventListener("focusout", hideTip);
    ["scroll", "click", "keydown"].forEach((type) => window.addEventListener(type, hideTip, true));

    /* ---------------- Preferencia de leyendas ---------------- */
    function markTipsChoice() {
        document.querySelectorAll("[data-tips-choice]").forEach((button) => {
            button.classList.toggle("is-active", (button.dataset.tipsChoice === "on") === tipsEnabled());
        });
    }
    document.addEventListener("click", (event) => {
        const choice = event.target.closest("[data-tips-choice]");
        if (!choice) return;
        try { localStorage.setItem(TIPS_KEY, choice.dataset.tipsChoice); } catch (e) { /* sin almacenamiento */ }
        markTipsChoice();
    });

    /* ---------------- Tour guiado ---------------- */
    const navSummary = (text) => [...document.querySelectorAll(".nav-group:not(.user-menu) > summary")].find((s) => clean(s) === text);
    const STEPS = [
        { title: "Bienvenido a GastroInsight AI 👋",
          text: "Te mostramos en un minuto dónde está cada cosa. Puedes avanzar con las flechas del teclado o salir con Esc." },
        { target: () => navSummary("Operación"), title: "Operación",
          text: "Abre mesas, toma pedidos eligiendo platos por su foto, cobra y registra las evaluaciones de tus clientes." },
        { target: () => navSummary("Visión IA"), title: "Visión IA",
          text: "Monitor en vivo de cada mesa, análisis con la cámara (sin guardar imágenes) y el panel de correlación." },
        { target: () => navSummary("Análisis"), title: "Análisis",
          text: "Dashboard del día, reportes en PDF y CSV, y el generador de promociones para redes." },
        { target: () => navSummary("Gestión"), title: "Gestión",
          text: "Locales, carta y fotos de los platos, incidencias técnicas y políticas de privacidad." },
        { target: ".kpi-grid", title: "Tu día en números",
          text: "Ventas, ticket, mesas atendiéndose, pedidos por cobrar y satisfacción. Deja el mouse 2 segundos sobre cualquier dato para ver qué significa." },
        { target: ".idea-section", title: "Ideas a partir de tus datos",
          text: "Oportunidades de venta, marketing y experiencia con su potencial estimado. Con «Crear promo» generas la imagen para redes." },
        { target: "#assistant-widget-toggle", title: "Sazón, tu copiloto",
          text: "Pregúntale en lenguaje natural: «¿cuánto vendimos esta semana?» o «¿qué debería promocionar?». Responde con tus datos reales." },
        { target: ".user-menu > summary", title: "Tu cuenta",
          text: "Mi perfil, configuración de cuenta, cambio de contraseña y cierre de sesión. Desde aquí también repites este tour." },
        { target: "#theme-toggle", title: "Tema oscuro o claro",
          text: "Elige el que se vea mejor en tu pantalla. La preferencia se guarda en este equipo." },
        { title: "¡Listo para empezar! 🚀",
          text: "Explora a tu ritmo. Si en algún momento quieres repetir el recorrido, usa «Ver tour guiado» en tu menú de usuario." },
    ];

    const resolve = (step) => {
        if (!step.target) return null;
        const el = typeof step.target === "function" ? step.target() : document.querySelector(step.target);
        return el && el.getClientRects().length ? el : undefined;
    };
    const userId = document.body.dataset.userId || "";
    const doneKey = `gi-tour-done-${userId}`;
    let tour = null;

    function place(el) {
        const { backdrop, spot, card } = tour;
        if (!el) {
            backdrop.hidden = false;
            spot.hidden = true;
            Object.assign(card.style, { top: "50%", left: "50%", transform: "translate(-50%, -50%)" });
            return;
        }
        backdrop.hidden = true;
        spot.hidden = false;
        const r = el.getBoundingClientRect();
        const pad = 6;
        Object.assign(spot.style, {
            top: `${r.top - pad}px`, left: `${r.left - pad}px`,
            width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px`,
        });
        card.style.transform = "none";
        const margin = 14;
        const width = card.offsetWidth;
        const height = card.offsetHeight;
        let top = r.bottom + pad + margin;
        if (top + height > window.innerHeight - margin) top = Math.max(margin, r.top - pad - margin - height);
        const left = Math.min(Math.max(margin, r.left), window.innerWidth - width - margin);
        Object.assign(card.style, { top: `${top}px`, left: `${left}px` });
    }

    function render() {
        const step = tour.steps[tour.index];
        const last = tour.index === tour.steps.length - 1;
        tour.card.innerHTML = "";
        const counter = document.createElement("small");
        counter.className = "gi-tour-counter";
        counter.textContent = `Paso ${tour.index + 1} de ${tour.steps.length}`;
        const title = document.createElement("h3");
        title.textContent = step.title;
        const text = document.createElement("p");
        text.textContent = step.text;
        const actions = document.createElement("div");
        actions.className = "gi-tour-actions";
        const skip = document.createElement("button");
        skip.type = "button";
        skip.className = "gi-tour-skip";
        skip.textContent = last ? "" : "Saltar tour";
        skip.addEventListener("click", endTour);
        const nav = document.createElement("div");
        if (tour.index > 0) {
            const prev = document.createElement("button");
            prev.type = "button";
            prev.className = "btn btn-secondary btn-small";
            prev.textContent = "Anterior";
            prev.addEventListener("click", () => go(-1));
            nav.appendChild(prev);
        }
        const next = document.createElement("button");
        next.type = "button";
        next.className = "btn btn-primary btn-small";
        next.textContent = last ? "Comenzar" : "Siguiente";
        next.addEventListener("click", () => (last ? endTour() : go(1)));
        nav.appendChild(next);
        actions.append(skip, nav);
        tour.card.append(counter, title, text, actions);

        const el = resolve(step);
        if (el) {
            el.scrollIntoView({ block: "center", behavior: "auto" });
            requestAnimationFrame(() => place(el));
        } else {
            place(null);
        }
        next.focus();
    }

    function go(delta) {
        tour.index = Math.min(Math.max(0, tour.index + delta), tour.steps.length - 1);
        render();
    }

    function onKey(event) {
        if (!tour) return;
        if (event.key === "Escape") endTour();
        if (event.key === "ArrowRight") go(1);
        if (event.key === "ArrowLeft") go(-1);
    }

    function onResize() {
        if (tour) place(resolve(tour.steps[tour.index]) || null);
    }

    function startTour() {
        if (tour) return;
        hideTip();
        document.querySelectorAll("details[open]").forEach((d) => { d.open = false; });
        const steps = STEPS.filter((step) => resolve(step) !== undefined);
        const backdrop = document.createElement("div");
        backdrop.className = "gi-tour-backdrop";
        const spot = document.createElement("div");
        spot.className = "gi-tour-spot";
        const card = document.createElement("div");
        card.className = "gi-tour-card";
        card.setAttribute("role", "dialog");
        card.setAttribute("aria-live", "polite");
        document.body.append(backdrop, spot, card);
        document.body.classList.add("gi-touring");
        tour = { steps, index: 0, backdrop, spot, card };
        window.addEventListener("keydown", onKey);
        window.addEventListener("resize", onResize);
        render();
    }

    function endTour() {
        if (!tour) return;
        tour.backdrop.remove();
        tour.spot.remove();
        tour.card.remove();
        tour = null;
        document.body.classList.remove("gi-touring");
        window.removeEventListener("keydown", onKey);
        window.removeEventListener("resize", onResize);
        try { localStorage.setItem(doneKey, "1"); } catch (e) { /* sin almacenamiento */ }
        window.scrollTo({ top: 0 });
    }

    document.addEventListener("click", (event) => {
        if (!event.target.closest("[data-start-tour]")) return;
        event.preventDefault();
        if (location.pathname === "/") {
            startTour();
        } else {
            location.href = "/?tour=1";
        }
    });

    document.addEventListener("DOMContentLoaded", () => {
        markTipsChoice();
        if (!userId || location.pathname !== "/") return;
        const params = new URLSearchParams(location.search);
        let done = false;
        try { done = localStorage.getItem(doneKey) === "1"; } catch (e) { done = true; }
        if (params.get("tour") === "1") {
            history.replaceState(null, "", "/");
            setTimeout(startTour, 500);
        } else if (!done) {
            setTimeout(startTour, 900);
        }
    });

    window.GITour = { start: startTour };
})();
