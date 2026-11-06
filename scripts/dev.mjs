import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
const root = process.cwd();
for (const name of [".env.deploy", ".env.security"])
  if (existsSync(name)) {
    process.loadEnvFile(name);
    break;
  }
const previewDependencies = path.join(root, ".dev-python");
const localPython = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const python =
  process.env.CODEVERSE_PYTHON ||
  (existsSync(previewDependencies)
    ? "/usr/bin/python3"
    : existsSync(localPython)
      ? localPython
      : process.platform === "win32"
        ? "python"
        : "python3");
const api = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "services.api.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
    "--no-access-log",
  ],
  {
    cwd: root,
    stdio: "inherit",
    env: {
      ...process.env,
      CODEVERSE_SECURE_MODE: process.env.CODEVERSE_SECURE_MODE || "1",
      ...(existsSync(previewDependencies)
        ? { PYTHONPATH: previewDependencies }
        : {}),
    },
  },
);
api.on("error", (error) =>
  console.error(
    "Backend could not start:",
    error.message,
    "Install Python requirements into .venv first.",
  ),
);
api.on("exit", (code) => {
  if (code)
    console.error(
      "Backend exited. Install requirements and configure .env.deploy; public GitHub discovery needs the API.",
    );
});
let ready = false;
for (let i = 0; i < 40; i++) {
  try {
    const r = await fetch("http://127.0.0.1:8000/api/health");
    if (r.ok) {
      ready = true;
      break;
    }
  } catch {}
  await new Promise((r) => setTimeout(r, 100));
}
if (!ready)
  console.error(
    "API is not ready on port 8000. Frontend will show its connection status.",
  );
const vite = spawn(
  process.execPath,
  [path.join(root, "node_modules/vite/bin/vite.js"), ...process.argv.slice(2)],
  { cwd: root, stdio: "inherit", env: process.env },
);
function stop() {
  api.kill("SIGTERM");
  vite.kill("SIGTERM");
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
vite.on("exit", (code) => {
  api.kill("SIGTERM");
  process.exit(code || 0);
});
