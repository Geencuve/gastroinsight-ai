/* GastroInsight AI · Miniaturas esquemáticas anónimas (solo coordenadas y métricas). */
window.GIThumb = (function () {
    "use strict";
    const color = (ieo) => (ieo == null ? "#8a93a7" : ieo >= 65 ? "#34d399" : ieo >= 45 ? "#fbbf24" : "#fb7185");
    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const SPOTS = [[45, 51], [115, 51], [80, 24], [80, 78], [58, 27], [102, 27], [58, 75], [102, 75]];

    function svg(d) {
        const W = 160, H = 100, c = color(d.ieo);
        let shapes = "";
        const boxes = (d.boxes || []).filter((b) => Array.isArray(b) && b.length >= 5);
        if (boxes.length) {
            boxes.filter((b) => b[4] === "t").forEach((b) => {
                shapes += `<rect x="${((b[0] - b[2] / 2) * W).toFixed(1)}" y="${((b[1] - b[3] / 2) * H).toFixed(1)}" width="${(b[2] * W).toFixed(1)}" height="${(b[3] * H).toFixed(1)}" rx="5" fill="rgba(148,163,184,.30)" stroke="rgba(148,163,184,.75)"/>`;
            });
            boxes.filter((b) => b[4] === "p").forEach((b) => {
                const r = Math.max(4, Math.min(11, (b[2] * W) / 3));
                shapes += `<circle cx="${(b[0] * W).toFixed(1)}" cy="${((b[1] - b[3] / 4) * H).toFixed(1)}" r="${r.toFixed(1)}" fill="${c}" fill-opacity=".9"/>`;
            });
        } else {
            shapes += `<rect x="55" y="38" width="50" height="26" rx="6" fill="rgba(148,163,184,.30)" stroke="rgba(148,163,184,.75)"/>`;
            const n = Math.max(0, Math.round(d.scene_people ?? d.people ?? d.occupancy ?? 0));
            for (let i = 0; i < Math.min(n, SPOTS.length); i += 1) {
                shapes += `<circle cx="${SPOTS[i][0]}" cy="${SPOTS[i][1]}" r="7" fill="${c}" fill-opacity=".9"/>`;
            }
        }
        let grid = "";
        for (let x = 20; x < W; x += 20) grid += `<line x1="${x}" y1="0" x2="${x}" y2="${H}" stroke="rgba(148,163,184,.12)"/>`;
        for (let y = 20; y < H; y += 20) grid += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="rgba(148,163,184,.12)"/>`;
        return `<svg viewBox="0 0 ${W} ${H}" class="thumb-svg" role="img" aria-label="Esquema anónimo de ${esc(d.name)}">` +
               `<rect width="${W}" height="${H}" fill="rgba(15,23,42,.05)"/>${grid}${shapes}</svg>`;
    }

    function mini(d) {
        return `<div class="chat-thumb">${svg(d)}<small><strong>${esc(d.name)}</strong> · IEO ${d.ieo ?? "—"}</small></div>`;
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".chat-thumbs[data-thumbs-id]").forEach((box) => {
            const source = document.getElementById(box.dataset.thumbsId);
            if (!source) return;
            try { box.innerHTML = JSON.parse(source.textContent).map(mini).join(""); } catch (e) { /* datos inválidos */ }
        });
    });
    return { svg, mini, color };
})();
