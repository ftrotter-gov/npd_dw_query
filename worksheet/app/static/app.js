"use strict";

let editor = null;
let current = null;         // current worksheet object
let activeRunId = null;
let activeWs = null;

const $ = (id) => document.getElementById(id);

// ── Monaco boot ──────────────────────────────────────────────────────────
require.config({ paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" } });
require(["vs/editor/editor.main"], () => {
  editor = monaco.editor.create($("editor"), {
    value: "-- Pick a worksheet on the left, or type SQL here.\n",
    language: "sql",
    theme: "vs-dark",
    fontSize: 13,
    minimap: { enabled: false },
    automaticLayout: true,
    scrollBeyondLastLine: false,
  });
  boot();
});

async function boot() {
  await loadWorksheets();
  await loadScripts();
  await refreshStatus();
  setInterval(refreshStatus, 20000);
  wireUI();
}

// ── status bar ───────────────────────────────────────────────────────────
async function refreshStatus() {
  let s;
  try { s = await (await fetch("/api/status")).json(); }
  catch { return; }
  const conn = $("conn"), ident = $("ident");
  if (!s.pat_loaded) {
    conn.className = "pill pill-off"; conn.textContent = "● no PAT";
    ident.textContent = `role ${s.role_cfg || "?"} · wh ${s.warehouse_cfg || "?"}`;
  } else if (s.connected) {
    conn.className = "pill pill-on"; conn.textContent = "● Snowflake connected";
    ident.textContent = `${s.account} · ${s.role} · ${s.warehouse} · ${s.user}`;
  } else {
    conn.className = "pill pill-err"; conn.textContent = "● connect failed";
    ident.textContent = (s.error || "").slice(0, 120);
  }
  $("idlenote").textContent = s.idle_shutdown_minutes
    ? `auto-stops after ${s.idle_shutdown_minutes} min idle` : "";
  if (!$("s3path").value && s.default_output) $("s3path").value = s.default_output;
  $("runBtn").disabled = !s.pat_loaded || !current;
}

// ── lists ────────────────────────────────────────────────────────────────
async function loadWorksheets() {
  const data = await (await fetch("/api/worksheets")).json();
  const box = $("wsList"); box.innerHTML = "";
  let lastGroup = null;
  data.worksheets.forEach((w) => {
    if (w.group !== lastGroup) {
      const g = document.createElement("div"); g.className = "side-title";
      g.textContent = w.group; box.appendChild(g); lastGroup = w.group;
    }
    const el = document.createElement("div");
    el.className = "item"; el.dataset.wid = w.id;
    el.innerHTML = `<span class="dot dot-${w.behavior}"></span>${w.title}`;
    el.onclick = () => selectWorksheet(w, el);
    box.appendChild(el);
  });
}

async function loadScripts() {
  const data = await (await fetch("/api/scripts")).json();
  const box = $("scriptList"); box.innerHTML = "";
  data.scripts.forEach((sc) => {
    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `${sc.title}<span class="grp">${sc.summary || sc.group}</span>`;
    el.onclick = () => viewScript(sc.path);
    box.appendChild(el);
  });
}

function selectWorksheet(w, el) {
  current = w;
  document.querySelectorAll("#wsList .item, #scriptList .item")
    .forEach((n) => n.classList.remove("sel"));
  el.classList.add("sel");
  $("wsTitle").textContent = w.title;
  $("wsDesc").textContent = w.description || "";
  const badge = $("wsBadge");
  badge.textContent = w.behavior === "hangs" ? "HANGS until Path A" : "works now";
  badge.className = "badge badge-" + w.behavior;
  editor.setValue(w.sql || "");
  monaco.editor.setModelLanguage(editor.getModel(), "sql");
  $("saveS3").checked = !!w.s3_default;
  $("runBtn").disabled = !current;
}

async function viewScript(path) {
  const data = await (await fetch("/api/scripts/source?path=" + encodeURIComponent(path))).json();
  current = null;
  $("wsTitle").textContent = path;
  $("wsDesc").textContent = "Reference source (read-only view). Copy SQL into a worksheet to run.";
  $("wsBadge").textContent = ""; $("wsBadge").className = "badge";
  editor.setValue(data.source || "");
  monaco.editor.setModelLanguage(editor.getModel(), "python");
  $("runBtn").disabled = true;
}

// ── run ──────────────────────────────────────────────────────────────────
function wireUI() {
  $("patBtn").onclick = () => { $("patModal").classList.remove("hidden"); $("patInput").focus(); };
  $("patCancel").onclick = () => $("patModal").classList.add("hidden");
  $("patSave").onclick = savePat;
  $("patInput").addEventListener("keydown", (e) => { if (e.key === "Enter") savePat(); });
  $("patClear").onclick = async () => { await fetch("/api/pat", { method: "DELETE" }); refreshStatus(); };
  $("runBtn").onclick = runQuery;
  $("cancelBtn").onclick = cancelRun;
  document.querySelectorAll(".tab").forEach((t) => t.onclick = () => switchTab(t.dataset.tab));
}

async function savePat() {
  const pat = $("patInput").value.trim();
  if (!pat) return;
  $("patErr").textContent = "connecting…";
  try {
    const r = await (await fetch("/api/pat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pat }),
    })).json();
    $("patInput").value = "";
    if (r.connected) {
      $("patModal").classList.add("hidden"); $("patErr").textContent = "";
    } else {
      $("patErr").textContent = "stored, but connect failed: " + (r.error || "unknown");
    }
    refreshStatus();
  } catch (e) { $("patErr").textContent = "error: " + e; }
}

async function runQuery() {
  if (!current) return;
  const sql = editor.getValue();
  const s3 = $("s3path").value.trim();
  const save = $("saveS3").checked;
  const payload = current.mode === "relay"
    ? { mode: "relay", sql, s3_uri: s3, filename: current.filename }
    : { mode: "inline", sql, s3_uri: s3, save_to_s3: save };

  $("consolePane").textContent = "";
  $("resultPane").innerHTML = '<div class="empty">running…</div>';
  switchTab("console");
  setRunning(true);
  logLine(`[client] submitting (${current.mode})…`);

  let res;
  try {
    res = await (await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })).json();
  } catch (e) { logLine("[client] submit failed: " + e, "err"); setRunning(false); return; }
  if (!res.run_id) { logLine("[client] " + (res.detail || "no run id"), "err"); setRunning(false); return; }
  activeRunId = res.run_id;
  openWs(res.run_id);
}

