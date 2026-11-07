/* GastroInsight AI · Avisos flotantes del equipo (alertas por rol, con "Voy" y sonido opcional). */
(function () {
    "use strict";
    const root = document.body;
    const url = root.dataset.alertsUrl;
    if (!url || root.dataset.embed === "1") return;
    const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
    const seenKey = "gi-alerts-seen";
    const soundKey = "gi-alert-sound";
    let seen = new Set(JSON.parse(sessionStorage.getItem(seenKey) || "[]"));
    const stack = document.createElement("div");
    stack.className = "toast-stack";
    stack.setAttribute("aria-live", "polite");
    document.body.appendChild(stack);
    const bell = document.getElementById("notif-count");

    const soundOn = () => { try { return localStorage.getItem(soundKey) === "on"; } catch (e) { return false; } };
    function beep(level) {
        if (!soundOn()) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.frequency.value = level === "danger" ? 880 : 660;
            gain.gain.value = 0.08;
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start(); osc.stop(ctx.currentTime + 0.18);
        } catch (e) { /* sin audio */ }
    }

    function toast(item) {
        const el = document.createElement("div");
        el.className = `toast level-${item.level}`;
        el.innerHTML = `<span class="toast-icon"></span><div class="toast-body"><strong></strong><small></small></div>
            <div class="toast-actions"><button type="button" class="btn btn-small btn-primary">Voy</button>
            <button type="button" class="toast-close" aria-label="Cerrar">✕</button></div>`;
        el.querySelector(".toast-icon").textContent = item.icon;
        el.querySelector("strong").textContent = item.title;
        el.querySelector("small").textContent = item.message;
        const close = () => { el.classList.add("is-leaving"); setTimeout(() => el.remove(), 250); };
        el.querySelector(".toast-close").addEventListener("click", close);
        el.querySelector(".btn").addEventListener("click", async () => {
            try {
                await fetch(item.ack_url, { method: "POST", credentials: "same-origin",
                    headers: { "X-CSRFToken": decodeURIComponent(csrf), "X-Requested-With": "fetch" } });
            } catch (e) { /* se reintenta con el panel */ }
            close();
        });
        stack.prepend(el);
        while (stack.children.length > 4) stack.lastElementChild.remove();
        if (item.level !== "danger") setTimeout(close, 12000);
        beep(item.level);
        if (item.level === "danger" && navigator.vibrate) navigator.vibrate([120, 60, 120]);
    }

    async function poll() {
        try {
            const response = await fetch(url, { credentials: "same-origin" });
            if (!response.ok) return;
            const data = await response.json();
            if (bell) { bell.textContent = data.count ? String(data.count) : ""; bell.hidden = !data.count; }
            data.items.slice().reverse().forEach((item) => {
                if (!seen.has(item.id)) { seen.add(item.id); toast(item); }
            });
            sessionStorage.setItem(seenKey, JSON.stringify([...seen].slice(-200)));
        } catch (e) { /* sin conexión: se reintenta */ }
    }

    document.addEventListener("click", (event) => {
        const toggle = event.target.closest("#sound-toggle");
        if (!toggle) return;
        try { localStorage.setItem(soundKey, soundOn() ? "off" : "on"); } catch (e) { /* sin almacenamiento */ }
        toggle.textContent = soundOn() ? "🔊 Sonido activado" : "🔈 Sonido";
        if (soundOn()) beep("info");
    });
    const toggle = document.getElementById("sound-toggle");
    if (toggle) toggle.textContent = soundOn() ? "🔊 Sonido activado" : "🔈 Sonido";

    poll();
    setInterval(poll, 6000);
})();
