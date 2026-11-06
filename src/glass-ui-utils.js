export function uniqueId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const b = globalThis.crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 15) | 64;
  b[8] = (b[8] & 63) | 128;
  const h = [...b].map((v) => v.toString(16).padStart(2, "0"));
  return (
    h.slice(0, 4).join("") +
    "-" +
    h.slice(4, 6).join("") +
    "-" +
    h.slice(6, 8).join("") +
    "-" +
    h.slice(8, 10).join("") +
    "-" +
    h.slice(10).join("")
  );
}
export const normalizeSkill = (value) => {
  const raw = String(value || "")
    .trim()
    .toLowerCase();
  const special = {
    "c++": "cpp",
    "c#": "csharp",
    "node.js": "nodejs",
    "node-js": "nodejs",
    "next.js": "nextjs",
  };
  return special[raw] || raw.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
};
export function parseCSV(text) {
  const rows = [];
  let row = [],
    cell = "",
    quoted = false;
  const source = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (c === '"') {
      if (quoted && source[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (!quoted && cell !== "")
        throw new Error("Quote inside an unquoted CSV cell");
      else quoted = !quoted;
    } else if (c === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((c === "\n" || c === "\r") && !quoted) {
      if (c === "\r" && source[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some(Boolean)) rows.push(row);
      row = [];
      cell = "";
    } else cell += c;
  }
  if (quoted) throw new Error("CSV has an unterminated quoted field");
  row.push(cell);
  if (row.some(Boolean)) rows.push(row);
  if (!rows.length) return [];
  const keys = rows.shift().map((k) => k.trim().toLowerCase());
  if (new Set(keys).size !== keys.length)
    throw new Error("CSV column names must be unique");
  return rows.map((r) => {
    if (r.length !== keys.length)
      throw new Error("CSV row has a different number of columns");
    return Object.fromEntries(keys.map((key, i) => [key, r[i]]));
  });
}
export function validateFlowImport(value) {
  if (
    value?.schema !== "codeverse.flow/1" ||
    !Array.isArray(value.nodes) ||
    !Array.isArray(value.datasets) ||
    value.nodes.length > 40 ||
    value.datasets.length > 30
  )
    throw new Error("Invalid workflow format");
  const allowed = new Set(["python", "dataset", "gmail", "http"]);
  const ids = new Set();
  for (const node of value.nodes) {
    if (
      !/^[A-Za-z0-9_-]{1,80}$/.test(node.id) ||
      ids.has(node.id) ||
      !allowed.has(node.kind) ||
      !Array.isArray(node.inputs || [])
    )
      throw new Error("Workflow contains invalid or duplicate boxes");
    ids.add(node.id);
  }
  const done = new Set();
  const pending = [...value.nodes];
  while (pending.length) {
    const ready = pending.filter((n) =>
      (n.inputs || []).every((id) => done.has(id)),
    );
    if (!ready.length)
      throw new Error("Workflow has a cycle or missing connection");
    for (const n of ready) {
      done.add(n.id);
      pending.splice(pending.indexOf(n), 1);
    }
  }
  const datasets = new Set(value.datasets.map((d) => d.id));
  if (datasets.size !== value.datasets.length)
    throw new Error("Dataset identifiers must be unique");
  for (const n of value.nodes)
    if (n.kind === "dataset" && !datasets.has(n.dataset))
      throw new Error("Dataset box refers to a missing file");
  return value;
}
export function companyRows(rows) {
  if (rows.length > 100) throw new Error("Maximum 100 companies");
  return rows.map((r) => {
    let u;
    try {
      u = new URL(r.url);
    } catch {
      throw new Error("Each company needs a valid career page URL");
    }
    if (u.protocol !== "https:" || !r.name?.trim())
      throw new Error("Company name and HTTPS URL are required");
    if (!["", "greenhouse", "lever"].includes((r.provider || "").toLowerCase()))
      throw new Error("Provider must be greenhouse, lever or empty");
    return {
      id: uniqueId(),
      name: r.name.trim(),
      url: u.href,
      provider: (r.provider || "").toLowerCase(),
      board: r.board || "",
    };
  });
}