function openWs(runId) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/run/${runId}/ws`);
  activeWs = ws;
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.t === "log") logLine(m.line);
    else if (m.t === "end") endRun(m);
  };
  ws.onerror = () => logLine("[client] websocket error", "err");
  ws.onclose = () => { if (activeRunId) { /* server ended */ } };
}

function endRun(m) {
  setRunning(false);
  $("runStatus").textContent = "status: " + m.status;
  if (m.status === "done" && m.result) renderResult(m.result);
  else if (m.status === "cancelled") $("resultPane").innerHTML = '<div class="empty">cancelled.</div>';
  else if (m.status === "error") { switchTab("console"); $("resultPane").innerHTML = '<div class="empty">error — see Console.</div>'; }
  activeRunId = null; activeWs = null;
}

async function cancelRun() {
  if (!activeRunId) return;
  logLine("[client] cancel requested…", "warn");
  await fetch(`/api/run/${activeRunId}/cancel`, { method: "POST" });
}

function renderResult(r) {
  const pane = $("resultPane");
  if (r.kind === "table") {
    let html = "";
    if (r.s3) html += `<div class="s3note">✓ written → ${r.s3}</div>`;
    html += `<div class="muted">${r.row_count} row(s)${r.truncated ? " (preview truncated)" : ""}</div>`;
    html += "<table class='result'><thead><tr>" +
      r.columns.map((c) => `<th>${esc(c)}</th>`).join("") + "</tr></thead><tbody>";
    r.rows.forEach((row) => {
      html += "<tr>" + row.map((v) => `<td>${v === null ? "<span class='muted'>NULL</span>" : esc(String(v))}</td>`).join("") + "</tr>";
    });
    html += "</tbody></table>";
    pane.innerHTML = html;
    switchTab("result");
  } else {
    pane.innerHTML = `<div class="s3note">${esc(r.text || "done")}</div>`;
    switchTab("result");
  }
}

// ── helpers ──────────────────────────────────────────────────────────────
function setRunning(on) {
  $("runBtn").disabled = on || !current;
  $("cancelBtn").disabled = !on;
  $("runStatus").textContent = on ? "running…" : $("runStatus").textContent;
}
function logLine(line, cls) {
  const pane = $("consolePane");
  const span = document.createElement("span");
  let klass = cls;
  if (!klass) {
    if (/error|✗|fatal|traceback/i.test(line)) klass = "err";
    else if (/warn|still working|hang/i.test(line)) klass = "warn";
    else if (/✓|done|connection established/i.test(line)) klass = "ok";
  }
  if (klass) span.className = "logline-" + klass;
  span.textContent = line + "\n";
  pane.appendChild(span);
  pane.scrollTop = pane.scrollHeight;
}
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("tab-active", t.dataset.tab === name));
  $("resultPane").classList.toggle("hidden", name !== "result");
  $("consolePane").classList.toggle("hidden", name !== "console");
}
function esc(s) { return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
