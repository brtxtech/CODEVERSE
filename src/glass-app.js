import "./glass-app.css";
import { createClient } from "@supabase/supabase-js";
import { createGlassScene } from "./glass-scene.js";
import { glassFallback } from "./glass-fallback.js";
import {
  parseCSV,
  companyRows,
  validateFlowImport,
  normalizeSkill,
  uniqueId,
} from "./glass-ui-utils.js";
import { parseGitHubOwner } from "./github-onboarding-data.js";
const $ = (s) => document.querySelector(s),
  esc = (v) =>
    String(v ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
const safeURL = (v) => {
  try {
    const u = new URL(v);
    return u.protocol === "https:" ? esc(u.href) : "#";
  } catch {
    return "#";
  }
};
const app = $("#app");
let scene,
  auth,
  session,
  me,
  workspace = { payload: {}, revision: 0 },
  dashboard,
  publicData,
  catalog = [],
  taxonomy = [],
  view = "Home",
  busy = false,
  integrationState = null,
  offerLocation = "",
  catalogSort = "match",
  projectCategory = "";
const illustration = [
  { name: "interface", commits: 180, stars: 450, language: "TypeScript" },
  { name: "network-core", commits: 1300, stars: 2300, language: "C" },
  { name: "research", commits: 65, stars: 160, language: "Python" },
  { name: "api-engine", commits: 580, stars: 800, language: "Python" },
  { name: "automation", commits: 120, stars: 420, language: "JavaScript" },
  { name: "data-lab", commits: 900, stars: 1500, language: "Python" },
  { name: "cloud-kit", commits: 45, stars: 82, language: "Go" },
  { name: "visualizer", commits: 250, stars: 670, language: "TypeScript" },
  { name: "next-project", commits: 12, stars: 30, language: "Rust" },
];
const notify = (msg, error = false) => {
  document.querySelector(".notice")?.remove();
  const n = document.createElement("div");
  n.className = "notice" + (error ? " error" : "");
  n.setAttribute("role", "status");
  n.textContent = msg;
  document.body.append(n);
  setTimeout(() => n.remove(), 9000);
};
async function api(path, body, method = "POST", extra = {}) {
  const r = await fetch("/api/" + path, {
    method: body === undefined ? "GET" : method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(session ? { Authorization: "Bearer " + session.access_token } : {}),
      ...extra,
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const d = await r.json().catch(() => ({
    detail:
      "The API is unavailable. Start the backend or check the deployment configuration.",
  }));
  if (!r.ok) {
    if (r.status === 409 && /reload|changed|conflict/i.test(String(d.detail)))
      document.dispatchEvent(new Event("workspace-conflict"));
    throw new Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail || d),
    );
  }
  return d;
}
async function action(fn) {
  if (busy) return;
  busy = true;
  try {
    await fn();
  } catch (e) {
    notify(e.message, true);
  } finally {
    ((busy = false),
      (integrationState = null),
      (offerLocation = ""),
      (catalogSort = "match"),
      (projectCategory = ""));
    document.querySelectorAll("button[data-busy]").forEach((b) => {
      b.disabled = false;
      delete b.dataset.busy;
    });
  }
}
const brand = () =>
  '<a class="brand" href="/"><span class="brand-icon"></span>CODEVERSE<span style="color:#7ca198;font-size:9px;letter-spacing:1px"> / GLASS</span></a>';
const topbar = () =>
  `<header class="topbar">${me ? `<span class="eyebrow">YOUR PERSONAL DEVELOPER UNIVERSE</span>` : brand()}<nav class="nav">${me ? '<button class="flat" data-nav-projects>Discover projects</button>' : '<a href="#discover">Discover projects</a>'}<span class="live">GitHub powered</span>${me ? `<span class="avatar">${esc((me.profile.github_username || "U")[0].toUpperCase())}</span><span>@${esc(me.profile.github_username)}</span><button id="signout-mobile" class="mobile-only">Sign out</button>` : '<span class="chip">BUILD YOUR NEXT CHAPTER ↗</span>'}</nav></header>`;
function footer() {
  return '<footer class="footer"><span>CODEVERSE © 2026 · Made for what comes next.</span><span>Code is evidence. Curiosity is the beginning.</span></footer>';
}
function repoCards(repos, create = false) {
  return repos
    .map(
      (r, i) =>
        `<article class="card"><div class="row"><span class="chip ${i % 2 ? "blue" : ""}">${esc(r.category)}</span><span class="muted">↗</span></div><h3><a href="${safeURL(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.id)}</a></h3><p>${esc(r.match_score ? "Matches " + r.reason : r.description)}</p><div class="tags">${r.search_text
          .split(" ")
          .slice(0, 5)
          .map((s) => `<span class="chip blue">${esc(s)}</span>`)
          .join(
            "",
          )}</div><div class="repo-bottom"><span data-metric="${esc(r.id)}">${r.stars == null ? "☆ Stars not fetched" : "☆ " + Number(r.stars).toLocaleString()}</span><button data-refresh="${esc(r.id)}">Refresh ☆</button>${create ? `<button data-create="${esc(r.id)}">Build this ↗</button>` : ""}</div></article>`,
    )
    .join("");
}
function bindRepoCards() {
  document.querySelectorAll("[data-refresh]").forEach(
    (b) =>
    (b.onclick = () =>
      action(async () => {
        b.disabled = true;
        b.dataset.busy = "1";
        const d = await api(
          "v1/glass/catalog/metrics?repository=" +
          encodeURIComponent(b.dataset.refresh),
        );
        Object.assign(
          catalog.find((r) => r.id === b.dataset.refresh) || {},
          d,
        );
        Object.assign(
          dashboard?.recommendations.find(
            (r) => r.id === b.dataset.refresh,
          ) || {},
          d,
        );
        document.querySelectorAll("[data-metric]").forEach((x) => {
          if (x.dataset.metric === b.dataset.refresh)
            x.textContent = `☆ ${d.stars.toLocaleString()} · ${d.license || "license unknown"}${d.archived ? " · archived" : ""}`;
        });
      })),
  );
  document
    .querySelectorAll("[data-create]")
    .forEach((b) => (b.onclick = () => projectModal(b.dataset.create)));
}
function attachScene(repos) {
  const host = document.querySelector(".scene-wrap");
  if (!host) return;
  let page = 0;
  const select = (repo) => {
    const out = $("#selected");
    if (out)
      out.innerHTML = `<strong>${esc(repo.name)}</strong>${repo.commits ?? "Unknown"} commits · ☆ ${repo.stars ?? 0}<br>${esc(repo.language || "Unknown language")}${repo.url ? ` · <a target="_blank" rel="noopener noreferrer" href="${safeURL(repo.url)}">Open repository ↗</a>` : ""}`;
  };
  function draw() {
    scene?.destroy();
    host.querySelector("#glass,.vector-glass")?.remove();
    const canvas = document.createElement("canvas");
    canvas.id = "glass";
    canvas.setAttribute("aria-label", "Interactive repository glass stacks");
    host.querySelector(".scene-heading").after(canvas);
    try {
      scene = createGlassScene(canvas, select);
      scene.build(repos.slice(page * 24, page * 24 + 24));
    } catch {
      scene = glassFallback(
        canvas,
        repos.slice(page * 24, page * 24 + 24),
        select,
      );
    }
    const label = host.querySelector("[data-stack-page]");
    if (label)
      label.textContent = `${repos.length ? page * 24 + 1 : 0}–${Math.min(repos.length, page * 24 + 24)} of ${repos.length}`;
    host
      .querySelector("[data-stack-prev]")
      ?.toggleAttribute("disabled", page === 0);
    host
      .querySelector("[data-stack-next]")
      ?.toggleAttribute("disabled", (page + 1) * 24 >= repos.length);
  }
  host.querySelector(".stack-pages")?.remove();
  if (repos.length > 24) {
    const control = document.createElement("div");
    control.className = "stack-pages";
    control.innerHTML =
      '<button data-stack-prev aria-label="Previous repository stacks">←</button><small data-stack-page></small><button data-stack-next aria-label="Next repository stacks">→</button>';
    host.append(control);
    control.querySelector("[data-stack-prev]").onclick = () => {
      page = Math.max(0, page - 1);
      draw();
    };
    control.querySelector("[data-stack-next]").onclick = () => {
      page = Math.min(Math.ceil(repos.length / 24) - 1, page + 1);
      draw();
    };
  }
  draw();
  if (!host.querySelector(".scene-export")) {
    const b = document.createElement("button");
    b.className = "scene-export";
    b.textContent = "Save view ↓";
    b.onclick = () => scene?.download?.();
    host.append(b);
  }
}

function sceneMarkup(title, sub) {
  return `<div class="scene-wrap"><div class="scene-heading">${esc(title)}<span>${esc(sub)}</span></div><canvas id="glass" aria-label="Interactive glass repository stacks; repository list follows"></canvas><div class="scene-tag" id="selected"><strong>Every layer tells a story.</strong>Height grows with commits.<br>Width grows with stars. Drag to orbit.</div></div>`;
}
function render() {
  scene?.destroy();
  scene = null;
  if (!me) return landing();
  history.replaceState(
    null,
    "",
    location.pathname + location.search + "#view=" + encodeURIComponent(view),
  );
  app.innerHTML = `<aside class="side">${brand()}${[
    "Home",
    "Career dashboard",
    "Projects",
    "Job opportunities",
    "Applications",
    "Automation",
    "Connections",
    "Security",
  ]
    .filter((x) => x !== "Security" || me.profile.role === "security_admin")
    .map(
      (name, i) =>
        `<button data-view="${name}" class="${name === view ? "active" : ""}">${["◈", "◷", "▱", "↗", "✓", "⌘", "⚙", "◇"][i]} &nbsp; ${name}</button>`,
    )
    .join(
      "",
    )}<div class="account"><span class="eyebrow">${esc(me.profile.role.replaceAll("_", " "))}</span><p style="margin:8px 0">@${esc(me.profile.github_username)}</p><button id="signout">Sign out ↗</button></div></aside><main class="workspace">${topbar()}<div id="page"></div>${footer()}</main>`;
  document.querySelectorAll("[data-view]").forEach(
    (b) =>
    (b.onclick = () => {
      view = b.dataset.view;
      render();
    }),
  );
  $("#signout").onclick = () =>
    action(async () => {
      await auth.auth.signOut();
      me = null;
      session = null;
      publicData = null;
      workspace = { payload: {}, revision: 0 };
      landing();
    });
  document
    .querySelector("#signout-mobile")
    ?.addEventListener("click", () => $("#signout").click());
  document
    .querySelector("[data-nav-projects]")
    ?.addEventListener("click", () => {
      view = "Projects";
      render();
    });
  if (view === "Home") home();
  else if (view === "Career dashboard") career();
  else if (view === "Projects") projects();
  else if (view === "Job opportunities") jobs();
  else if (view === "Applications") applications();
  else if (view === "Automation") automation();
  else if (view === "Connections") connections();
  else
    $("#page").innerHTML =
      '<div class="page-title"><h1>Security & observability</h1><p class="muted">Existing MFA-protected administration and Grafana are preserved.</p></div><a href="/admin">Open secure administration ↗</a>';
}
function landing() {
  app.innerHTML = `<main class="shell">${topbar()}<section class="hero"><div class="hero-copy"><div class="eyebrow">YOUR WORK. A WHOLE NEW DIMENSION.</div><h1>You wrote the code.<br>Now <em>see your<br>potential.</em></h1><p>Turn your GitHub into a universe of glass stacks. Discover the skills behind your work, find your next project, and build a career that feels like you.</p><form class="github-form" id="github-form"><input aria-label="GitHub username or profile URL" id="owner" placeholder="github.com / your-username" value="${esc(publicData?.owner || "")}" required><button class="primary" type="submit">Reveal my stacks ↗</button></form><div class="form-note" id="scan-status">Public repositories only. Start exploring, no account needed.</div><small id="service-state" class="service-state">Checking backend connection…</small></div>${sceneMarkup(publicData ? "@" + publicData.owner + " / REPOSITORY CONSTELLATION" : "A NEW PERSPECTIVE ON YOUR CODE", publicData ? "Live GitHub metadata · select a stack" : "Illustrative stacks · connect for your real data")}</section><div class="legend"><span><b>▰</b> Commits → height</span><span><b>◇</b> Stars → footprint</span><span><b>◌</b> Technology → color</span><span>Unknown commit counts use a marked baseline.</span></div><div id="public-results"></div><section class="access-band"><div><h3>Your code is only the beginning.</h3><p>Connect your identity. Build your profile in seven steps. Get a plan for your next level.</p></div><button class="primary" id="access">Access your universe ↗</button></section><div class="section-head" id="discover"><div><div class="eyebrow">THE NEXT THING YOU COULD BUILD</div><h2>Great projects. New possibilities.</h2></div><small>58 curated references · live stars available</small></div><div class="grid">${repoCards((publicData?.recommendations || catalog).slice(0, 6))}</div>${footer()}</main>`;
  attachScene(publicData?.repositories || illustration);
  api("health")
    .then(() => {
      if ($("#service-state"))
        $("#service-state").textContent =
          "API connected · no token needed for public discovery";
    })
    .catch(() => {
      if ($("#service-state"))
        $("#service-state").textContent =
          "API unavailable · start the combined development server";
    });
  $("#github-form").onsubmit = (e) => {
    e.preventDefault();
    action(async () => {
      const owner = parseGitHubOwner($("#owner").value);
      if (!owner) throw new Error("Enter a GitHub username or profile URL");
      $("#scan-status").textContent =
        "Reading your repositories and default-branch commit counts…";
      const btn = $("#github-form button");
      btn.disabled = true;
      btn.dataset.busy = "1";
      try {
        publicData = await api(
          "v1/glass/discover?owner=" + encodeURIComponent(owner),
        );
      } catch (e) {
        $("#scan-status").textContent =
          "Discovery unavailable. Please retry after checking the API connection.";
        throw e;
      }
      sessionStorage.setItem("codeverse.discovery.owner", owner);
      landing();
      showPublic();
    });
  };
  $("#access").onclick = authModal;
  bindRepoCards();
  if (publicData) showPublic();
}
function showPublic() {
  const p = publicData;
  if (!p) return;
  $("#public-results").innerHTML =
    `<div class="stats"><div class="stat"><div class="number">${p.count}${p.truncated ? "+" : ""}</div><small>Public repositories</small></div><div class="stat"><div class="number">${p.skills.length}</div><small>Language signals</small></div><div class="stat"><div class="number">${p.repositories.reduce((s, r) => s + r.stars, 0).toLocaleString()}</div><small>GitHub stars</small></div><div class="stat"><div class="number">${p.repositories.filter((r) => r.commits != null).length}</div><small>Repos with commit counts</small></div></div><div class="section-head"><h2>Your skills, made visible.</h2><small>Metadata signals · not proficiency ratings</small></div><div class="tags">${p.skills.map((s) => `<span class="chip">${esc(s)} · ${p.repositories.filter((r) => r.language === s).length} repos</span>`).join("") || "<p>No primary languages reported.</p>"}</div><details><summary>Explore all ${p.count} repositories and evidence</summary><div class="table-wrap"><table><thead><tr><th>Repository</th><th>Language</th><th>Commits (default branch)</th><th>Stars</th><th>Framework evidence</th></tr></thead><tbody>${p.repositories.map((r) => `<tr><td><a href="${safeURL(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.name)}</a></td><td>${esc(r.language || "Unknown")}</td><td>${r.commits ?? "<span>Not fetched</span>"} ${r.commits == null ? `<button data-commit-metric="${esc(r.full_name)}">Fetch count</button>` : ""}</td><td>${r.stars}</td><td><button data-scan="${esc(r.full_name)}">Check manifests</button><small data-signals="${esc(r.full_name)}"></small></td></tr>`).join("")}</tbody></table></div></details><p class="form-note" style="margin-bottom:25px">Up to 100 repositories; the scene shows 24 per page. Commit counts are fetched for up to 12 repositories per scan to conserve GitHub quota. Checked ${esc(new Date(p.checked_at).toLocaleString())}.</p>`;
  document.querySelectorAll("[data-scan]").forEach(
    (b) =>
    (b.onclick = () =>
      action(async () => {
        b.disabled = true;
        b.dataset.busy = "1";
        const d = await api(
          "v1/glass/analyze?repository=" + encodeURIComponent(b.dataset.scan),
        );
        const skillNames = [...new Set(d.evidence.map((e) => e.skill))];
        document.querySelectorAll("[data-signals]").forEach((out) => {
          if (out.dataset.signals === b.dataset.scan)
            out.textContent =
              (skillNames.join(", ") || "No supported manifests found") +
              " · static evidence";
        });
        notify(
          "Manifest scan complete. Repository use does not establish authorship.",
        );
      })),
  );
  document.querySelectorAll("[data-commit-metric]").forEach(
    (b) =>
    (b.onclick = () =>
      action(async () => {
        const value = await api(
          "v1/glass/repository/metrics?repository=" +
          encodeURIComponent(b.dataset.commitMetric),
        );
        const repo = publicData.repositories.find(
          (r) => r.full_name === b.dataset.commitMetric,
        );
        repo.commits = value.commits;
        attachScene(publicData.repositories);
        showPublic();
      })),
  );
}
function modal(html) {
  const el = document.createElement("div");
  el.className = "modal-backdrop";
  el.innerHTML = `<section class="modal" role="dialog" aria-modal="true">${html}<div class="row"><small>CODEVERSE / GLASS</small><button id="close-modal" class="flat">Close</button></div></section>`;
  document.body.append(el);
  connectLabels(el);
  el.querySelector("#close-modal").onclick = () => el.remove();
  el.addEventListener("click", (e) => {
    if (e.target === el) el.remove();
  });
  el.addEventListener("keydown", (e) => {
    if (e.key === "Escape") el.remove();
    if (e.key === "Tab") {
      const f = [
        ...el.querySelectorAll("button,input,textarea,select,a[href]"),
      ].filter((x) => !x.disabled);
      if (e.shiftKey && document.activeElement === f[0]) {
        e.preventDefault();
        f.at(-1).focus();
      } else if (!e.shiftKey && document.activeElement === f.at(-1)) {
        e.preventDefault();
        f[0].focus();
      }
    }
  });
  el.querySelector("input,button,textarea")?.focus();
  return el;
}
function authModal() {
  const el = modal(
    '<div class="eyebrow">YOUR NEXT CHAPTER</div><h2>Welcome to your universe.</h2><p class="muted">Sign in with GitHub to keep your verified username with you. Every new account starts as Visitor.</p><button class="primary" style="width:100%;margin:25px 0" id="github-auth">Continue with GitHub ↗</button><small>Dev, Recruiter and Admin are provisioned by the operator. Access cannot be changed from the browser.</small>',
  );
  el.querySelector("#github-auth").onclick = () =>
    action(async () => {
      await ensureAuth();
      const { error } = await auth.auth.signInWithOAuth({
        provider: "github",
        options: {
          redirectTo: location.origin + "/",
          scopes: "read:user public_repo",
        },
      });
      if (error) throw error;
    });
}
async function ensureAuth() {
  if (auth) return;
  const c = await api("secure/config");
  auth = createClient(c.supabase_url, c.supabase_anon_key, {
    auth: { flowType: "pkce", persistSession: true, detectSessionInUrl: true },
  });
}
async function loadAccount() {
  await api("v1/glass/identity", {});
  me = await api("secure/me");
  workspace = await api("v1/glass/state");
  dashboard = await api("v1/glass/dashboard");
  const owner = me.profile.github_username;
  try {
    publicData = await api(
      "v1/glass/discover?owner=" + encodeURIComponent(owner),
    );
  } catch (e) {
    notify(
      "Your profile loaded. Repository visualization will retry later: " +
      e.message,
      true,
    );
  }
  render();
}
function home() {
  const p = workspace.payload;
  $("#page").innerHTML =
    `<div class="page-title"><div class="eyebrow">THIS IS YOUR UNIVERSE</div><h1>Welcome, @${esc(me.profile.github_username)}.</h1><p class="muted">Your work is taking shape. Let’s turn it into your next opportunity.</p></div><section style="display:grid;grid-template-columns:1.4fr 1fr;gap:20px" class="home-scene">${sceneMarkup("YOUR REPOSITORY STACKS", "GitHub identity verified · public repository signals")}<div class="card" style="align-self:center"><div class="eyebrow">YOUR CURRENT SIGNALS</div><h2 style="margin-top:15px">${dashboard.skills.length} technologies.<br>Room to grow.</h2><div class="tags">${dashboard.skills
      .slice(0, 12)
      .map((s) => `<span class="chip">${esc(s)}</span>`)
      .join(
        "",
      )}</div><p>${p.submitted_at ? "Your career plan is ready. Build new evidence, one project at a time." : "Complete your profile below to get a career plan that connects your current work to where you want to go."}</p></div></section><div id="wizard"></div>`;
  attachScene(publicData?.repositories || p.journey?.[1]?.repositories || []);
  if (p.submitted_at) {
    $("#wizard").innerHTML =
      '<section class="access-band"><div><h3>Your seven-step profile is complete.</h3><p>Your roadmap, matching projects, and career opportunities are ready.</p></div><div class="split-actions"><button data-reopen="1">Edit profile</button><button class="primary" id="dashboard-go">Open career dashboard ↗</button></div></section>';
    $("#dashboard-go").onclick = () => {
      view = "Career dashboard";
      render();
    };
    bindReopenButtons();
  } else wizard();
}
const stageNames = [
  "Your background",
  "Your GitHub evidence",
  "Review your skills",
  "Choose your direction",
  "Companies & opportunities",
  "Your learning plan",
  "Review & submit",
];
function wizard() {
  const history = workspace.payload.journey || [],
    step = history.length + 1;
  let fields = "";
  const d = dashboard;
  if (step === 1)
    fields = `<label for="cv-file">Upload CV (PDF, DOCX or TXT, max 2 MB)</label><input id="cv-file" type="file" accept=".pdf,.docx,.txt"><label for="step-text">Or paste your CV / background</label><textarea id="step-text" placeholder="Your education, experience, technologies and projects…"></textarea><div id="cv-preview" class="muted" style="margin-top:15px"></div>`;
  if (step === 2)
    fields = `<div class="review"><h3>@${esc(me.profile.github_username)}</h3><p>${publicData?.count || 0} public repositories found. We’ll attach these to your profile and check supported manifests in up to two original repositories. Language and dependency signals describe repositories; they don’t establish your personal mastery.</p></div>`;
  if (step === 3)
    fields = `<div class="tags">${d.skills.map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</div><p class="muted">CV skills are self-reported. GitHub languages and manifest matches are repository signals. A reviewed project is needed to demonstrate control of a skill.</p><label><input id="ack" type="checkbox" style="width:auto"> I reviewed these signals and their limitations.</label>`;
  if (step === 4)
    fields = `<label for="target">Recommended career profile</label><select id="target">${d.profiles.map((r) => `<option value="${esc(r.id)}">${esc(r.title)} · ${r.match_percent}% technology coverage</option>`).join("")}</select><label for="location">Preferred location</label><input id="location" placeholder="Caen, Paris, Montréal, Bilbao, remote…"><div id="target-preview" class="review"></div>`;
  if (step === 5)
    fields = `<p class="muted">Companies to explore for ${esc(d.target.title)}. These are career page suggestions, not confirmed vacancies.</p><div class="review">${suggestedCompanies()
      .map(
        (c) =>
          `<p><a href="${safeURL(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.name)} ↗</a> · ${esc(c.provider || "Career page")}</p>`,
      )
      .join(
        "",
      )}</div><label><input id="ack" type="checkbox" style="width:auto"> Keep these companies in my career workspace.</label>`;
  if (step === 6)
    fields = `${d.plans.map((p) => `<details><summary>${esc(p.skill)} · ${esc(p.status)}</summary><ol>${p.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></details>`).join("")}<label><input id="ack" type="checkbox" style="width:auto"> I reviewed my learning plan.</label>`;
  if (step === 7)
    fields = `<div class="review"><h3>${esc(d.target.title)}</h3><p>${d.skills.length} skill signals · ${d.score}% technology coverage</p><p class="muted">${esc(d.score_method)}</p></div><label><input id="ack" type="checkbox" style="width:auto"> Submit my profile and create my personal career dashboard.</label>`;
  $("#wizard").innerHTML =
    `<section class="wizard"><div class="row"><span class="eyebrow">YOUR CAREER PROFILE</span><small>STEP ${step} / 7</small></div><div class="step-track">${stageNames.map((s, i) => `<span class="${i < step ? "done" : ""}" title="${esc(s)}"></span>`).join("")}</div><h2>${stageNames[step - 1]}</h2>${fields}${history.length ? `<details><summary>Review ${history.length} saved step${history.length > 1 ? "s" : ""}</summary>${history.map((v, i) => `<div class="review"><strong>${i + 1}. ${stageNames[i]}</strong>${stageSummary(v, i)}<button data-reopen="${i + 1}">Edit this step</button></div>`).join("")}</details>` : ""}<div class="actions"><small>Progress saved after each Continue.</small><button class="primary" id="continue">${step === 7 ? "Submit my profile" : "Save & continue"} ↗</button></div></section>`;
  installWizardControls(step);
  if (step === 1)
    $("#cv-file").onchange = () =>
      action(async () => {
        const file = $("#cv-file").files[0];
        if (!file) return;
        if (file.size > 2 * 1024 * 1024)
          throw new Error("CV must be under 2 MB");
        if (file.name.endsWith(".txt")) {
          $("#step-text").value = await file.text();
          return;
        }
        const form = new FormData();
        form.append("file", file);
        const r = await fetch("/api/v1/workflow/cv/extract", {
          method: "POST",
          headers: { Authorization: "Bearer " + session.access_token },
          body: form,
        });
        const v = await r.json();
        if (!r.ok) throw new Error(v.detail || "CV extraction failed");
        const names = v.skills.map((s) => s.name || s.id).filter(Boolean);
        $("#step-text").value = "Skills extracted from CV: " + names.join(", ");
        $("#cv-preview").textContent =
          names.join(" · ") + " · Review extracted skills before continuing.";
      });
  if (step === 4) {
    const preview = () => {
      const role = d.profiles.find((r) => r.id === $("#target").value);
      $("#target-preview").innerHTML =
        `<strong>Existing signals</strong><p>${esc(role.matched_skills.join(", ") || "No matching technologies yet")}</p><strong>Skills to develop</strong><p>${esc(role.missing_skills.join(", "))}</p>`;
    };
    $("#target").onchange = preview;
    preview();
  }
  $("#continue").onclick = () =>
    action(async () => {
      const b = $("#continue");
      b.disabled = true;
      b.dataset.busy = "1";
      const body =
        step === 1
          ? { text: $("#step-text").value, profile: readStudentProfile() }
          : step === 4
            ? { target: $("#target").value, location: $("#location").value }
            : {
              acknowledge: $("#ack")?.checked || step === 2,
              ...(step === 3
                ? {
                  ratings: Object.fromEntries(
                    [...document.querySelectorAll("[data-self-rating]")]
                      .filter((c) => c.value !== "")
                      .map((c) => [c.dataset.selfRating, Number(c.value)]),
                  ),
                }
                : {}),
            };
      await api("v1/glass/journey/" + step, body);
      workspace = await api("v1/glass/state");
      dashboard = await api("v1/glass/dashboard");

      if (step === 7) view = "Career dashboard";
      render();
    });
}
function gate() {
  if (!workspace.payload.submitted_at) {
    $("#page").innerHTML =
      '<div class="page-title"><h1>Your next chapter is almost ready.</h1><p class="muted">Complete your seven-step profile on Home to unlock your personal career workspace.</p></div><button id="back-home" class="primary">Continue my profile ↗</button>';
    $("#back-home").onclick = () => {
      view = "Home";
      render();
    };
    return true;
  }
  return false;
}
function career() {
  if (gate()) return;
  const d = dashboard;
  $("#page").innerHTML =
    `<div class="page-title"><div class="eyebrow">YOUR CAREER DASHBOARD</div><h1>Build toward ${esc(d.target.title)}.</h1><p class="muted">A clear direction. A practical next step. Evidence you can keep building.</p></div><div class="stats"><div class="stat"><div class="number">${d.score}%</div><small>Target technology coverage</small></div><div class="stat"><div class="number">${d.skills.length}</div><small>Current skill signals</small></div><div class="stat"><div class="number">${d.target.missing_skills.length}</div><small>Technologies to explore</small></div><div class="stat"><div class="number">${workspace.payload.applications?.length || 0}</div><small>Application records</small></div></div><p class="form-note">${esc(d.score_method)}</p><div class="section-head"><div><div class="eyebrow">YOUR NEXT LEVEL</div><h2>A plan for every technology.</h2></div><input id="tech-search" placeholder="Search the ${taxonomy.length}-technology catalog" style="max-width:330px" aria-label="Search technology catalog"></div><div id="tech-results" class="tags"></div><div class="grid">${d.plans.map((p) => `<article class="card"><div class="row"><h3>${esc(p.skill)}</h3><span class="chip ${p.status === "learn" ? "blue" : ""}">${esc(p.status)}</span></div><p>${p.status === "learn" ? "Develop this skill through a focused project." : "Turn an existing signal into stronger, reviewable evidence."}</p><ol>${p.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol><button data-find="${esc(p.skill)}">Find a reference project ↗</button></article>`).join("")}</div><div class="section-head"><h2>Projects to take you there.</h2></div><div class="grid">${repoCards(d.recommendations.slice(0, 6), true)}</div>`;
  $("#tech-search").oninput = () => {
    $("#tech-results").innerHTML = taxonomy
      .filter((t) =>
        t.name.toLowerCase().includes($("#tech-search").value.toLowerCase()),
      )
      .slice(0, 16)
      .map(
        (t) =>
          `<span class="chip blue">${esc(t.name)} · ${esc(t.category)}</span>`,
      )
      .join("");
  };
  document.querySelectorAll("[data-find]").forEach(
    (b) =>
    (b.onclick = () => {
      view = "Projects";
      render();
      $("#project-search").value = b.dataset.find;
      $("#project-search").dispatchEvent(new Event("input"));
    }),
  );
  installCareerControls();
  bindRepoCards();
}
function projects() {
  if (gate()) return;
  $("#page").innerHTML =
    `<div class="page-title"><div class="eyebrow">PROJECT LAUNCHPAD</div><h1>Build your next glass stack.</h1><p class="muted">Start an original learning repository with a plan inspired by an established project. Your stack appears after GitHub confirms creation.</p></div><input id="project-search" placeholder="Search by project, skill or technology" aria-label="Search project catalog"><div class="section-head"><h2>Reference projects</h2><small>Review upstream license before adapting code.</small></div><div class="grid" id="project-grid"></div>`;
  const filter = () => {
    const q = $("#project-search").value.toLowerCase();
    let rows = (
      q
        ? catalog
        : catalogSort === "match"
          ? dashboard.recommendations
          : catalog
    ).filter((r) =>
      (r.id + " " + r.search_text + " " + r.category).toLowerCase().includes(q),
    );
    rows = rows.filter(
      (r) => !projectCategory || r.category === projectCategory,
    );
    if (catalogSort === "stars")
      rows.sort((a, b) => (b.stars ?? -1) - (a.stars ?? -1));
    $("#project-grid").innerHTML =
      repoCards(rows, true) ||
      '<p class="empty">No matching reference. Try a broader technology name.</p>';
    bindRepoCards();
  };
  installProjectControls(filter);
  $("#project-search").oninput = filter;
  filter();
}
function projectModal(id) {
  const ref = catalog.find((r) => r.id === id);
  const el = modal(
    `<div class="eyebrow">NEW PROJECT / NEW POSSIBILITIES</div><h2>Make it your own.</h2><p class="muted">Reference: ${esc(id)}. Creates a new public repository with original runnable starter files, tests, and a learning plan tailored to your target. Upstream source is not copied.</p><label for="repo-name">New repository name</label><input id="repo-name" value="my-${esc(id.split("/")[1])}-lab"><ol>${ref.plan.map((s) => `<li>${esc(s)}</li>`).join("")}</ol><label><input type="checkbox" id="repo-confirm" style="width:auto"> Create this public repository in my GitHub account.</label><button id="repo-launch" class="primary">Create repository & stack ↗</button><div id="creation-status" class="muted" style="margin-top:15px"></div>`,
  );
  el.querySelector("#repo-launch").onclick = () =>
    action(async () => {
      if (!el.querySelector("#repo-confirm").checked)
        throw new Error("Confirm repository creation first");
      const { data } = await auth.auth.getSession();
      const token = data.session?.provider_token;
      if (!token) {
        const { error } = await auth.auth.signInWithOAuth({
          provider: "github",
          options: {
            redirectTo: location.origin + "/",
            scopes: "read:user public_repo",
          },
        });
        if (error) throw error;
        return;
      }
      el.querySelector("#creation-status").textContent =
        "Creating your repository on GitHub…";
      const result = await api(
        "v1/glass/projects",
        {
          template: id,
          name: el.querySelector("#repo-name").value,
          confirmed: true,
        },
        "POST",
        { "X-GitHub-Token": token },
      );
      const r = result.repository;
      publicData ??= { repositories: [], owner: me.profile.github_username };
      publicData.repositories.unshift({
        name: r.name,
        full_name: r.full_name,
        url: r.html_url,
        language: null,
        commits: result.commits ?? (result.initialized ? 1 : 0),
        stars: 0,
      });
      workspace = await api("v1/glass/state");
      el.remove();
      view = "Home";
      render();
      notify(
        result.warning ||
        "GitHub repository created. Your new stack is now in your universe.",
      );
    });
}
function suggestedCompanies() {
  const target = dashboard?.target.id || "";
  if (["telecom", "network"].includes(target))
    return [
      { name: "Nokia", url: "https://www.nokia.com/about-us/careers/" },
      { name: "Ericsson", url: "https://www.ericsson.com/en/careers" },
      { name: "Orange", url: "https://orange.jobs/" },
    ];
  if (["ai-ml", "llm", "research"].includes(target))
    return [
      { name: "Hugging Face", url: "https://huggingface.co/join-us" },
      { name: "Mistral AI", url: "https://mistral.ai/careers/" },
      {
        name: "Google",
        url: "https://www.google.com/about/careers/applications/",
      },
    ];
  return [
    { name: "OVHcloud", url: "https://careers.ovhcloud.com/" },
    {
      name: "GitLab",
      url: "https://about.gitlab.com/jobs/",
      provider: "greenhouse",
      board: "gitlab",
    },
    { name: "Canonical", url: "https://canonical.com/careers" },
  ];
}
async function saveWorkspace(changes) {
  const d = await api(
    "v1/glass/state",
    { revision: workspace.revision, ...changes },
    "PATCH",
  );
  workspace.payload = { ...workspace.payload, ...changes };
  workspace.revision = d.revision;
}
let offers = [];
function jobs() {
  if (gate()) return;
  const companies = workspace.payload.companies || [];
  $("#page").innerHTML =
    `<div class="page-title"><div class="eyebrow">JOB OPPORTUNITIES</div><h1>Find where your work belongs.</h1><p class="muted">Your career pages, live opportunities, and recruiter outreach in one place.</p></div><div class="split-actions"><button id="add-company" class="primary">+ Add company</button><button id="company-csv">Export companies CSV</button><button id="live-jobs">Fetch live job feed ↻</button><button id="gmail-connect">Connect Gmail</button><button id="gmail-test">Test Gmail</button><button id="compose">Compose email ↗</button></div><div class="table-wrap"><table><thead><tr><th>Company</th><th>Career page</th><th>Provider / board</th><th>Fetch</th></tr></thead><tbody>${companies.map((c, i) => `<tr><td>${esc(c.name)}</td><td><a href="${safeURL(c.url)}" target="_blank" rel="noopener noreferrer">Career page ↗</a></td><td>${esc(c.provider || "Link only")} ${esc(c.board || "")}</td><td><button data-company="${i}" ${!c.provider ? "disabled" : ""}>Fetch jobs ↻</button></td></tr>`).join("")}</tbody></table></div><p class="form-note">Structured fetching supports Greenhouse and Lever board IDs. Other career sites remain accessible by link. Recruiter email is shown only when explicitly present in an offer; none is guessed.</p><div class="section-head"><h2>Opportunities</h2><input id="offer-search" placeholder="Filter title, company, location" style="max-width:300px" aria-label="Filter opportunities"></div><div id="offers"></div>`;
  $("#add-company").onclick = () => {
    const el = modal(
      '<h2>Add a company.</h2><label>Name</label><input id="co-name" required><label>Career page (HTTPS)</label><input id="co-url" type="url"><label>Structured provider</label><select id="co-provider"><option value="">Career page link only</option value="greenhouse">Greenhouse</option><option value="lever">Lever</option></select><label>Board identifier (for fetching)</label><input id="co-board" placeholder="e.g. gitlab"><button id="co-save" class="primary" style="margin-top:20px">Save company</button>',
    );
    el.querySelector("#co-save").onclick = () =>
      action(async () => {
        const c = {
          name: el.querySelector("#co-name").value.trim(),
          url: el.querySelector("#co-url").value,
          provider: el.querySelector("#co-provider").value,
          board: el.querySelector("#co-board").value,
        };
        if (!c.name || safeURL(c.url) === "#")
          throw new Error("Provide a name and valid HTTPS career page");
        await saveWorkspace({ companies: [...companies, c] });
        el.remove();
        jobs();
      });
  };
  $("#company-csv").onclick = () =>
    csv("career-pages.csv", ["name", "url", "provider", "board"], companies);
  document.querySelectorAll("[data-company]").forEach(
    (b) =>
    (b.onclick = () =>
      action(async () => {
        const c = companies[+b.dataset.company];
        b.disabled = true;
        b.dataset.busy = "1";
        const d = await api("v1/glass/companies/fetch", {
          provider: c.provider,
          board: c.board,
        });
        await acceptOffers(d.offers);
        drawOffers();
        notify(`${offers.length} opportunities fetched from ${c.name}.`);
      })),
  );
  $("#live-jobs").onclick = () =>
    action(async () => {
      const d = await api("v1/glass/jobs");
      await acceptOffers(d.offers);
      drawOffers();
    });
  $("#offer-search").oninput = drawOffers;
  $("#gmail-connect").onclick = () =>
    action(async () => {
      const d = await api("v1/glass/gmail/connect", {});
      location.assign(d.url);
    });
  $("#gmail-test").onclick = () =>
    action(async () => {
      await api("v1/glass/gmail/test", {});
      notify("Gmail authorization tested. No email was sent.");
    });
  $("#compose").onclick = () => mailModal();
  installJobControls();
  drawOffers();
}
function drawOffers() {
  const q = $("#offer-search")?.value.toLowerCase() || "",
    rows = offers.filter((o) =>
      JSON.stringify([o.title, o.company, o.location])
        .toLowerCase()
        .includes(q),
    );
  $("#offers").innerHTML = rows.length
    ? `<div class="grid">${rows.map((o) => `<article class="card"><span class="chip">${esc(o.company)}</span><h3 style="margin-top:15px">${esc(o.title)}</h3><p>${esc(typeof o.location === "object" ? o.location?.name : o.location)}</p><div class="tags"><span class="chip">${o.match_percent == null ? "Score unavailable" : o.match_percent + "% skill overlap"}</span></div><small>${esc(o.requirements_source || "Published offer")}</small><small>Matched: ${esc((o.matched_skills || []).join(", ") || "None detected")}</small><small>To develop: ${esc((o.missing_skills || []).join(", ") || "No recognized gaps")}</small><small>Recruiter email: ${esc(o.recruiter_email || "Not provided")}</small><div class="split-actions" style="margin-top:20px"><button data-apply="${esc(o.id)}">Open application ↗</button>${o.recruiter_email ? `<button data-email="${esc(o.recruiter_email)}">Draft email</button>` : ""}</div></article>`).join("")}</div>`
    : '<div class="empty">Fetch a company board or the live feed to see real opportunities.</div>';
  document.querySelectorAll("[data-apply]").forEach(
    (b) =>
    (b.onclick = () =>
      action(async () => {
        const o = offers.find((o) => String(o.id) === b.dataset.apply);
        if (safeURL(o.url) === "#")
          throw new Error("This offer has no valid HTTPS application URL");
        const a = [...(workspace.payload.applications || [])];
        if (!a.some((x) => x.url === o.url))
          a.push({
            id: String(o.id),
            title: o.title,
            company: o.company,
            url: o.url,
            status: "opened",
            opened_at: new Date().toISOString(),
          });
        window.open(o.url, "_blank", "noopener,noreferrer");
        await saveWorkspace({ applications: a });
        notify(
          "Application link opened and recorded. Mark it submitted after you apply.",
        );
      })),
  );
  document
    .querySelectorAll("[data-email]")
    .forEach((b) => (b.onclick = () => mailModal(b.dataset.email)));
}
function applications() {
  if (gate()) return;
  const rows = workspace.payload.applications || [];
  $("#page").innerHTML =
    `<div class="page-title"><div class="eyebrow">YOUR APPLICATION PIPELINE</div><h1>Every opportunity, in motion.</h1><p class="muted">Opening a link records “opened”. You confirm when an application is submitted.</p></div><button id="export-apps">Export CSV</button><div class="table-wrap"><table><thead><tr><th>Role</th><th>Company</th><th>Current status</th><th>Action</th></tr></thead><tbody>${rows.map((a, i) => `<tr><td><a href="${safeURL(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)} ↗</a></td><td>${esc(a.company)}</td><td><select data-status="${i}">${["opened", "submitted", "interview", "offer", "rejected"].map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select></td><td>${a.status === "submitted" ? "✓ Submitted" : esc(a.opened_at?.slice(0, 10) || "")}</td></tr>`).join("") || '<tr><td colspan="4">No applications yet. Explore job opportunities to begin.</td></tr>'}</tbody></table></div>`;
  installApplicationControls();
  $("#export-apps").onclick = () =>
    csv(
      "applications.csv",
      ["title", "company", "url", "status", "opened_at"],
      rows,
    );
  document.querySelectorAll("[data-status]").forEach(
    (s) =>
    (s.onchange = () =>
      action(async () => {
        const next = rows.map((a, i) =>
          i === +s.dataset.status
            ? {
              ...a,
              status: s.value,
              updated_at: new Date().toISOString(),
              ...(s.value === "submitted"
                ? { submitted_at: new Date().toISOString() }
                : {}),
            }
            : a,
        );
        await saveWorkspace({ applications: next });
        notify("Application status saved.");
      })),
  );
}
function csv(name, keys, rows) {
  const cell = (v) =>
    '"' +
    String(v ?? "")
      .replace(/^[=+@-]/, "'$&")
      .replaceAll('"', '""') +
    '"';
  download(
    name,
    keys.join(",") +
    "\n" +
    rows.map((r) => keys.map((k) => cell(r[k])).join(",")).join("\n"),
    "text/csv",
  );
}
function download(name, text, type = "application/json") {
  const u = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.download = name;
  a.href = u;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
function mailModal(to = "") {
  const el = modal(
    `<div class="eyebrow">GMAIL / REVIEW BEFORE SENDING</div><h2>Start a conversation.</h2><label for="mail-to">Verified recruiter email</label><input id="mail-to" type="email" value="${esc(to)}"><label for="mail-subject">Subject</label><input id="mail-subject" value="Application — ${esc(dashboard.target.title)}"><label for="mail-body">Message</label><textarea id="mail-body">Hello,\n\nI’m interested in opportunities as a ${esc(dashboard.target.title)}. My recent work includes ${esc(dashboard.skills.slice(0, 5).join(", "))}.\n\nPortfolio: https://github.com/${esc(me.profile.github_username)}\n\nI would welcome the opportunity to discuss how I could contribute.\n\nKind regards,\n${esc(me.profile.display_name || me.profile.github_username)}</textarea><label><input type="checkbox" id="mail-confirm" style="width:auto"> I verified this recipient and reviewed this message.</label><button id="mail-send" class="primary">Send with Gmail ↗</button>`,
  );
  el.querySelector("#mail-send").onclick = () =>
    action(async () => {
      if (!el.querySelector("#mail-confirm").checked)
        throw new Error("Verify recipient and review message first");
      await api("v1/glass/gmail/send", {
        to: el.querySelector("#mail-to").value,
        subject: el.querySelector("#mail-subject").value,
        body: el.querySelector("#mail-body").value,
        confirmed: true,
      });
      el.remove();
      notify("Email accepted by Gmail.");
    });
}
function automation() {
  if (gate()) return;
  const nodes = workspace.payload.nodes || [],
    datasets = workspace.payload.datasets || [];
  $("#page").innerHTML =
    `<div class="page-title"><div class="eyebrow">AUTOMATION WORKSPACE</div><h1>Small boxes. Powerful connections.</h1><p class="muted">Build a flow with Python skills, datasets and Gmail drafts. Link inputs, configure each box, then start.</p></div><div class="row" style="margin-bottom:22px"><div class="split-actions"><button id="flow-start" class="primary">▶ Start workflow</button><button id="flow-export">Export flow</button><button id="flow-import">Import flow</button><input type="file" id="flow-file" accept=".json" class="hidden"></div><small>${nodes.length} boxes · ${datasets.length} datasets</small></div><div class="automation"><aside class="inventory"><div><div class="eyebrow" style="margin-bottom:15px">BOX INVENTORY</div><article class="card" draggable="true" data-kind="python"><span class="chip">PYTHON SKILL</span><h3 style="margin-top:15px">ƒ Python box</h3><p>JSON in → JSON out</p><button data-add="python">+ Add box</button></article><article class="card" draggable="true" data-kind="dataset"><span class="chip blue">DATASET</span><h3 style="margin-top:15px">▱ Data source</h3><p>CSV · JSON · text</p><button data-add="dataset">+ Add dataset</button></article><article class="card" draggable="true" data-kind="http"><span class="chip blue">API CONNECTOR</span><h3 style="margin-top:15px">↗ HTTPS API</h3><p>Configure · test · connect</p><button data-add="http">+ Configure API</button></article><article class="card" draggable="true" data-kind="gmail"><span class="chip">GMAIL</span><h3 style="margin-top:15px">✉ Gmail draft</h3><p>Connect & test first</p><button data-add="gmail">+ Configure Gmail</button></article></div></aside><div><div class="canvas-board" id="board"><svg class="graph-lines" aria-hidden="true">${nodes
      .flatMap((n) =>
        (n.inputs || []).map((id) => {
          const from = nodes.find((x) => x.id === id);
          if (!from) return "";
          const x1 = (from.x || 30) + 205,
            y1 = (from.y || 30) + 38,
            x2 = n.x || 30,
            y2 = (n.y || 30) + 38;
          return `<path d="M ${x1},${y1} C ${x1 + 90},${y1} ${x2 - 90},${y2} ${x2},${y2}" fill="none" stroke="#73b6a1" stroke-width="2"/>`;
        }),
      )
      .join(
        "",
      )}</svg>${nodes.map((n) => `<article class="node" tabindex="0" aria-label="${esc(n.name)} box; use arrow keys to move" data-node="${esc(n.id)}" style="left:${Number(n.x) || 30}px;top:${Number(n.y) || 30}px"><span class="eyebrow">${esc(n.kind)}</span><h3 style="margin-top:8px">${esc(n.name)}</h3><small>${n.inputs?.length || 0} input(s) · ${esc(n.outputName || "output.json")}</small><button data-edit="${esc(n.id)}">Configure ↗</button><button data-test-node="${esc(n.id)}">Run to here</button></article>`).join("")}${!nodes.length ? '<div style="padding:150px 30px;text-align:center;pointer-events:none"><h2 style="color:#72978e">Your canvas starts here.</h2><p class="muted">Drop a box from the inventory to begin.</p></div>' : ""}</div><div class="review" id="run-log"><small>Execution results appear here. Python requires the isolated runner. Gmail boxes create drafts; sending requires review.</small></div></div></div>`;
  document
    .querySelectorAll("[data-add]")
    .forEach((b) => (b.onclick = () => nodeModal(null, b.dataset.add)));
  document
    .querySelectorAll("[data-kind]")
    .forEach(
      (c) =>
      (c.ondragstart = (e) =>
        e.dataTransfer.setData("text/plain", c.dataset.kind)),
    );
  const board = $("#board");
  board.ondragover = (e) => e.preventDefault();
  board.ondrop = (e) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData("text/plain");
    if (["python", "dataset", "gmail", "http"].includes(kind))
      nodeModal(null, kind, {
        x: Math.max(20, e.offsetX),
        y: Math.max(20, e.offsetY),
      });
  };
  document
    .querySelectorAll("[data-edit]")
    .forEach(
      (b) =>
      (b.onclick = () =>
        nodeModal(nodes.find((n) => n.id === b.dataset.edit))),
    );
  document.querySelectorAll("[data-node]").forEach((el) => {
    el.onpointerdown = (e) => {
      if (e.target.closest("button")) return;
      const node = nodes.find((n) => n.id === el.dataset.node),
        start = {
          x: e.clientX,
          y: e.clientY,
          nx: node.x || 30,
          ny: node.y || 30,
        };
      el.setPointerCapture(e.pointerId);
      el.onpointermove = (ev) => {
        node.x = Math.max(10, Math.min(1500, start.nx + ev.clientX - start.x));
        node.y = Math.max(10, Math.min(1000, start.ny + ev.clientY - start.y));
        el.style.left = node.x + "px";
        el.style.top = node.y + "px";
        redrawConnections();
      };
      el.onpointerup = () => {
        el.onpointermove = null;
        el.onpointerup = null;
        action(async () => {
          await saveWorkspace({ nodes });
          automation();
        });
      };
    };
  });
  $("#flow-start").onclick = () => startFlow();
  installAutomationControls();
  $("#flow-export").onclick = () =>
    download(
      "codeverse-workflow.json",
      JSON.stringify({ schema: "codeverse.flow/1", nodes, datasets }, null, 2),
    );
  $("#flow-import").onclick = () => $("#flow-file").click();
  $("#flow-file").onchange = () =>
    action(async () => {
      const file = $("#flow-file").files[0];
      if (!file || file.size > 2_000_000)
        throw new Error("Choose a workflow JSON under 2 MB");
      const v = JSON.parse(await file.text());
      validateFlowImport(v);
      await saveWorkspace({ nodes: v.nodes, datasets: v.datasets });
      automation();
    });
}
function nodeModal(existing, kind, pos = {}) {
  kind = existing?.kind || kind;
  const nodes = workspace.payload.nodes || [],
    datasets = workspace.payload.datasets || [];
  const n = existing || {
    id: uniqueId(),
    kind,
    name:
      kind === "python"
        ? "Python skill"
        : kind === "gmail"
          ? "Gmail draft"
          : kind === "http"
            ? "API connector"
            : "Dataset",
    x: pos.x || 40 + (nodes.length % 3) * 250,
    y: pos.y || 40 + Math.floor(nodes.length / 3) * 170,
    inputs: [],
    code: 'import json, sys\ninputs = json.load(sys.stdin)\nprint(json.dumps({"result": inputs}))',
    outputName: "output.json",
  };
  const el = modal(
    `<div class="eyebrow">CONFIGURE ${esc(kind.toUpperCase())} BOX</div><h2>Give this box a purpose.</h2><label>Name</label><input id="node-name" value="${esc(n.name)}"><label>Inputs (select boxes to link)</label><select id="node-inputs" multiple style="min-height:90px">${nodes
      .filter((x) => x.id !== n.id)
      .map(
        (x) =>
          `<option value="${esc(x.id)}" ${n.inputs?.includes(x.id) ? "selected" : ""}>${esc(x.name)}</option>`,
      )
      .join("")}</select><small>Choose upstream boxes to connect. Outputs use JSON values.</small>${kind === "python" ? `<label>Python code · reads JSON from stdin, prints JSON to stdout</label><textarea id="node-code" class="code">${esc(n.code)}</textarea><p class="form-note">Runs in an isolated, offline container with CPU, memory, process and time limits. Standard Python library only.</p>` : kind === "dataset" ? `<label>Choose an existing dataset</label><select id="node-dataset"><option value="">Upload a new dataset</option>${datasets.map((d) => `<option value="${esc(d.id)}" ${d.id === n.dataset ? "selected" : ""}>${esc(d.name)} (${esc(d.type)})</option>`).join("")}</select><label>Upload CSV, JSON or TXT (max 500 KB)</label><input id="dataset-file" type="file" accept=".csv,.json,.txt"><small>Upload text here or select any file from the dataset inventory. Files remain owner-scoped.</small>` : `<p class="muted" style="margin-top:20px">Gmail must be connected and tested before using this box. It produces drafts for review in the email composer.</p><button id="node-gmail-connect" style="margin-top:20px">Connect Gmail</button><button id="node-gmail-test">Test authorization</button>`}<label>Output filename</label><input id="node-output" value="${esc(n.outputName)}"><div class="split-actions" style="margin-top:20px"><button id="node-save" class="primary">Save box & connections</button>${existing && nodes.some((x) => x.id === n.id) ? '<button id="node-delete">Delete box</button>' : ""}</div>`,
  );
  let tested = false,
    testedCode = existing?.tested_code,
    connectorName = existing?.connectorName;
  if (kind === "python" && existing?.testInput)
    el.querySelector("#node-code").dataset.testInput = existing.testInput;
  if (kind === "http") {
    el.querySelector(".modal>p")?.remove();
    el.querySelector("#node-output").previousElementSibling.insertAdjacentHTML(
      "beforebegin",
      "<label>Connector name</label><input id=connector-name placeholder=my-api><label>HTTPS host (operator allowlist)</label><input id=connector-host placeholder=api.github.com><label>API path (GET)</label><input id=connector-path value=/zen><label>Bearer API key (optional; encrypted server-side)</label><input id=connector-key type=password autocomplete=off><button id=connector-test style=margin-top:15px>Test & save configuration</button>",
    );
    el.querySelector("#connector-name").value = connectorName || "";
    if (connectorName)
      api("v1/glass/connectors/" + encodeURIComponent(connectorName))
        .then((d) => {
          el.querySelector("#connector-host").value = d.host;
          el.querySelector("#connector-path").value = d.path;
          el.querySelector("#connector-key").placeholder = d.has_token
            ? "Stored key retained if blank"
            : "Optional key";
        })
        .catch((e) => notify(e.message, true));
    el.querySelector("#connector-test").onclick = () =>
      action(async () => {
        const d = await api("v1/glass/connectors/test", {
          name: el.querySelector("#connector-name").value,
          host: el.querySelector("#connector-host").value,
          path: el.querySelector("#connector-path").value,
          token: el.querySelector("#connector-key").value,
        });
        tested = true;
        connectorName = d.name;
        el.querySelector("#connector-key").value = "";
        notify("API connection tested and encrypted configuration saved.");
      });
    el.querySelector("#node-gmail-connect")?.remove();
    el.querySelector("#node-gmail-test")?.remove();
  }
  if (kind === "python") {
    const button = document.createElement("button");
    button.textContent = "Test Python box";
    el.querySelector("#node-code").insertAdjacentHTML(
      "afterend",
      '<label for="python-test-input">Test input (JSON array of upstream values)</label><textarea id="python-test-input" class="code" style="min-height:90px">[]</textarea><pre id="python-test-result"></pre>',
    );
    el.querySelector("#python-test-input").after(button);
    button.onclick = () =>
      action(async () => {
        const d = await api("v1/glass/automation/test", {
          code: el.querySelector("#node-code").value,
          input: JSON.parse(el.querySelector("#python-test-input").value),
        });
        testedCode = d.tested_code;
        el.querySelector("#node-code").dataset.testedCode = testedCode;
        el.querySelector("#python-test-result").textContent = JSON.stringify(
          d.output,
          null,
          2,
        );
        notify("Python test passed: " + JSON.stringify(d.output).slice(0, 200));
      });
  }
  if (kind === "gmail") {
    el.querySelector("#node-gmail-connect").onclick = () =>
      action(async () => {
        const d = await api("v1/glass/gmail/connect", {});
        location.assign(d.url);
      });
    el.querySelector("#node-gmail-test").onclick = () =>
      action(async () => {
        await api("v1/glass/gmail/test", {});
        tested = true;
        notify("Gmail configuration tested successfully.");
      });
  }
  installNodeExtras(el, n);
  el.querySelector("#node-save").onclick = () =>
    action(async () => {
      const next = {
        ...n,
        name: el.querySelector("#node-name").value.slice(0, 80),
        inputs: [...el.querySelectorAll("input[name=node-input]:checked")].map(
          (o) => o.value,
        ),
        outputName: el.querySelector("#node-output").value.slice(0, 100),
      };
      let updatedDatasets = [...datasets];
      if (!next.name) throw new Error("Name this box");
      if (kind === "python") {
        next.code = el.querySelector("#node-code").value;
        next.tested_code = testedCode;
        next.testInput = el.querySelector("#python-test-input").value;
      }
      if (kind === "dataset") {
        const file = el.querySelector("#dataset-file").files[0];
        if (file) {
          if (file.size > 500_000 || !/\.(csv|json|txt)$/i.test(file.name))
            throw new Error("Choose a CSV, JSON or TXT under 500 KB");
          const data = {
            id: uniqueId(),
            name: file.name,
            type: file.name.split(".").pop().toLowerCase(),
            content: await file.text(),
          };
          if (data.type === "json") JSON.parse(data.content);
          updatedDatasets.push(data);
          next.dataset = data.id;
        } else next.dataset = el.querySelector("#node-dataset").value;
        if (!next.dataset) throw new Error("Choose or upload a dataset");
      }
      if (kind === "http") {
        if (!tested && !existing)
          throw new Error("Test the API connector before adding this box");
        next.connectorName = connectorName;
      }
      if (kind === "gmail") {
        next.to = el.querySelector("#gmail-node-to").value;
        next.subject = el.querySelector("#gmail-node-subject").value;
        next.body = el.querySelector("#gmail-node-body").value;
        next.operation = el.querySelector("#gmail-node-operation").value;
      }
      if (kind === "gmail" && !tested && !existing)
        throw new Error("Test Gmail authorization before adding this box");
      const updated =
        existing && nodes.some((x) => x.id === n.id)
          ? nodes.map((x) => (x.id === n.id ? next : x))
          : [...nodes, next];
      await saveWorkspace({ nodes: updated, datasets: updatedDatasets });
      el.remove();
      automation();
    });
  if (existing && nodes.some((x) => x.id === n.id))
    el.querySelector("#node-delete").onclick = () =>
      action(async () => {
        await saveWorkspace({
          nodes: nodes
            .filter((x) => x.id !== n.id)
            .map((x) => ({
              ...x,
              inputs: (x.inputs || []).filter((i) => i !== n.id),
            })),
        });
        el.remove();
        automation();
      });
}
async function init() {
  const results = await Promise.allSettled([
    fetch("/repository-catalog.json").then((r) => r.json()),
    fetch("/technology-taxonomy.json").then((r) => r.json()),
  ]);
  catalog = results[0].status === "fulfilled" ? results[0].value : [];
  taxonomy =
    results[1].status === "fulfilled" ? results[1].value.technologies : [];
  const chosen = new URLSearchParams(location.hash.slice(1)).get("view");
  if (
    [
      "Home",
      "Career dashboard",
      "Projects",
      "Job opportunities",
      "Applications",
      "Automation",
      "Connections",
      "Security",
    ].includes(chosen)
  )
    view = chosen;

  if (devBypassActive()) {
    me = {
      profile: {
        github_username: "dev-bypass-user",
        role: "developer",
      },
    };
    workspace = { payload: { journey: [] }, revision: 0 };
    dashboard = {
      skills: ["Python", "JavaScript", "FastAPI", "Docker", "SQL"],
    };
    publicData = {
      owner: "dev-bypass-user",
      count: 0,
      skills: ["Python", "JavaScript"],
      repositories: [],
      recommendations: [],
      checked_at: new Date().toISOString(),
    };
    render();
    return;
  }

  landing();
  api("v1/glass/catalog?limit=100")
    .then((result) => {
      if (result.repositories?.length) catalog = result.repositories;
    })
    .catch(() => { });
  try {
    await ensureAuth();
    const { data, error } = await auth.auth.getSession();
    if (error) throw error;
    session = data.session;
    if (session) await loadAccount();
    if (new URLSearchParams(location.search).get("gmail") === "connected") {
      notify("Gmail connected. Test authorization in Connections.");
      history.replaceState(null, "", location.pathname + location.hash);
    }
    auth.auth.onAuthStateChange((event, s) => {
      session = s;
      if (event === "SIGNED_OUT") {
        me = null;
        landing();
      }
      if (event === "TOKEN_REFRESHED") session = s;
    });
  } catch (e) {
    if (location.search.includes("code=") || session) notify(e.message, true);
  }
}
window.addEventListener("hashchange", () => {
  const next = new URLSearchParams(location.hash.slice(1)).get("view");
  if (me && next && next !== view) {
    view = next;
    render();
  }
});
init();

