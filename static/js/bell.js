/* GastroInsight AI · Campana de alertas global y botón de tema en la esquina superior derecha. */
(function () {
    "use strict";
    if (document.body.dataset.embed === "1" || !document.querySelector(".app-sidebar")) return;
    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const feed = document.body.dataset.alertsUrl;
    const main = document.querySelector("main");
    const nowBox = main && main.querySelector(".now-box");
    const csrf = decodeURIComponent((document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "");

    const bar = document.createElement("div");
    bar.className = "top-actions";
    document.body.appendChild(bar);

    if (feed || nowBox) {
        const bell = document.createElement("div");
        bell.className = "home-bell";
        bell.innerHTML = `<button type="button" class="home-bell-btn" aria-expanded="false" aria-label="Alertas"><span class="bell-glyph">🔔</span><span class="home-bell-count" hidden></span></button>
            <div class="home-bell-panel" hidden><header><div class="bell-head-text"><strong>Alertas</strong><small class="home-bell-sub"></small></div><button type="button" class="bell-sound" aria-pressed="false"></button></header><div class="home-bell-list"></div></div>`;
        bar.appendChild(bell);
        const button = bell.querySelector(".home-bell-btn");
        const panel = bell.querySelector(".home-bell-panel");
        const list = bell.querySelector(".home-bell-list");
        const SOUND = "gi-alert-sound";
        const sound = bell.querySelector(".bell-sound");
        const soundOn = () => { try { return localStorage.getItem(SOUND) === "on"; } catch (e) { return false; } };
        const paintSound = () => {
            const on = soundOn();
            sound.textContent = on ? "🔊" : "🔇";
            sound.title = on ? "Sonido activado: toca para silenciar" : "Sonido desactivado: toca para activarlo";
            sound.setAttribute("aria-label", sound.title);
            sound.setAttribute("aria-pressed", String(on));
        };
        sound.addEventListener("click", (event) => {
            event.stopPropagation();
            try { localStorage.setItem(SOUND, soundOn() ? "off" : "on"); } catch (e) { /* sin almacenamiento */ }
            paintSound();
            if (!soundOn()) return;
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.frequency.value = 660;
                gain.gain.value = 0.08;
                osc.connect(gain); gain.connect(ctx.destination);
                osc.start(); osc.stop(ctx.currentTime + 0.18);
            } catch (e) { /* sin audio */ }
        });
        paintSound();
        const live = new Map();

        function card(item, isLive) {
            const article = document.createElement("article");
            article.className = `bell-card level-${item.level || "warning"}`;
            article.innerHTML = `<div class="bell-icon">${esc(item.icon)}</div><div class="bell-body"><strong>${esc(item.title)}</strong>
                ${item.action ? `<p><b>Qué hacer:</b> ${esc(item.action)}</p>` : ""}<div class="bell-actions"></div></div>`;
            const actions = article.querySelector(".bell-actions");
            if (item.href) actions.insertAdjacentHTML("beforeend", `<a class="btn btn-small btn-primary" href="${esc(item.href)}">Ir ahora</a>`);
            if (isLive && item.ack_url) {
                const go = document.createElement("button");
                go.type = "button";
                go.className = "btn btn-small btn-primary";
                go.textContent = "Voy";
                go.addEventListener("click", async () => {
                    try { await fetch(item.ack_url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" } }); } catch (e) { /* se reintenta */ }
                    article.remove();
                    refresh();
                });
                actions.appendChild(go);
            }
            return article;
        }

        function refresh() {
            const total = list.querySelectorAll(".bell-card").length;
            const count = bell.querySelector(".home-bell-count");
            count.hidden = !total;
            count.textContent = String(total);
            button.classList.toggle("has-alerts", total > 0);
            bell.querySelector(".bell-glyph").textContent = total ? "🔔" : "✓";
            bell.querySelector(".home-bell-sub").textContent = total ? `${total} pendiente${total === 1 ? "" : "s"}` : "";
            list.querySelectorAll(".bell-empty").forEach((e) => e.remove());
            if (!total) list.insertAdjacentHTML("beforeend", '<p class="bell-empty">✅ Todo en orden. No hay nada pendiente.</p>');
        }

        if (nowBox) {
            nowBox.querySelectorAll("li").forEach((li) => {
                const strong = li.querySelector("strong");
                const link = li.querySelector("a[href]");
                const full = li.textContent;
                const title = strong ? strong.textContent.trim() : full.trim();
                const icon = strong ? full.slice(0, full.indexOf(strong.textContent)).trim() : "⚠️";
                const action = strong ? full.slice(full.indexOf(strong.textContent) + strong.textContent.length)
                    .replace(link ? link.textContent : "", "").replace(/^\s*—\s*/, "").trim() : "";
                list.appendChild(card({ icon: icon || "⚠️", title, action, href: link ? link.href : null }, false));
            });
            nowBox.remove();
        }

        async function poll() {
            if (!feed) return;
            try {
                const response = await fetch(feed, { credentials: "same-origin" });
                if (!response.ok) return;
                const data = await response.json();
                const ids = new Set();
                (data.items || []).forEach((item) => {
                    ids.add(item.id);
                    if (!live.has(item.id)) {
                        const element = card({ icon: item.icon, title: item.title, action: item.message, level: item.level, ack_url: item.ack_url }, true);
                        live.set(item.id, element);
                        list.prepend(element);
                    }
                });
                live.forEach((element, id) => { if (!ids.has(id)) { element.remove(); live.delete(id); } });
                refresh();
            } catch (e) { /* sin conexión: se reintenta */ }
        }
        refresh();
        poll();
        setInterval(poll, 15000);

        const close = () => { panel.hidden = true; button.setAttribute("aria-expanded", "false"); };
        button.addEventListener("click", (event) => { event.stopPropagation(); panel.hidden = !panel.hidden; button.setAttribute("aria-expanded", String(!panel.hidden)); });
        document.addEventListener("click", (event) => { if (!bell.contains(event.target)) close(); });
        document.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
    }

    const theme = document.getElementById("theme-toggle");
    if (theme) bar.appendChild(theme);
})();
