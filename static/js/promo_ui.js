/* GastroInsight AI · Promociones: barra que se contrae, imagen centrada y texto sugerido flotante. */
(function () {
    "use strict";
    if (!location.pathname.startsWith("/promociones/") || document.body.dataset.embed === "1") return;
    const form = document.getElementById("promo-form");
    if (!form || form.querySelector(".promo-more")) return;

    // 1. Barra: lo esencial a la vista y «Personalizar» para el resto
    const PRIMARY = ["f-tipo", "f-plato", "f-plato2", "f-dia", "f-formato"];
    const groups = [...form.querySelectorAll(":scope > .form-group")];
    const more = document.createElement("div");
    more.className = "promo-more";
    groups.filter((g) => !PRIMARY.some((id) => g.querySelector(`#${id}`))).forEach((g) => more.appendChild(g));
    const submit = form.querySelector("button[type=submit], .btn-primary");
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn btn-secondary promo-more-toggle";
    const KEY = "gi-promo-more";
    let open = false;
    try { open = localStorage.getItem(KEY) === "1"; } catch (e) { open = false; }
    const upload = document.getElementById("promo-upload");
    const paint = () => {
        more.hidden = !open;
        if (upload) upload.classList.toggle("is-collapsed", !open);
        toggle.textContent = open ? "✏️ Personalizar ▴" : "✏️ Personalizar ▾";
        toggle.setAttribute("aria-expanded", String(open));
    };
    toggle.addEventListener("click", () => {
        open = !open;
        try { localStorage.setItem(KEY, open ? "1" : "0"); } catch (e) { /* sin almacenamiento */ }
        paint();
    });
    if (submit) { submit.before(toggle); form.appendChild(more); } else { form.append(toggle, more); }
    paint();

    // 2 y 3. Imagen centrada con sus botones debajo; texto sugerido en una tarjeta flotante
    const preview = document.querySelector(".promo-preview");
    const card = preview && preview.closest(".card");
    const caption = card && card.querySelector(".promo-caption");
    const actions = card && card.querySelector(".promo-actions");
    if (!card || !caption || !actions) return;
    card.classList.add("promo-stage");
    const heading = caption.previousElementSibling && /texto sugerido/i.test(caption.previousElementSibling.textContent) ? caption.previousElementSibling : null;
    const tip = caption.nextElementSibling && /publica|💡/i.test(caption.nextElementSibling.textContent) ? caption.nextElementSibling : null;
    const pop = document.createElement("div");
    pop.className = "caption-pop";
    pop.hidden = true;
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-label", "Texto sugerido para la publicación");
    pop.innerHTML = '<header><strong>💬 Texto sugerido</strong><button type="button" class="caption-close" aria-label="Cerrar">✕</button></header><div class="caption-body"></div><footer></footer>';
    pop.querySelector(".caption-body").append(caption);
    if (tip) pop.querySelector(".caption-body").append(tip);
    if (heading) heading.remove();
    const copy = [...actions.querySelectorAll("button, a")].find((b) => /copiar/i.test(b.textContent));
    if (copy) {
        const copyHere = document.createElement("button");
        copyHere.type = "button";
        copyHere.className = "btn btn-small btn-primary";
        copyHere.textContent = "📋 Copiar";
        copyHere.addEventListener("click", () => { copy.click(); copyHere.textContent = "✓ Copiado"; setTimeout(() => { copyHere.textContent = "📋 Copiar"; }, 1500); });
        pop.querySelector("footer").appendChild(copyHere);
    }
    document.body.appendChild(pop);
    const show = document.createElement("button");
    show.type = "button";
    show.className = "btn btn-secondary caption-open";
    show.textContent = "💬 Texto sugerido";
    actions.appendChild(show);
    const close = () => { pop.hidden = true; show.setAttribute("aria-expanded", "false"); };
    show.addEventListener("click", (event) => { event.stopPropagation(); pop.hidden = !pop.hidden; show.setAttribute("aria-expanded", String(!pop.hidden)); });
    pop.querySelector(".caption-close").addEventListener("click", close);
    document.addEventListener("click", (event) => { if (!pop.hidden && !pop.contains(event.target) && event.target !== show) close(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
})();
