import test from "node:test";
import assert from "node:assert/strict";
import {
  parseCSV,
  companyRows,
  normalizeSkill,
  validateFlowImport,
  uniqueId,
} from "../src/glass-ui-utils.js";
test("company CSV preserves quoted commas, newlines and escaped quotes", () => {
  const rows = parseCSV(
    '\uFEFFname,url,provider,board\r\n"ACME, Inc.",https://example.org/careers,lever,acme\r\n"Two\nLines",https://example.org/other,,\r\n',
  );
  assert.equal(rows[0].name, "ACME, Inc.");
  assert.equal(rows[1].name, "Two\nLines");
  assert.equal(companyRows(rows).length, 2);
  assert.equal(
    parseCSV('name\n"A ""quoted"" name"')[0].name,
    'A "quoted" name',
  );
});
test("bad CSV and non-HTTPS company destinations fail before importing", () => {
  assert.throws(() => parseCSV('name,url\n"unterminated'));
  assert.throws(() => parseCSV("name,name\nx,y"));
  assert.throws(() => parseCSV("name,url\nx"));
  assert.throws(() =>
    companyRows([{ name: "Test", url: "javascript:alert(1)" }]),
  );
  assert.throws(() =>
    companyRows([
      { name: "Test", url: "https://example.org", provider: "arbitrary" },
    ]),
  );
});
test("C-family skills remain distinct in the interface", () => {
  assert.deepEqual(["C", "C++", "C#"].map(normalizeSkill), [
    "c",
    "cpp",
    "csharp",
  ]);
});
test("workflow import rejects cycles and missing datasets", () => {
  const base = { schema: "codeverse.flow/1", datasets: [], nodes: [] };
  assert.throws(() =>
    validateFlowImport({
      ...base,
      nodes: [
        { id: "a", kind: "python", inputs: ["b"] },
        { id: "b", kind: "python", inputs: ["a"] },
      ],
    }),
  );
  assert.throws(() =>
    validateFlowImport({
      ...base,
      nodes: [{ id: "a", kind: "dataset", dataset: "missing" }],
    }),
  );
  assert.equal(
    validateFlowImport({
      ...base,
      datasets: [{ id: "data" }],
      nodes: [{ id: "a", kind: "dataset", dataset: "data", inputs: [] }],
    }).nodes.length,
    1,
  );
});

test("UUID generation works when randomUUID is absent", () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  const fake = {
    getRandomValues: (b) => {
      b.fill(7);
      return b;
    },
  };
  Object.defineProperty(globalThis, "crypto", {
    value: fake,
    configurable: true,
  });
  try {
    assert.match(
      uniqueId(),
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  } finally {
    if (original) Object.defineProperty(globalThis, "crypto", original);
    else delete globalThis.crypto;
  }
});
