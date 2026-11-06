import { languageColor } from "./model.js";
import { Color } from "three";
import { stackMetrics } from "./glass-scene.js";
const escape = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
// Vector isometric renderer for devices without WebGL. Uses exactly the same repository metrics.
export function glassFallback(canvas, repos, onSelect) {
  const colors = [
    "#83f4d4",
    "#91beff",
    "#a99fe9",
    "#71e0e0",
    "#eca0c2",
    "#edca8a",
  ];
  const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  el.setAttribute("viewBox", "0 0 720 560");
  el.setAttribute("class", "vector-glass");
  el.setAttribute("role", "group");
  el.setAttribute("aria-label", "Isometric glass repository stacks");
  const items = repos.slice(0, 24),
    cols = Math.max(1, Math.ceil(Math.sqrt(items.length)));
  let parts = [];
  const center = 360,
    ground = 300,
    gap = 68;
  const project = (x, y, z) => [
    center + (x - z) * 0.86,
    ground + (x + z) * 0.43 - y,
  ];
  const poly = (points, fill, stroke, extra = "") =>
    `<polygon points="${points.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ")}" fill="${fill}" stroke="${stroke}" stroke-width=".8" ${extra}/>`;
  const base = [
    project(-170, 0, -170),
    project(170, 0, -170),
    project(170, 0, 170),
    project(-170, 0, 170),
  ];
  parts.push(poly(base, "url(#ground)", "#25484b"));
  for (let i = -150; i <= 150; i += 30) {
    const a = project(i, 0, -170),
      b = project(i, 0, 170),
      c = project(-170, 0, i),
      d = project(170, 0, i);
    parts.push(
      `<path d="M${a} L${b} M${c} L${d}" stroke="#33565c" stroke-width=".5" opacity=".45"/>`,
    );
  }
  items
    .map((repo, i) => ({
      repo,
      i,
      x: ((i % cols) - (cols - 1) / 2) * gap,
      z:
        (Math.floor(i / cols) - (Math.ceil(items.length / cols) - 1) / 2) * gap,
    }))
    .sort((a, b) => a.x + a.z - (b.x + b.z))
    .forEach(({ repo, i, x, z }) => {
      const m = stackMetrics(repo),
        w = m.width * 10.5,
        color =
          "#" +
          new Color(languageColor(repo.language || "Unknown")).getHexString(),
        top = m.layers * 6.3;
      let slabs = "";
      for (let j = 0; j < m.layers; j++) {
        const y = 6 + j * 6.3;
        const a = project(x - w, y, z - w),
          b = project(x + w, y, z - w),
          c = project(x + w, y, z + w),
          d = project(x - w, y, z + w),
          ad = project(x - w, y - 4, z - w),
          bd = project(x + w, y - 4, z - w),
          cd = project(x + w, y - 4, z + w),
          dd = project(x - w, y - 4, z + w),
          co = j < m.layers * 0.22 ? "#cf4c9b" : color;
        slabs += poly([d, c, cd, dd], co + "38", co + "aa");
        slabs += poly([b, c, cd, bd], co + "66", co + "a0");
        slabs += poly([a, b, c, d], color + "38", co + "b0");
        slabs += `<path d="M${d} L${c}" stroke="${co}" stroke-width="1.4" opacity=".8"/>`;
      }
      const cap = [
        project(x - w - 2, top + 8, z - w - 2),
        project(x + w + 2, top + 8, z - w - 2),
        project(x + w + 2, top + 8, z + w + 2),
        project(x - w - 2, top + 8, z + w + 2),
      ];
      slabs += poly(cap, "#143b43e0", "#adfff3");
      const at = project(x, top + 33, z);
      slabs += `<circle cx="${at[0]}" cy="${at[1] - 10}" r="17" fill="${color}" opacity=".06" filter="url(#glow)"/><text x="${at[0]}" y="${at[1]}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="${color}" letter-spacing="1">${repo.commits ?? "?"}</text>`;
      const label = project(x, 0, z);
      slabs += `<text x="${label[0]}" y="${label[1] + 28}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#a6c7c2">${escape(repo.name.slice(0, 19))}</text>`;
      parts.push(
        `<g class="svg-stack" data-repo="${i}" tabindex="0" role="button" aria-label="${escape(repo.name)}; ${repo.commits ?? "unknown"} commits; ${repo.stars || 0} stars" style="animation-delay:${i * 0.06}s"><title>${escape(repo.name)} · ${repo.commits ?? "unknown"} commits · ${repo.stars || 0} stars</title>${slabs}</g>`,
      );
    });
  const particles = Array.from(
    { length: 45 },
    (_, i) =>
      `<circle cx="${70 + (Math.sin(i * 139) + 1) * 285}" cy="${35 + (Math.cos(i * 71) + 1) * 220}" r="${i % 3 === 0 ? 1.2 : 0.6}" fill="#9af3d2" opacity="${0.15 + (i % 5) * 0.07}"/>`,
  ).join("");
  el.innerHTML = `<defs><linearGradient id="ground" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#163139" stop-opacity=".8"/><stop offset="1" stop-color="#0b1b26" stop-opacity=".3"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="8"/></filter>${colors.map((c, i) => `<linearGradient id="slab${i}"><stop stop-color="${c}" stop-opacity=".16"/><stop offset=".5" stop-color="${c}" stop-opacity=".4"/><stop offset="1" stop-color="#143e48" stop-opacity=".5"/></linearGradient>`).join("")}</defs>${particles}${parts.join("")}`;
  canvas.replaceWith(el);
  el.querySelectorAll("[data-repo]").forEach((g) => {
    const select = () => onSelect(items[+g.dataset.repo]);
    g.onclick = select;
    g.onkeydown = (e) => {
      if (["Enter", " "].includes(e.key)) {
        e.preventDefault();
        select();
      }
    };
  });
  return {
    download() {
      const source = new XMLSerializer().serializeToString(el);
      const url = URL.createObjectURL(
        new Blob([source], { type: "image/svg+xml" }),
      );
      const a = document.createElement("a");
      a.download = "codeverse-glass-stacks.svg";
      a.href = url;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    build() {},
    destroy() {
      el.remove();
    },
  };
}