function stageSummary(value, index) {
  if (index === 0)
    return `<p>${esc(value.profile?.full_name || "Student profile")} · ${esc(value.profile?.university || "University not provided")}</p><p>${esc(value.profile?.education || "")}</p><div class="tags">${(value.skills || []).map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</div>`;
  if (index === 1)

    return `<p>@${esc(value.owner)} · ${value.repositories?.length || 0} repositories · ${value.manifest_scans?.length || 0} manifest scans</p><div class="tags">${(
      value.repositories || []
    )
      .slice(0, 12)
      .map(
        (r) =>
          `<a class="chip blue" href="${safeURL(r.url || "https://github.com/" + r.full_name)}" target="_blank" rel="noopener noreferrer">${esc(r.name)}</a>`,
      )
      .join(
        "",
      )}</div>${(value.warnings || []).map((w) => `<small>${esc(w)}</small>`).join("")}`;
  if (index === 3)
    return `<p>${esc(dashboard.profiles.find((r) => r.id === value.target)?.title || value.target)} · ${esc(value.location || "Any location")}</p>`;
  return `<p>${index === 2 ? "Skill evidence and its limitations reviewed" : index === 4 ? "Company career pages reviewed" : index === 5 ? "Learning plan reviewed" : "Profile review complete"}</p>`;
}
function readStudentProfile() {
  return Object.fromEntries(
    [
      "full_name",
      "university",
      "education",
      "experience",
      "availability",
      "portfolio",
    ].map((key) => [key, $("#profile-" + key)?.value || ""]),
  );
}
function installWizardControls(step) {
  const draft = workspace.payload.drafts?.[step] || {},
    form = $("#wizard .wizard");
  if (step === 1) {
    const profile =
      draft.profile || workspace.payload.journey?.[0]?.profile || {};
    $("#cv-file").previousElementSibling.insertAdjacentHTML(
      "beforebegin",
      `<div class="profile-fields two-col">${[
        ["full_name", "Full name"],
        ["university", "University / school"],
        ["education", "Degree and year"],
        ["experience", "Experience summary"],
        ["availability", "Availability / internship dates"],
        ["portfolio", "Portfolio URL (optional)"],
      ]
        .map(
          ([key, label]) =>
            `<div><label for="profile-${key}">${label}</label><input id="profile-${key}" value="${esc(profile[key] || "")}" maxlength="${key === "experience" ? 1500 : key === "full_name" ? 120 : ["university", "availability"].includes(key) ? 160 : 300}"></div>`,
        )
        .join("")}</div>`,
    );
    if (draft.skills?.length)
      $("#step-text").value = "Saved skill claims: " + draft.skills.join(", ");
  }
  if (step === 3) {
    const block = document.createElement("div");
    block.className = "two-col";
    block.innerHTML = dashboard.skills
      .map(
        (skill) =>
          `<div><label>${esc(skill)} · optional self-assessment</label><select data-self-rating="${esc(skill)}" aria-label="Self-assessed ${esc(skill)} level"><option value="">Not assessed</option>${["New to it", "Learning basics", "Can build with guidance", "Independent", "Can mentor"].map((label, i) => `<option value="${i}" ${draft.ratings?.[skill] === i ? "selected" : ""}>${i}/4 — ${label}</option>`).join("")}</select></div>`,
      )
      .join("");
    form.querySelector("h2").after(block);
  }
  if (step === 4) {
    if (draft.target) $("#target").value = draft.target;
    $("#location").value = draft.location || "";
  }
  if ($("#ack") && draft.acknowledge) $("#ack").checked = true;
  const actions = form.querySelector(".actions");
  actions.insertAdjacentHTML(
    "beforebegin",
    '<div class="split-actions" style="margin-top:20px"><button id="save-draft">Save draft</button><button id="export-profile">Download profile</button></div>',
  );
  $("#save-draft").onclick = () =>
    action(async () => {
      const values =
        step === 1
          ? { text: $("#step-text").value, profile: readStudentProfile() }
          : step === 4
            ? { target: $("#target").value, location: $("#location").value }
            : { acknowledge: $("#ack")?.checked || false, ...(step === 3 ? { ratings: Object.fromEntries([...document.querySelectorAll("[data-self-rating]")].filter(c => c.value !== "").map(c => [c.dataset.selfRating, Number(c.value)])) } : {}) };
      const r = await api(
        "v1/glass/journey/draft",
        { revision: workspace.revision, step, values },
        "PUT",
      );
      workspace = await api("v1/glass/state");
      notify(
        "Draft saved. Original CV text is excluded; structured fields and skill claims are retained.",
      );
    });
  $("#export-profile").onclick = () =>
    download(
      "codeverse-profile.json",
      JSON.stringify(
        {
          github: me.profile.github_username,
          journey: workspace.payload.journey || [],
          career: dashboard.target,
          skills: dashboard.skill_details,
        },
        null,
        2,
      ),
    );
  bindReopenButtons();
}
function bindReopenButtons() {
  document.querySelectorAll("[data-reopen]").forEach(
    (b) =>
    (b.onclick = () => {
      const step = Number(b.dataset.reopen);
      const el = modal(
        `<h2>Edit ${esc(stageNames[step - 1])}?</h2><p class="muted">This reopens step ${step} and the later profile reviews. Your companies, applications, projects and automation files are kept.</p><button class="primary" id="reopen-confirm" style="margin-top:20px">Edit and review later steps</button>`,
      );
      el.querySelector("#reopen-confirm").onclick = () =>
        action(async () => {
          await api("v1/glass/journey/reopen", {
            revision: workspace.revision,
            step,
            confirmed: true,
          });
          workspace = await api("v1/glass/state");
          dashboard = await api("v1/glass/dashboard");
          el.remove();
          view = "Home";
          render();
          $("#wizard")?.scrollIntoView({
            block: "start",
            behavior: "smooth",
          });
        });
    }),
  );
}
function installCareerControls() {
  const grids = $("#page").querySelectorAll(".grid");
  grids[0]?.querySelectorAll(".card").forEach((card, index) => {
    const plan = dashboard.plans[index],
      key = normalizeSkill(plan.skill),
      current = dashboard.progress?.[key] || {};
    card.querySelector("ol").innerHTML = plan.steps
      .map(
        (text, i) =>
          `<li><label class="milestone"><input type="checkbox" data-progress="${i}" ${current[i]?.completed ? "checked" : ""}>${esc(text)}</label><input class="proof-url" type="url" data-proof="${i}" aria-label="Optional proof URL for ${esc(plan.skill)} milestone ${i + 1}" placeholder="Optional HTTPS proof link" value="${esc(current[i]?.proof_url || "")}"></li>`,
      )
      .join("");
    card.insertAdjacentHTML(
      "beforeend",
      `<small class="completion-count">${Object.values(current).filter((x) => x.completed).length}/4 completed · self-reported</small>`,
    );
    const save = (index) =>
      action(async () => {
        const result = await api("v1/glass/learning/progress", {
          revision: workspace.revision,
          skill: plan.skill,
          index: Number(index),
          completed: card.querySelector(`[data-progress="${index}"]`).checked,
          proof_url: card.querySelector(`[data-proof="${index}"]`).value,
        });
        workspace.revision = result.revision;
        dashboard.progress ??= {};
        dashboard.progress[key] = result.progress;
        card.querySelector(".completion-count").textContent =
          Object.values(result.progress).filter((x) => x.completed).length +
          "/4 completed · self-reported";
      });
    card
      .querySelectorAll("[data-progress]")
      .forEach((c) => (c.onchange = () => save(c.dataset.progress)));
    card
      .querySelectorAll("[data-proof]")
      .forEach((c) => (c.onchange = () => save(c.dataset.proof)));
  });
  const section = document.createElement("section");
  section.innerHTML = `<div class="section-head"><div><div class="eyebrow">SKILLS & EVIDENCE</div><h2>Know what supports each signal.</h2></div><button id="download-evidence">Export skills CSV</button></div><p class="form-note">Evidence strength counts source types, from 1 to 3. It is not a mastery rating. Personal mastery remains unassessed until a reviewed assessment.</p><div class="table-wrap"><table><thead><tr><th>Technology</th><th>Evidence</th><th>Source strength</th><th>Related repositories</th></tr></thead><tbody>${(dashboard.skill_details || []).map((row) => `<tr><td>${esc(row.name)}<small>${row.self_rating == null ? esc(row.mastery) : "Self-rated " + row.self_rating + "/4; unverified"}</small></td><td>${row.sources.map((s) => `<details><summary>${esc(s.kind)}</summary>${esc(s.reference)}</details>`).join("")}</td><td>${row.evidence_score}/3 source types</td><td>${row.related_repositories.map((id) => `<p><a href="https://github.com/${esc(id)}" target="_blank" rel="noopener noreferrer">${esc(id)} ↗</a></p>`).join("")}</td></tr>`).join("")}</tbody></table></div>`;
  $("#page").append(section);
  $("#download-evidence").onclick = () =>
    csv(
      "skill-evidence.csv",
      ["technology", "source_types", "sources", "mastery"],
      dashboard.skill_details.map((r) => ({
        technology: r.name,
        source_types: r.evidence_score,
        sources: r.sources.map((s) => s.kind + ": " + s.reference).join(" | "),
        mastery: r.mastery,
      })),
    );
}
function installProjectControls(filter) {
  $("#project-search").insertAdjacentHTML(
    "afterend",
    `<div class="split-actions" style="margin-top:16px"><select id="project-category" aria-label="Project category" style="max-width:240px"><option value="">All categories</option>${[...new Set(catalog.map((r) => r.category))].map((c) => `<option ${c === projectCategory ? "selected" : ""}>${esc(c)}</option>`).join("")}</select><select id="project-sort" aria-label="Project ranking" style="max-width:240px"><option value="match">Recommended skill match</option><option value="stars">Known GitHub stars</option></select><button id="refresh-stars">Refresh visible stars</button></div><p class="form-note">Star ordering uses fetched metrics only. Unknown values remain unknown. Refreshes are limited to eight projects per batch.</p>`,
  );
  $("#project-sort").value = catalogSort;
  $("#project-category").onchange = () => {
    projectCategory = $("#project-category").value;
    filter();
  };
  $("#project-sort").onchange = () => {
    catalogSort = $("#project-sort").value;
    filter();
  };
  $("#refresh-stars").onclick = () =>
    action(async () => {
      const ids = [...document.querySelectorAll("#project-grid [data-refresh]")]
        .slice(0, 8)
        .map((b) => b.dataset.refresh);
      let updated = 0;
      for (const id of ids) {
        const metric = await api(
          "v1/glass/catalog/metrics?repository=" + encodeURIComponent(id),
        );
        Object.assign(catalog.find((r) => r.id === id) || {}, metric);
        Object.assign(
          dashboard.recommendations.find((r) => r.id === id) || {},
          metric,
        );
        updated++;
      }
      filter();
      notify(updated + " GitHub metrics refreshed.");
    });
  const own = workspace.payload.created_projects || [];
  if (own.length)
    $("#page").insertAdjacentHTML(
      "beforeend",
      `<div class="section-head"><h2>Your launched projects</h2></div><div class="grid">${own.map((r) => `<article class="card"><h3><a href="${safeURL(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.full_name)} ↗</a></h3><p>Reference: ${esc(r.reference)}</p><small>${r.files?.length || 0} original starter files</small>${r.missing_files?.length ? `<p>Needs attention: ${esc(r.missing_files.join(", "))}</p>` : ""}<small>Created ${esc(new Date(r.created_at).toLocaleString())}</small></article>`).join("")}</div>`,
    );
}
let rawOffers = [];
async function acceptOffers(rows) {
  rawOffers = rows;
  const ranked = await api("v1/glass/jobs/rank", {
    offers: rows,
    location: offerLocation || undefined,
  });
  offers = ranked.offers;
}
function companyModal(index) {
  const records = workspace.payload.companies || [],
    c = records[index];
  const el = modal(
    `<h2>Edit company</h2><label for="edit-co-name">Company</label><input id="edit-co-name" value="${esc(c.name)}"><label for="edit-co-url">HTTPS career page</label><input id="edit-co-url" value="${esc(c.url)}"><label for="edit-co-provider">Provider</label><select id="edit-co-provider"><option value="">Link only</option><option value="greenhouse">Greenhouse</option><option value="lever">Lever</option></select><label for="edit-co-board">Board identifier</label><input id="edit-co-board" value="${esc(c.board)}"><div class="split-actions" style="margin-top:20px"><button class="primary" id="company-update">Save</button><button id="company-remove">Remove company</button></div>`,
  );
  el.querySelector("#edit-co-provider").value = c.provider || "";
  el.querySelector("#company-update").onclick = () =>
    action(async () => {
      const row = companyRows([
        {
          name: el.querySelector("#edit-co-name").value,
          url: el.querySelector("#edit-co-url").value,
          provider: el.querySelector("#edit-co-provider").value,
          board: el.querySelector("#edit-co-board").value,
        },
      ])[0];
      await saveWorkspace({
        companies: records.map((v, i) => (i === index ? { ...v, ...row } : v)),
      });
      el.remove();
      jobs();
    });
  el.querySelector("#company-remove").onclick = () =>
    action(async () => {
      await saveWorkspace({ companies: records.filter((_, i) => i !== index) });
      el.remove();
      jobs();
    });
}
function installJobControls() {
  const buttons = $("#page .split-actions");
  buttons.insertAdjacentHTML(
    "beforeend",
    '<button id="import-companies">Import companies CSV</button><input class="hidden" type="file" id="company-file" accept=".csv"><button id="board-chart">Toggle company chart</button>',
  );
  $("#import-companies").onclick = () => $("#company-file").click();
  $("#company-file").onchange = () =>
    action(async () => {
      const file = $("#company-file").files[0];
      if (!file || file.size > 500000)
        throw new Error("Choose a companies CSV under 500 KB");
      const incoming = companyRows(parseCSV(await file.text())),
        combined = [...(workspace.payload.companies || [])];
      for (const r of incoming)
        if (!combined.some((c) => c.url === r.url)) combined.push(r);
      await saveWorkspace({ companies: combined });
      jobs();
      notify("CSV imported; duplicate career URLs were skipped.");
    });
  document.querySelectorAll("[data-company]").forEach((b) => {
    b.insertAdjacentHTML(
      "afterend",
      `<button data-company-edit="${b.dataset.company}">Edit</button><span data-fetch-status="${b.dataset.company}" class="form-note"></span>`,
    );
    if (!b.disabled)
      b.onclick = () =>
        action(async () => {
          const company = (workspace.payload.companies || [])[
            +b.dataset.company
          ],
            out = document.querySelector(
              `[data-fetch-status="${b.dataset.company}"]`,
            );
          out.textContent = "Checking…";
          b.disabled = true;
          b.dataset.busy = "1";
          try {
            const response = await api("v1/glass/companies/fetch", {
              provider: company.provider,
              board: company.board,
            });
            await acceptOffers(response.offers);
            drawOffers();
            out.textContent =
              response.offers.length +
              " offers · " +
              new Date().toLocaleTimeString();
          } catch (error) {
            out.textContent = "Fetch failed · open career page instead";
            throw error;
          }
        });
  });
  document
    .querySelectorAll("[data-company-edit]")
    .forEach(
      (b) => (b.onclick = () => companyModal(Number(b.dataset.companyEdit))),
    );
  $("#offer-search").insertAdjacentHTML(
    "beforebegin",
    `<input id="offer-location" aria-label="Offer location filter" placeholder="Locations, separated by commas" value="${esc(offerLocation || workspace.payload.journey?.[3]?.location || "")}" style="max-width:280px"><button id="offer-location-apply">Apply location</button>`,
  );
  $("#offer-location-apply").onclick = () =>
    action(async () => {
      offerLocation = $("#offer-location").value;
      await acceptOffers(rawOffers);
      drawOffers();
    });
  $("#board-chart").onclick = () => {
    const existing = $("#company-chart");
    if (existing) {
      existing.remove();
      return;
    }
    const counts = new Map();
    for (const o of offers)
      counts.set(o.company, (counts.get(o.company) || 0) + 1);
    const max = Math.max(1, ...counts.values());
    const el = document.createElement("div");
    el.id = "company-chart";
    el.className = "review";
    el.innerHTML =
      "<h3>Fetched opportunities by company</h3>" +
      ([...counts]
        .map(
          ([name, value]) =>
            `<div class="chart-row"><span>${esc(name)}</span><meter min="0" max="${max}" value="${value}" aria-label="${esc(name)} offers"></meter><b>${value}</b></div>`,
        )
        .join("") || "<p>Fetch a board to populate this chart.</p>");
    $("#offers").before(el);
  };
}
function installApplicationControls() {
  $("#page>button").insertAdjacentHTML(
    "afterend",
    '<select id="application-filter" aria-label="Application status filter" style="max-width:220px;margin-left:15px"><option value="">All statuses</option><option>opened</option><option>submitted</option><option>interview</option><option>offer</option><option>rejected</option></select>',
  );
  $("#application-filter").onchange = () => {
    const value = $("#application-filter").value;
    document.querySelectorAll("#page tbody tr").forEach((row) => {
      row.hidden = !!value && row.querySelector("select")?.value !== value;
    });
  };
}
async function connections() {
  $("#page").innerHTML =
    '<div class="page-title"><div class="eyebrow">CONNECTIONS</div><h1>Your integrations, under control.</h1><p class="muted">Connected, tested, or waiting for configuration. Secret values are never displayed.</p></div><div id="connections-state" class="empty">Reading connection status…</div>';
  try {
    integrationState = await api("v1/glass/integrations");
    const d = integrationState;
    $("#connections-state").className = "grid";
    $("#connections-state").innerHTML =
      `<article class="card"><h3>GitHub</h3><span class="chip">Identity verified</span><p>@${esc(me.profile.github_username)}</p><small>Repository-write permission is checked when creating a project.</small></article><article class="card"><h3>Gmail</h3><p>${d.gmail.connected ? "Connected" : d.gmail.configured ? "Not connected" : "Server OAuth configuration required"}</p><small>Last tested: ${d.gmail.tested_at ? esc(new Date(d.gmail.tested_at).toLocaleString()) : "Not tested"}</small><div class="split-actions" style="margin-top:20px"><button id="connection-gmail">Connect</button><button id="connection-test">Test</button><button id="connection-disconnect">Disconnect</button></div></article><article class="card"><h3>Python execution</h3><span class="chip">${d.python.configured ? "Runner configured" : "Worker configuration required"}</span><p>Test code with an input sample before running your workflow. Code executes on the isolated worker.</p></article><article class="card"><h3>HTTPS API boxes</h3><p>Allowed hosts: ${esc(d.allowed_api_hosts.join(", "))}</p><small>Configure and test each credential in the automation box.</small></article>`;
    $("#connection-gmail").onclick = () =>
      action(async () => {
        const r = await api("v1/glass/gmail/connect", {});
        location.assign(r.url);
      });
    $("#connection-test").onclick = () =>
      action(async () => {
        await api("v1/glass/gmail/test", {});
        notify("Authorization tested. No message sent.");
        connections();
      });
    $("#connection-disconnect").onclick = () =>
      action(async () => {
        await api("v1/glass/gmail/disconnect", {});
        notify(
          "Gmail disconnected from CODEVERSE. Google grant revocation is available in your Google Account permissions.",
        );
        connections();
      });
  } catch (e) {
    if ($("#connections-state"))
      $("#connections-state").textContent = e.message;
  }
}
function redrawConnections() {
  const nodes = workspace.payload.nodes || [],
    svg = $(".graph-lines");
  if (!svg) return;
  svg.innerHTML = nodes
    .flatMap((n) =>
      (n.inputs || []).map((id) => {
        const from = nodes.find((x) => x.id === id);
        if (!from) return "";
        const x = (from.x || 30) + 205,
          y = (from.y || 30) + 38,
          tx = n.x || 30,
          ty = (n.y || 30) + 38;
        return `<path d="M ${x},${y} C ${x + 80},${y} ${tx - 80},${ty} ${tx},${ty}" stroke="#73b6a1" stroke-width="2" fill="none"/>`;
      }),
    )
    .join("");
}
function connectLabels(root) {
  root.querySelectorAll("label").forEach((label) => {
    if (label.htmlFor || label.querySelector("input,textarea,select")) return;
    const control = label.nextElementSibling;
    if (control?.matches("input,textarea,select")) {
      control.id ||= "field-" + uniqueId();
      label.htmlFor = control.id;
    }
  });
}
function installNodeExtras(el, node) {
  const select = el.querySelector("#node-inputs");
  const nodes = workspace.payload.nodes || [];
  select.outerHTML = `<fieldset class="input-ports"><legend>Upstream boxes</legend>${nodes
    .filter((n) => n.id !== node.id)
    .map(
      (n) =>
        `<label><input type="checkbox" name="node-input" value="${esc(n.id)}" ${(node.inputs || []).includes(n.id) ? "checked" : ""}>${esc(n.name)}</label>`,
    )
    .join("") || "<small>Add an upstream box to create a connection.</small>"
    }</fieldset>`;
  if (node.kind === "python") {
    if (node.testInput)
      el.querySelector("#python-test-input").value = node.testInput;
    el.querySelector("#node-save").insertAdjacentHTML(
      "afterend",
      '<button id="save-skill-inventory">Save reusable skill</button>',
    );
    el.querySelector("#save-skill-inventory").onclick = () =>
      action(async () => {
        const skills = [...(workspace.payload.skills_inventory || [])];
        skills.push({
          id: uniqueId(),
          kind: "python",
          name: el.querySelector("#node-name").value,
          code: el.querySelector("#node-code").value,
          tested_code: el.querySelector("#node-code").dataset.testedCode,
          testInput: el.querySelector("#python-test-input").value,
          outputName: el.querySelector("#node-output").value,
        });
        await saveWorkspace({ skills_inventory: skills });
        notify("Reusable skill saved. It is available in the inventory.");
      });
  }
  if (node.kind === "gmail") {
    el.querySelector("#node-output").previousElementSibling.insertAdjacentHTML(
      "beforebegin",
      `<label for="gmail-node-operation">Gmail action</label><select id="gmail-node-operation"><option value="draft">Prepare a draft</option><option value="send">Send after workflow review</option></select><label for="gmail-node-to">Recipient</label><input type="email" id="gmail-node-to" value="${esc(node.to || "")}"><label for="gmail-node-subject">Subject</label><input id="gmail-node-subject" value="${esc(node.subject || "")}"><label for="gmail-node-body">Message · use {{input}} for linked data, {{github}} for your username</label><textarea id="gmail-node-body">${esc(node.body || "Hello,\n\n{{input}}\n\n{{github}}")}</textarea>`,
    );
    el.querySelector("#gmail-node-operation").value = node.operation || "draft";
  }
  connectLabels(el);
}

function installAutomationControls() {
  const inventory = $(".inventory>div");
  inventory.insertAdjacentHTML(
    "beforeend",
    `<div class="section-head"><h3>My Python skills</h3><button id="new-skill">+</button></div><div id="skill-shelf">${(workspace.payload.skills_inventory || []).map((s) => `<article class="card" draggable="true" data-skill-template="${esc(s.id)}"><span class="chip">PYTHON</span><h3>${esc(s.name)}</h3><div class="split-actions" style="margin-top:10px"><button data-place-skill="${esc(s.id)}">Place box</button><button data-edit-skill="${esc(s.id)}">Edit</button></div></article>`).join("") || '<p class="form-note">Save reusable Python code here before placing a box.</p>'}</div><div class="section-head"><h3>My datasets</h3><button id="new-dataset">+</button></div><div>${(workspace.payload.datasets || []).map((d) => `<article class="card" draggable="true" data-dataset-template="${esc(d.id)}"><span class="chip blue">${d.type === "csv" ? "▦ CSV" : d.type === "json" ? "{ } JSON" : "≡ TEXT"}</span><h3>${esc(d.name)}</h3><small>${new TextEncoder().encode(d.content || "").length} bytes</small><div class="split-actions" style="margin-top:10px"><button data-place-dataset="${esc(d.id)}">Place</button><button data-preview-dataset="${esc(d.id)}">Preview / edit</button></div></article>`).join("") || '<p class="form-note">Uploaded files can remain unlinked.</p>'}</div>`,
  );
  $("#new-skill").onclick = () => skillModal();
  $("#new-dataset").onclick = () => datasetModal();
  const placeSkill = (id, pos = {}) => {
    const skill = (workspace.payload.skills_inventory || []).find(
      (s) => s.id === id,
    );
    nodeModal(
      {
        ...skill,
        id: uniqueId(),
        kind: "python",
        inputs: [],
        x: pos.x || 40,
        y: pos.y || 40,
        source_skill_id: id,
      },
      "python",
    );
  };
  const placeDataset = (id, pos = {}) => {
    const dataset = (workspace.payload.datasets || []).find((d) => d.id === id);
    nodeModal(
      {
        id: uniqueId(),
        kind: "dataset",
        name: dataset.name,
        dataset: id,
        inputs: [],
        x: pos.x || 40,
        y: pos.y || 40,
        outputName: "dataset.json",
      },
      "dataset",
    );
  };
  document
    .querySelectorAll("[data-place-skill]")
    .forEach((b) => (b.onclick = () => placeSkill(b.dataset.placeSkill)));
  document
    .querySelectorAll("[data-edit-skill]")
    .forEach(
      (b) =>
      (b.onclick = () =>
        skillModal(
          (workspace.payload.skills_inventory || []).find(
            (s) => s.id === b.dataset.editSkill,
          ),
        )),
    );
  document
    .querySelectorAll("[data-place-dataset]")
    .forEach((b) => (b.onclick = () => placeDataset(b.dataset.placeDataset)));
  document
    .querySelectorAll("[data-preview-dataset]")
    .forEach(
      (b) =>
      (b.onclick = () =>
        datasetModal(
          (workspace.payload.datasets || []).find(
            (d) => d.id === b.dataset.previewDataset,
          ),
        )),
    );
  document
    .querySelectorAll("[data-skill-template]")
    .forEach(
      (c) =>
      (c.ondragstart = (e) =>
        e.dataTransfer.setData(
          "text/plain",
          "skill:" + c.dataset.skillTemplate,
        )),
    );
  document
    .querySelectorAll("[data-dataset-template]")
    .forEach(
      (c) =>
      (c.ondragstart = (e) =>
        e.dataTransfer.setData(
          "text/plain",
          "dataset:" + c.dataset.datasetTemplate,
        )),
    );
  const board = $("#board"),
    before = board.ondrop;
  board.ondrop = (e) => {
    const value = e.dataTransfer.getData("text/plain"),
      r = board.getBoundingClientRect(),
      pos = {
        x: Math.max(20, e.clientX - r.left + board.scrollLeft),
        y: Math.max(20, e.clientY - r.top + board.scrollTop),
      };
    if (value.startsWith("skill:")) {
      e.preventDefault();
      placeSkill(value.slice(6), pos);
    } else if (value.startsWith("dataset:")) {
      e.preventDefault();
      placeDataset(value.slice(8), pos);
    } else before(e);
  };
  document.querySelectorAll("[data-node]").forEach(
    (el) =>
    (el.onkeydown = (e) => {
      if (
        !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
          e.key,
        ) ||
        e.target !== el
      )
        return;
      e.preventDefault();
      const n = workspace.payload.nodes.find((n) => n.id === el.dataset.node);
      n.x = Math.max(
        10,
        Math.min(
          1500,
          (n.x || 30) + ({ ArrowLeft: -15, ArrowRight: 15 }[e.key] || 0),
        ),
      );
      n.y = Math.max(
        10,
        Math.min(
          1000,
          (n.y || 30) + ({ ArrowUp: -15, ArrowDown: 15 }[e.key] || 0),
        ),
      );
      el.style.left = n.x + "px";
      el.style.top = n.y + "px";
      redrawConnections();
      clearTimeout(el._saveTimer);
      el._saveTimer = setTimeout(
        () => action(() => saveWorkspace({ nodes: workspace.payload.nodes })),
        250,
      );
    }),
  );
  document
    .querySelectorAll("[data-test-node]")
    .forEach((b) => (b.onclick = () => startFlow(b.dataset.testNode)));
  $("#flow-start").insertAdjacentHTML(
    "afterend",
    '<button id="flow-validate">Validate connections</button>',
  );
  $("#flow-validate").onclick = () =>
    action(async () => {
      const d = await api("v1/glass/automation/validate", {});
      notify(
        "Valid dependency graph: " +
        d.boxes +
        " boxes. Execution order: " +
        d.order.join(" → "),
      );
    });
  $("#run-log").insertAdjacentHTML(
    "beforebegin",
    '<div id="run-history" class="review"></div>',
  );
  renderRunHistory();
}
function renderRunHistory() {
  const target = $("#run-history");
  if (!target) return;
  const runs = workspace.payload.runs || [];
  target.innerHTML =
    "<h3>Run history</h3>" +
    (runs
      .map(
        (r, i) =>
          `<button data-run-history="${i}" style="margin:8px 8px 0 0">${r.status === "completed" ? "✓" : "!"} ${esc(new Date(r.started_at).toLocaleString())} · ${r.elapsed_ms} ms</button>`,
      )
      .join("") ||
      '<p class="muted">No runs yet. Successful and failed runs are retained after reload.</p>');
  target
    .querySelectorAll("[data-run-history]")
    .forEach((b) => (b.onclick = () => renderRun(runs[+b.dataset.runHistory])));
  if (runs.length) renderRun(runs[0]);
}
function renderRun(run) {
  const out = $("#run-log");
  if (!out) return;
  out.innerHTML = `<h3>${run.status === "completed" ? "Workflow complete" : "Workflow needs attention"}</h3>${run.error ? `<p>${esc(run.error)}</p>` : ""}<div class="table-wrap"><table><thead><tr><th>Box</th><th>Status</th><th>Time</th><th>Output file</th></tr></thead><tbody>${run.log.map((l) => `<tr><td>${esc(l.name || l.node)}</td><td>${esc(l.status)}</td><td>${l.elapsed_ms ?? 0} ms</td><td>${run.files[l.node] ? `<button data-file="${esc(l.node)}">${esc(run.files[l.node].name)} ↓</button>` : "No output"}</td></tr>`).join("")}</tbody></table></div><details><summary>Inspect inputs and outputs</summary><pre>${esc(JSON.stringify(run.outputs, null, 2))}</pre></details><button id="run-download">Download complete result</button>`;
  out.querySelectorAll("[data-file]").forEach(
    (b) =>
    (b.onclick = () => {
      const f = run.files[b.dataset.file];
      download(
        f.name,
        f.encoding === "base64"
          ? Uint8Array.from(atob(f.content), (c) => c.charCodeAt(0))
          : f.content,
        f.type,
      );
    }),
  );
  $("#run-download").onclick = () =>
    download("workflow-" + run.id + ".json", JSON.stringify(run, null, 2));
}
async function startFlow(target = null) {
  let direct = false;
  await action(async () => {
    const validation = await api("v1/glass/automation/validate", { target });
    if (validation.sends.length) {
      const el = modal(
        `<h2>Review workflow emails.</h2><p class="muted">Starting this flow sends the configured messages below. Inspect upstream outputs before including them in a message.</p>${validation.sends.map((m) => `<div class="review"><strong>${esc(m.to || "Recipient missing")}</strong><p>${esc(m.subject)}</p><pre>${esc(m.body)}</pre></div>`).join("")}<label><input type="checkbox" id="confirm-flow-mail" style="width:auto"> I verified the recipients and content.</label><button id="confirm-flow-start" class="primary">Start and send reviewed messages</button>`,
      );
      el.querySelector("#confirm-flow-start").onclick = () => {
        if (!el.querySelector("#confirm-flow-mail").checked) {
          notify("Review and confirm the messages first.", true);
          return;
        }
        el.remove();
        performFlow(target, true);
      };
    } else direct = true;
  });
  if (direct) await performFlow(target, false);
}
async function performFlow(target, confirmed) {
  return action(async () => {
    const button = $("#flow-start");
    button.disabled = true;
    button.dataset.busy = "1";
    $("#run-log").textContent = "Running boxes in dependency order…";
    const r = await api("v1/glass/automation/execute", {
      target,
      confirm_email_send: confirmed,
    });
    workspace = await api("v1/glass/state");
    renderRunHistory();
    renderRun(r);
    notify(
      r.status === "completed"
        ? "Workflow completed. Outputs are saved."
        : r.error,
      r.status !== "completed",
    );
  });
}

function skillModal(existing) {
  const el = modal(
    `<div class="eyebrow">REUSABLE PYTHON SKILL</div><h2>${existing ? "Edit skill" : "Create a skill"}</h2><label for="skill-name">Name</label><input id="skill-name" value="${esc(existing?.name || "My Python skill")}"><label for="skill-code">Code · JSON in, JSON out</label><textarea id="skill-code" class="code">${esc(existing?.code || "import json, sys\ninputs = json.load(sys.stdin)\nprint(json.dumps(inputs))")}</textarea><label for="skill-input">Test input JSON array</label><textarea id="skill-input" style="min-height:90px">${esc(existing?.testInput || "[]")}</textarea><label for="skill-output">Output filename</label><input id="skill-output" value="${esc(existing?.outputName || "output.json")}"><div class="split-actions" style="margin-top:20px"><button id="skill-test">Test code</button><button id="skill-save" class="primary">Save to inventory</button></div><pre id="skill-result"></pre>`,
  );
  let testedCode = existing?.tested_code;
  el.querySelector("#skill-test").onclick = () =>
    action(async () => {
      const input = JSON.parse(el.querySelector("#skill-input").value);
      if (!Array.isArray(input))
        throw new Error("Test input must be a JSON array");
      const result = await api("v1/glass/automation/test", {
        code: el.querySelector("#skill-code").value,
        input,
      });
      testedCode = result.tested_code;
      el.querySelector("#skill-result").textContent = JSON.stringify(
        result.output,
        null,
        2,
      );
    });
  el.querySelector("#skill-save").onclick = () =>
    action(async () => {
      const skill = {
        id: existing?.id || uniqueId(),
        name: el.querySelector("#skill-name").value,
        kind: "python",
        code: el.querySelector("#skill-code").value,
        testInput: el.querySelector("#skill-input").value,
        tested_code: testedCode,
        outputName: el.querySelector("#skill-output").value,
      };
      const all = workspace.payload.skills_inventory || [];
      await saveWorkspace({
        skills_inventory: existing
          ? all.map((x) => (x.id === existing.id ? skill : x))
          : [...all, skill],
      });
      el.remove();
      automation();
    });
}
function datasetModal(existing) {
  let encoding = existing?.encoding || "utf8",
    mediaType = existing?.media_type || "text/plain";
  const el = modal(
    `<div class="eyebrow">DATASET INVENTORY</div><h2>${existing ? "Inspect and edit dataset" : "Upload a dataset"}</h2><label for="inventory-dataset-file">Any file · up to 500 KB</label><input id="inventory-dataset-file" type="file"><label for="inventory-dataset-name">Filename</label><input id="inventory-dataset-name" value="${esc(existing?.name || "")}"><label for="inventory-dataset-content">Text content / binary metadata</label><textarea id="inventory-dataset-content" class="code">${esc(existing?.content || "")}</textarea><small id="dataset-encoding"></small><button id="inventory-dataset-save" class="primary" style="margin-top:20px">Save dataset</button><div id="dataset-preview" class="review"></div>`,
  );
  const preview = () => {
    const name = el.querySelector("#inventory-dataset-name").value,
      content = el.querySelector("#inventory-dataset-content").value;
    el.querySelector("#inventory-dataset-content").readOnly =
      encoding === "base64";
    el.querySelector("#dataset-encoding").textContent =
      encoding === "base64"
        ? "Binary data is preserved as base64. Python receives filename, media_type and base64 fields."
        : "CSV is parsed to records; JSON to its native value; other text is passed as text.";
    try {
      const data =
        encoding === "base64"
          ? {
            filename: name,
            encoding,
            media_type: mediaType,
            bytes: Math.floor((content.length * 3) / 4),
          }
          : name.toLowerCase().endsWith(".csv")
            ? parseCSV(content)
            : name.toLowerCase().endsWith(".json")
              ? JSON.parse(content)
              : content;
      el.querySelector("#dataset-preview").textContent = JSON.stringify(
        Array.isArray(data) ? data.slice(0, 5) : data,
        null,
        2,
      ).slice(0, 3000);
    } catch (e) {
      el.querySelector("#dataset-preview").textContent = e.message;
    }
  };
  el.querySelector("#inventory-dataset-file").onchange = () =>
    action(async () => {
      const f = el.querySelector("#inventory-dataset-file").files[0];
      if (!f || f.size > 500000) throw new Error("Choose a file under 500 KB");
      el.querySelector("#inventory-dataset-name").value = f.name;
      mediaType = f.type || "application/octet-stream";
      if (/\.(csv|json|txt|md|yaml|yml|ipynb)$/i.test(f.name)) {
        encoding = "utf8";
        el.querySelector("#inventory-dataset-content").value = await f.text();
      } else {
        encoding = "base64";
        const bytes = new Uint8Array(await f.arrayBuffer());
        let binary = "";
        for (let i = 0; i < bytes.length; i += 8192)
          binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        el.querySelector("#inventory-dataset-content").value = btoa(binary);
      }
      preview();
    });
  el.querySelector("#inventory-dataset-content").oninput = preview;
  el.querySelector("#inventory-dataset-save").onclick = () =>
    action(async () => {
      const name = el.querySelector("#inventory-dataset-name").value,
        content = el.querySelector("#inventory-dataset-content").value,
        type = name.split(".").pop().toLowerCase();
      if (!name || name.length > 200)
        throw new Error("Provide a filename under 200 characters");
      const size =
        encoding === "base64"
          ? atob(content).length
          : new TextEncoder().encode(content).length;
      if (size > 500000) throw new Error("Dataset exceeds 500 KB");
      if (encoding !== "base64" && type === "csv") parseCSV(content);
      if (encoding !== "base64" && type === "json") JSON.parse(content);
      const value = {
        id: existing?.id || uniqueId(),
        name,
        content,
        type,
        encoding,
        media_type: mediaType,
      };
      const all = workspace.payload.datasets || [];
      await saveWorkspace({
        datasets: existing
          ? all.map((d) => (d.id === existing.id ? value : d))
          : [...all, value],
      });
      el.remove();
      automation();
    });
  preview();
}

const devBypassActive = () => {
  const fromQuery = new URLSearchParams(location.search).get("devbypass");
  if (fromQuery === "1") {
    localStorage.setItem("codeverse-dev-bypass", "1");
    return true;
  }
  return (
    localStorage.getItem("codeverse-dev-bypass") === "1" ||
    import.meta.env.VITE_DEV_BYPASS_AUTH === "1"
  );
};
