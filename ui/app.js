"use strict";
/* RE6 ARC Studio front end. Plain JS, no build step. All DOM text goes through textContent / h(). */

// ---------- helpers ----------------------------------------------------------------------
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ICONS = {
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9l-.8-1.2A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  box: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  chev: '<path d="m9 18 6-6-6-6"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  cube: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z"/><path d="M12 9v4M12 17h.01"/>',
  copy: '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"/>',
  trash: '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  undo: '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/>',
  swap: '<path d="m16 3 4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
};
const icon = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24">${ICONS[n] || ""}</svg>`;
function hydrateIcons(root = document) {
  $$("svg[data-icon]", root).forEach(s => { s.setAttribute("viewBox", "0 0 24 24"); s.classList.add("i"); s.innerHTML = ICONS[s.dataset.icon] || ""; });
}
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;       // only ever called with static markup
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(c));
  return el;
}
const fmtSize = n => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MB` : `${(n / 1073741824).toFixed(2)} GB`;
const fmtNum = n => n.toLocaleString();
const baseName = p => p.slice(p.lastIndexOf("/") + 1);
const dirName = p => { const i = p.lastIndexOf("/"); return i < 0 ? "" : p.slice(0, i); };
const debounce = (fn, ms) => { let id; return (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); }; };

let LANG = "zh";
function t(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}
function applyI18n() {
  document.documentElement.lang = LANG;
  $$("[data-i]").forEach(e => e.textContent = t(e.dataset.i));
  $$("[data-ph]").forEach(e => e.placeholder = t(e.dataset.ph));
  $("#btnPrev").title = t("toggle_preview");
}

// ---------- backend bridge -------------------------------------------------------------------
const DEV_BRIDGE = new URLSearchParams(location.search).has("dev");   // http://127.0.0.1:8765/?dev
const hasNativeApi = () => !!(window.pywebview && window.pywebview.api && typeof window.pywebview.api.app_info === "function");
const BACKEND_READY = new Promise(res => {
  if (hasNativeApi() || DEV_BRIDGE) return res();
  window.addEventListener("pywebviewready", () => res(), { once: true });
});
async function call(name, ...args) {
  await BACKEND_READY;
  const r = hasNativeApi() || !DEV_BRIDGE ? await window.pywebview.api[name](...args)
    : await (await fetch("/api/" + name, { method: "POST", body: JSON.stringify(args) })).json();
  if (!r.ok) throw new Error(r.error || "error");
  return r.data;
}

// ---------- state -----------------------------------------------------------------------------
const S = {
  archives: [], rows: [], trees: {}, node: { a: null, dir: "" }, expanded: new Set(),
  sel: new Set(), anchor: -1, view: "details", sort: { k: null, dir: 1 },
  q: "", rx: false, ext: "", recursive: true, list: [], settings: {}, showPreview: true,
};
const thumbCache = new Map();
let previewGen = 0;

function toast(msg, kind = "") {
  const el = h("div", { class: "toast " + kind }, h("span", { html: icon(kind === "err" ? "alert" : kind === "ok" ? "check" : "eye"), style: { marginTop: "2px" } }), h("span", {}, msg));
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "err" ? 7000 : 3200);
}
const fail = e => { toast(String(e.message || e), "err"); try { call("log_js", "fail: " + String(e.stack || e.message || e)); } catch { /* ignore */ } };

// ---------- data ------------------------------------------------------------------------------
async function reloadArchives() { S.archives = await call("archives"); }

async function loadRows(aid) {
  const a = S.archives.find(x => x.id === aid);
  const raw = await call("rows", aid);
  S.rows = S.rows.filter(r => r.a !== aid);
  raw.forEach((r, i) => S.rows.push({
    a: aid, an: a ? a.name : aid, p: r[0], e: r[1], c: r[2], s: r[3], o: r[4], st: r[5],
    k: aid + "|" + r[0].toLowerCase(), d: dirName(r[0]), n: baseName(r[0]), i, ai: S.archives.findIndex(x => x.id === aid),
  }));
  S.trees[aid] = buildTree(S.rows.filter(r => r.a === aid));
}

function buildTree(rows) {
  const root = { ch: new Map(), files: 0, count: 0, path: "", name: "" };
  for (const r of rows) {
    let n = root; n.count++;
    if (r.d) for (const part of r.d.split("/")) {
      let c = n.ch.get(part);
      if (!c) { c = { ch: new Map(), files: 0, count: 0, path: n.path ? n.path + "/" + part : part, name: part }; n.ch.set(part, c); }
      n = c; n.count++;
    }
    n.files++;
  }
  return root;
}

async function openPaths(paths) {
  try {
    const before = new Set(S.archives.map(a => a.id));
    const res = await call("open_paths", paths);
    S.archives = res.archives;
    const fresh = res.opened.filter(id => !before.has(id));
    for (const id of fresh) await loadRows(id);
    res.errors.forEach(e => toast(e, "err"));
    if (!res.opened.length && !res.errors.length) toast(t("no_arc"), "err");
    else if (fresh.length) toast(t("opened_n", { n: fresh.length }), "ok");
    else if (!res.errors.length) toast(t("already"));
    if (fresh.length === 1 && S.archives.length === 1) S.expanded.add(fresh[0]);
    if (fresh.length) { S.node = S.archives.length === 1 ? { a: fresh[0], dir: "" } : { a: null, dir: "" }; }
    recompute(); renderAll();
  } catch (e) { fail(e); }
}
async function refreshArchive(aid) {
  await reloadArchives(); await loadRows(aid); recompute(); renderAll();
}

// ---------- filtering / sorting -----------------------------------------------------------------
function matcher() {
  const q = S.q.trim();
  if (!q) return null;
  if (S.rx) { try { const re = new RegExp(q, "i"); $("#q").style.borderColor = ""; return r => re.test(r.p); } catch { $("#q").style.borderColor = "var(--err)"; return () => false; } }
  $("#q").style.borderColor = "";
  const parts = q.toLowerCase().split(/\s+/);
  return r => { const p = r.p.toLowerCase(); return parts.every(x => p.includes(x)); };
}
function inNode(r, node, recursive = true) {
  if (node.a && r.a !== node.a) return false;
  if (!node.dir) return true;
  return recursive ? (r.d === node.dir || r.d.startsWith(node.dir + "/")) : r.d === node.dir;
}
function recompute() {
  const m = matcher();
  let list = S.rows.filter(r => inNode(r, S.node, S.recursive) && (!S.ext || r.e === S.ext) && (!m || m(r)));
  const { k, dir } = S.sort;
  if (k) {
    const key = { p: r => r.p.toLowerCase(), e: r => r.e, s: r => r.s, c: r => r.c, ratio: r => r.s ? r.c / r.s : 0, a: r => r.an.toLowerCase(), st: r => r.st }[k];
    list = list.map(r => [key(r), r]).sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0) * dir).map(x => x[1]);
  } else list.sort((x, y) => x.ai - y.ai || x.i - y.i);
  S.list = list;
  const keys = new Set(list.map(r => r.k));
  for (const k2 of [...S.sel]) if (!keys.has(k2)) S.sel.delete(k2);
  rebuildExtSelect();
}
function rebuildExtSelect() {
  const sel = $("#extSel");
  const scope = S.rows.filter(r => inNode(r, S.node, S.recursive));
  const cnt = new Map(); scope.forEach(r => cnt.set(r.e, (cnt.get(r.e) || 0) + 1));
  const opts = [...cnt.entries()].sort((a, b) => b[1] - a[1]);
  if (S.ext && !cnt.has(S.ext)) S.ext = "";
  sel.replaceChildren(h("option", { value: "" }, t("all_types")), ...opts.map(([e, n]) => h("option", { value: e }, `.${e}  (${n})`)));
  sel.value = S.ext;
}
const selectedRows = () => S.list.filter(r => S.sel.has(r.k));

// ---------- tree --------------------------------------------------------------------------------------
function renderTree() {
  const root = $("#tree"); root.replaceChildren();
  $("#archCount").textContent = S.archives.length ? String(S.archives.length) : "";
  if (!S.archives.length) return;
  const total = S.rows.length;
  root.append(treeRow({ label: t("all_archives"), count: total, depth: 0, on: !S.node.a, icon: "box", onclick: () => selectNode({ a: null, dir: "" }) }));
  for (const a of S.archives) {
    const tree = S.trees[a.id]; if (!tree) continue;
    const open = S.expanded.has(a.id);
    root.append(treeRow({
      label: a.name, count: a.count, depth: 0, arc: true, edit: a.edits > 0, open, hasKids: tree.ch.size > 0, icon: "cube",
      on: S.node.a === a.id && !S.node.dir, title: a.path,
      onclick: () => selectNode({ a: a.id, dir: "" }), ontoggle: () => toggleExpand(a.id),
      oncontext: e => archiveMenu(e, a),
    }));
    if (open) renderChildren(root, a.id, tree, 1);
  }
}
function renderChildren(root, aid, node, depth) {
  const kids = [...node.ch.values()].sort((x, y) => x.name.localeCompare(y.name));
  for (const child of kids) {
    let n = child, label = child.name;
    while (n.files === 0 && n.ch.size === 1) { n = [...n.ch.values()][0]; label += "/" + n.name; }
    const key = aid + "|" + n.path, open = S.expanded.has(key);
    root.append(treeRow({
      label, count: n.count, depth, open, hasKids: n.ch.size > 0, icon: "folder",
      on: S.node.a === aid && S.node.dir === n.path, title: n.path,
      onclick: () => selectNode({ a: aid, dir: n.path }), ontoggle: () => toggleExpand(key),
      oncontext: e => dirMenu(e, aid, n.path),
    }));
    if (open) renderChildren(root, aid, n, depth + 1);
  }
}
function treeRow(o) {
  const row = h("div", { class: "tn" + (o.on ? " on" : "") + (o.arc ? " arc" : ""), title: o.title || "", style: { paddingLeft: 4 + o.depth * 14 + "px" }, onclick: o.onclick, oncontextmenu: o.oncontext, ondblclick: o.ontoggle },
    h("span", { class: "tw" + (o.open ? " open" : ""), html: o.hasKids ? icon("chev") : "", onclick: e => { e.stopPropagation(); o.ontoggle && o.ontoggle(); } }),
    h("span", { html: icon(o.icon), style: { color: o.arc ? "var(--accent)" : "var(--muted)", display: "flex" } }),
    h("span", { class: "lb" }, o.label),
    o.edit ? h("span", { class: "edit-dot" }) : null,
    h("span", { class: "ct" }, fmtNum(o.count)));
  return row;
}
function toggleExpand(key) { S.expanded.has(key) ? S.expanded.delete(key) : S.expanded.add(key); renderTree(); }
function selectNode(node) {
  S.node = node; S.sel.clear(); S.anchor = -1;
  if (node.a && !node.dir) S.expanded.add(node.a);
  recompute(); renderAll(); $("#scroller").scrollTop = 0; renderList();
}
const rowsUnder = (aid, dir) => S.rows.filter(r => r.st !== "added" && inNode(r, { a: aid, dir }, true));

// ---------- list (virtualised) -------------------------------------------------------------------------------
function columns() {
  const multi = S.archives.length > 1;
  const cols = [["p", t("col_path"), ""], ["e", t("col_type"), ""], ["s", t("col_size"), "r"], ["c", t("col_comp"), "r"], ["ratio", t("col_ratio"), "r"]];
  if (multi) cols.push(["a", t("col_arc"), ""]);
  cols.push(["st", t("col_state"), ""]);
  const tpl = ["minmax(140px,1fr)", "58px", "76px", "76px", "52px", ...(multi ? ["118px"] : []), "64px"].join(" ");
  return { cols, tpl };
}
function renderHead() {
  const head = $("#listHead");
  if (S.view !== "details") { head.hidden = true; return; }
  head.hidden = false;
  const { cols, tpl } = columns();
  head.style.setProperty("--cols", tpl);
  head.replaceChildren(...cols.map(([k, label, cls]) => h("div", { class: cls, onclick: () => cycleSort(k) },
    label, S.sort.k === k ? h("span", { class: "muted" }, S.sort.dir > 0 ? "▲" : "▼") : null)));
}
function cycleSort(k) {
  if (S.sort.k !== k) S.sort = { k, dir: 1 };
  else if (S.sort.dir === 1) S.sort.dir = -1;
  else S.sort = { k: null, dir: 1 };
  recompute(); renderHead(); renderList();
}
function geom() {
  const sc = $("#scroller");
  if (S.view === "details") return { rh: 30, per: 1, sc };
  const w = sc.clientWidth - 24;
  return { rh: 168, per: Math.max(1, Math.floor((w + 10) / 146)), sc };
}
let raf = 0;
function renderList() { cancelAnimationFrame(raf); raf = requestAnimationFrame(drawList); }
function drawList() {
  const { rh, per, sc } = geom();
  const n = S.list.length, rowsN = Math.ceil(n / per);
  $("#spacer").style.height = rowsN * rh + "px";
  $("#empty").hidden = S.archives.length > 0;
  const first = Math.max(0, Math.floor(sc.scrollTop / rh) - 4);
  const last = Math.min(rowsN, Math.ceil((sc.scrollTop + sc.clientHeight) / rh) + 4);
  const inner = $("#inner"); inner.style.transform = `translateY(${first * rh}px)`;
  const frag = document.createDocumentFragment();
  const { tpl } = columns();
  for (let r = first; r < last; r++) {
    if (S.view === "details") frag.append(detailRow(S.list[r], r, tpl));
    else {
      const line = h("div", { class: "grid-row" });
      for (let c = 0; c < per && r * per + c < n; c++) line.append(tile(S.list[r * per + c], r * per + c));
      frag.append(line);
    }
  }
  inner.replaceChildren(frag);
  updateStatus();
}
function detailRow(r, idx, tpl) {
  const pct = r.s && r.c ? r.c / r.s * 100 : 0;
  const ratio = !pct ? "" : pct < 10 ? pct.toFixed(1) + "%" : Math.round(pct) + "%";
  const multi = S.archives.length > 1;
  const el = h("div", { class: "row" + (S.sel.has(r.k) ? " on" : "") + (r.st === "deleted" ? " deleted" : ""), "data-idx": idx },
    h("div", { class: "nm", title: r.p }, h("span", { html: icon(r.e === "tex" ? "image" : "file"), style: { color: r.e === "tex" ? "var(--info)" : "var(--muted)", display: "flex" } }),
      r.d ? h("span", { class: "dir muted" }, r.d + "/") : null, h("span", { class: "fn" }, r.n)),
    h("div", { class: "c" }, h("span", { class: "ext " + r.e }, r.e)),
    h("div", { class: "c r" }, fmtSize(r.s)), h("div", { class: "c r muted" }, r.c ? fmtSize(r.c) : ""), h("div", { class: "c r muted" }, ratio),
    multi ? h("div", { class: "c muted", title: r.an }, r.an) : null,
    h("div", { class: "c" }, r.st ? h("span", { class: "pill " + r.st }, t("st_" + r.st)) : null));
  el.style.setProperty("--cols", tpl);
  return el;
}
const thumbQueue = [], thumbPending = new Set(); let thumbActive = 0;
const tileEls = key => $$(".tile").filter(el => el.dataset.key === key);
function applyThumb(key, src) {
  for (const el of tileEls(key)) { const img = $("img", el), ph = $(".ph", el); img.src = src; img.hidden = false; ph.hidden = true; }
}
function requestThumb(r) {
  if (thumbPending.has(r.k)) return;
  thumbPending.add(r.k); thumbQueue.push(r);
  setTimeout(pumpThumbs, 20);                 // let the freshly built tiles attach first
}
function pumpThumbs() {
  while (thumbActive < 4 && thumbQueue.length) {
    const r = thumbQueue.pop();               // newest first = what is on screen now
    if (!tileEls(r.k).length) { thumbPending.delete(r.k); continue; }
    thumbActive++;
    call("thumb", r.a, r.p, 128)
      .then(v => { thumbCache.set(r.k, v || null); if (v) applyThumb(r.k, v); })
      .catch(() => thumbCache.set(r.k, null))
      .finally(() => { thumbActive--; thumbPending.delete(r.k); pumpThumbs(); });
  }
}
function tile(r, idx) {
  const cached = thumbCache.get(r.k);
  const img = h("img", { hidden: !cached, draggable: "false", ...(cached ? { src: cached } : {}) });
  const ph = h("div", { class: "ph", hidden: !!cached }, "." + r.e);
  const el = h("div", { class: "tile" + (S.sel.has(r.k) ? " on" : "") + (r.st === "deleted" ? " deleted" : ""), "data-idx": idx, "data-key": r.k, title: r.p },
    h("div", { class: "th" }, img, ph), h("div", { class: "tl" }, r.n),
    r.st ? h("span", { class: "tb pill " + r.st, style: { background: "var(--panel)" } }, t("st_" + r.st)) : null);
  if (r.e === "tex" && r.st !== "added" && !thumbCache.has(r.k)) requestThumb(r);
  return el;
}

// ---------- selection & keyboard ------------------------------------------------------------------------------------
function rowFromEvent(e) { const el = e.target.closest("[data-idx]"); return el ? +el.dataset.idx : -1; }
function onListClick(e) {
  const i = rowFromEvent(e);
  if (i < 0) { S.sel.clear(); S.anchor = -1; }
  else {
    const r = S.list[i];
    if (e.shiftKey && S.anchor >= 0) {
      const [a, b] = [Math.min(S.anchor, i), Math.max(S.anchor, i)];
      if (!e.ctrlKey) S.sel.clear();
      for (let x = a; x <= b; x++) S.sel.add(S.list[x].k);
    } else if (e.ctrlKey || e.metaKey) { S.sel.has(r.k) ? S.sel.delete(r.k) : S.sel.add(r.k); S.anchor = i; }
    else { S.sel = new Set([r.k]); S.anchor = i; }
  }
  renderList(); onSelectionChanged();
}
function onSelectionChanged() { updateStatus(); updateExtractButton(); schedulePreview(); }
function onKey(e) {
  if (e.target.matches("input,select,textarea")) { if (e.key === "Escape") e.target.blur(); return; }
  if ($("#viewBrowse").hidden || document.querySelector(".modal-bg")) return;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === "a") { e.preventDefault(); S.list.forEach(r => S.sel.add(r.k)); renderList(); onSelectionChanged(); }
  else if (mod && e.key.toLowerCase() === "f") { e.preventDefault(); $("#q").focus(); $("#q").select(); }
  else if (mod && e.key.toLowerCase() === "c" && S.sel.size) { copyPaths(); }
  else if (e.key === "Escape") { S.sel.clear(); renderList(); onSelectionChanged(); }
  else if (e.key === "Delete" && S.sel.size) { stageDelete(selectedRows()); }
  else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && S.list.length) {
    e.preventDefault();
    const { per } = geom();
    const step = S.view === "tiles" ? per : 1;
    const cur = S.anchor < 0 ? (e.key === "ArrowDown" ? -step : step) : S.anchor;
    const i = Math.max(0, Math.min(S.list.length - 1, cur + (e.key === "ArrowDown" ? step : -step)));
    if (e.shiftKey) S.sel.add(S.list[i].k); else S.sel = new Set([S.list[i].k]);
    S.anchor = i; scrollToIndex(i); renderList(); onSelectionChanged();
  } else if (S.view === "tiles" && (e.key === "ArrowLeft" || e.key === "ArrowRight") && S.list.length) {
    e.preventDefault();
    const i = Math.max(0, Math.min(S.list.length - 1, (S.anchor < 0 ? 0 : S.anchor) + (e.key === "ArrowRight" ? 1 : -1)));
    S.sel = new Set([S.list[i].k]); S.anchor = i; scrollToIndex(i); renderList(); onSelectionChanged();
  }
}
function scrollToIndex(i) {
  const { rh, per, sc } = geom(); const top = Math.floor(i / per) * rh;
  if (top < sc.scrollTop) sc.scrollTop = top; else if (top + rh > sc.scrollTop + sc.clientHeight) sc.scrollTop = top + rh - sc.clientHeight;
}
async function copyPaths() {
  const text = selectedRows().map(r => r.p).join("\n");
  try { await navigator.clipboard.writeText(text); toast(t("copied"), "ok"); }
  catch { const ta = h("textarea", { style: { position: "fixed", opacity: 0 } }); ta.value = text; document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove(); toast(t("copied"), "ok"); }
}

// ---------- status / toolbar -----------------------------------------------------------------------------------------
function updateStatus() {
  const total = S.rows.length;
  $("#stFiles").textContent = S.list.length === total ? t("files_n", { n: fmtNum(total) }) : t("of_total", { n: fmtNum(S.list.length), t: fmtNum(total) });
  const sel = selectedRows();
  $("#stSel").textContent = sel.length ? t("sel_n", { n: fmtNum(sel.length) }) + " · " + fmtSize(sel.reduce((s, r) => s + r.s, 0)) : "";
  const crumbParts = [];
  if (S.archives.length) {
    const a = S.node.a ? S.archives.find(x => x.id === S.node.a) : null;
    crumbParts.push(a ? a.name : t("all_archives"));
    if (S.node.dir) crumbParts.push(S.node.dir);
  }
  const cr = $("#crumb"); cr.hidden = !S.archives.length;
  cr.replaceChildren(h("span", { class: "mono", title: crumbParts.join(" / ") }, crumbParts.join("  /  ")), h("span", {}, t("files_n", { n: fmtNum(S.list.length) })));
}
function updateExtractButton() {
  const n = S.sel.size;
  $("#extractLbl").textContent = n ? t("extract_sel", { n: fmtNum(n) }) : t("extract_shown", { n: fmtNum(S.list.length) });
  $("#btnExtract").disabled = !S.list.length;
}
function updatePending() {
  const n = S.archives.reduce((s, a) => s + a.edits, 0);
  $("#pendingBar").hidden = n === 0;
  $("#pendingText").textContent = t("pending_n", { n });
  const b = $("#tabBadge"); b.hidden = n === 0; b.textContent = n;
}

// ---------- preview ---------------------------------------------------------------------------------------------------------
const schedulePreview = debounce(showPreview, 90);
async function showPreview() {
  const body = $("#prevBody"); const gen = ++previewGen;
  const sel = selectedRows();
  if (!sel.length) { body.replaceChildren(h("div", { class: "muted", style: { margin: "auto", textAlign: "center" } }, t("pv_none"))); return; }
  if (sel.length > 1) {
    const exts = new Map(); sel.forEach(r => exts.set(r.e, (exts.get(r.e) || 0) + 1));
    body.replaceChildren(h("h3", {}, t("pv_multi", { n: fmtNum(sel.length) })), h("div", { class: "muted" }, t("pv_total", { s: fmtSize(sel.reduce((s, r) => s + r.s, 0)) })),
      h("div", { class: "chips" }, [...exts.entries()].map(([e, n]) => h("span", { class: "chip" }, "." + e, h("b", {}, n)))));
    return;
  }
  const r = sel[0];
  body.replaceChildren(h("h3", {}, r.n), h("div", { class: "muted" }, t("pv_loading")));
  if (!S.showPreview) return;
  try {
    const pv = await call("preview", r.a, r.p);
    if (gen !== previewGen) return;
    const kv = [[t("pv_arc"), r.an], [t("pv_size"), `${fmtSize(pv.size)} (${fmtNum(pv.size)} B)`], [t("pv_magic"), pv.magic]];
    let main;
    if (pv.kind === "image") {
      kv.push([t("pv_dim"), `${pv.width} × ${pv.height}`], [t("pv_mips"), pv.mips + (pv.images > 1 ? ` × ${pv.images}` : "")], [t("pv_fmt"), pv.format], [t("pv_code"), String(pv.format_code)], [t("pv_shown"), pv.shown]);
      main = h("div", { class: "checker" }, h("img", { src: pv.image, draggable: "false" }));
    } else main = h("div", {}, h("pre", { class: "hex" }, pv.hex), pv.truncated ? h("div", { class: "muted", style: { marginTop: "6px" } }, t("pv_trunc")) : null, pv.note ? h("div", { class: "err-text" }, pv.note) : null);
    body.replaceChildren(h("h3", {}, r.p), main, h("dl", { class: "kv" }, kv.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])));
  } catch (e) { if (gen === previewGen) body.replaceChildren(h("h3", {}, r.n), h("div", { class: "err-text" }, t("pv_fail") + ": " + e.message)); }
}

// ---------- context menus -----------------------------------------------------------------------------------------------------
function showMenu(e, items) {
  e.preventDefault(); closeMenu();
  const m = h("div", { class: "ctx" }, items.map(it => it === "-" ? h("hr") :
    h("button", { class: it.danger ? "danger" : "", disabled: it.disabled, onclick: () => { closeMenu(); it.run(); } }, h("span", { html: icon(it.icon || "file"), style: { display: "flex" } }), it.label, it.sc ? h("span", { class: "sc" }, it.sc) : null)));
  document.body.append(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(e.clientX, innerWidth - r.width - 8) + "px"; m.style.top = Math.min(e.clientY, innerHeight - r.height - 8) + "px";
}
function closeMenu() { $$(".ctx").forEach(x => x.remove()); }
function onListContext(e) {
  const i = rowFromEvent(e);
  if (i >= 0 && !S.sel.has(S.list[i].k)) { S.sel = new Set([S.list[i].k]); S.anchor = i; renderList(); onSelectionChanged(); }
  const sel = selectedRows();
  if (!sel.length) return e.preventDefault();
  const single = sel.length === 1 ? sel[0] : null;
  const allTex = sel.every(r => r.e === "tex");
  const extractable = sel.filter(r => r.st !== "added");
  const items = [
    { icon: "download", label: t("m_extract"), run: () => extractRows(extractable, "raw"), disabled: !extractable.length },
    allTex ? { icon: "image", label: t("m_extract_dds"), run: () => extractRows(extractable, "dds") } : null,
    allTex ? { icon: "image", label: t("m_extract_png"), run: () => extractRows(extractable, "png") } : null,
    "-",
    single && single.st !== "added" ? { icon: "swap", label: t("m_replace"), run: () => replaceRow(single) } : null,
    sel.some(r => r.st === "modified" || r.st === "deleted" || r.st === "added") ? { icon: "undo", label: t("m_restore"), run: () => unstageRows(sel) } : null,
    { icon: "trash", label: t("m_delete"), danger: true, run: () => stageDelete(sel), sc: "Del" },
    "-",
    { icon: "copy", label: t("m_copy"), run: copyPaths, sc: "Ctrl+C" },
    { icon: "list", label: t("m_select_all"), run: () => { S.list.forEach(r => S.sel.add(r.k)); renderList(); onSelectionChanged(); }, sc: "Ctrl+A" },
  ].filter(Boolean);
  showMenu(e, items);
}
function archiveMenu(e, a) {
  showMenu(e, [
    { icon: "download", label: t("m_extract_all"), run: () => extractRows(rowsUnder(a.id, ""), "raw") },
    { icon: "plus", label: t("m_add"), run: () => addFile(a.id, "") },
    { icon: "shield", label: t("m_verify"), run: () => verifyArchive(a) },
    "-",
    { icon: "folder", label: t("m_reveal"), run: () => call("reveal", a.path).catch(fail) },
    { icon: "x", label: t("m_close"), run: () => closeArchive(a.id) },
  ]);
}
function dirMenu(e, aid, dir) {
  showMenu(e, [
    { icon: "download", label: t("m_extract_dir"), run: () => extractRows(rowsUnder(aid, dir), "raw") },
    { icon: "plus", label: t("m_add"), run: () => addFile(aid, dir) },
    { icon: "copy", label: t("m_copy"), run: () => navigator.clipboard.writeText(dir).then(() => toast(t("copied"), "ok")) },
  ]);
}
async function closeArchive(aid) {
  S.archives = await call("close_archive", aid).catch(e => { fail(e); return S.archives; });
  S.rows = S.rows.filter(r => r.a !== aid); delete S.trees[aid];
  if (S.node.a === aid) S.node = { a: null, dir: "" };
  recompute(); renderAll();
}

// ---------- staged edits -----------------------------------------------------------------------------------------------------------
const groupByArchive = rows => { const g = new Map(); rows.forEach(r => { if (!g.has(r.a)) g.set(r.a, []); g.get(r.a).push(r); }); return g; };
async function replaceRow(r) {
  try {
    const f = await call("pick_file", r.e === "tex" ? "tex" : "any"); if (!f) return;
    await call("stage_replace", r.a, r.p, f);
    toast(t("replaced", { p: r.n }), "ok"); await refreshArchive(r.a);
  } catch (e) { fail(e); }
}
async function stageDelete(rows) {
  try {
    for (const [aid, rs] of groupByArchive(rows)) { await call("stage_delete", aid, rs.map(r => r.p)); await refreshArchive(aid); }
    toast(t("staged_del", { n: rows.length }), "ok");
  } catch (e) { fail(e); }
}
async function unstageRows(rows) {
  try { for (const [aid, rs] of groupByArchive(rows)) { await call("unstage", aid, rs.map(r => r.p)); await refreshArchive(aid); } } catch (e) { fail(e); }
}
async function addFile(aid, dir) {
  try {
    const f = await call("pick_file", "any"); if (!f) return;
    const name = f.split(/[\\/]/).pop();
    const input = h("input", { class: "input", value: (dir ? dir + "/" : "") + name, style: { width: "100%" } });
    const ok = await modal(t("add_title"), null, [h("label", { class: "field" }, h("span", {}, t("add_path")), input), h("div", { class: "muted mono", style: { fontSize: "11.5px" } }, f)], t("add_ok"));
    if (!ok) return;
    await call("stage_add", aid, f, input.value.trim());
    toast(t("added", { p: input.value.trim() }), "ok"); await refreshArchive(aid);
  } catch (e) { fail(e); }
}

// ---------- modal / tasks -------------------------------------------------------------------------------------------------------------
function modal(title, sub, content, okLabel, { cancel = true } = {}) {
  return new Promise(resolve => {
    const done = v => { bg.remove(); resolve(v); };
    const bg = h("div", { class: "modal-bg", onmousedown: e => { if (e.target === bg && cancel) done(false); } },
      h("div", { class: "modal" }, h("h2", {}, title), sub ? h("div", { class: "sub" }, sub) : null, ...content,
        h("div", { class: "foot" }, cancel ? h("button", { class: "btn", onclick: () => done(false) }, t("cancel")) : null,
          okLabel ? h("button", { class: "btn primary", onclick: () => done(true) }, okLabel) : null)));
    document.body.append(bg);
    const inp = $("input.input", bg); if (inp) { inp.focus(); inp.select(); }
    bg.addEventListener("keydown", e => { if (e.key === "Escape" && cancel) done(false); if (e.key === "Enter" && okLabel && e.target.tagName === "INPUT") done(true); });
  });
}
async function runTask(tid, title, render) {
  const bar = h("i"), cur = h("div", { class: "muted mono", style: { marginTop: "8px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } }, "");
  const cancelBtn = h("button", { class: "btn" }, t("cancel"));
  const closeBtn = h("button", { class: "btn primary", hidden: true }, t("close"));
  const result = h("div");
  const bg = h("div", { class: "modal-bg" }, h("div", { class: "modal" }, h("h2", {}, title), h("div", { class: "prog", style: { width: "100%", marginTop: "12px" } }, bar), cur, result, h("div", { class: "foot" }, cancelBtn, closeBtn)));
  document.body.append(bg);
  cancelBtn.onclick = () => call("cancel", tid);
  $("#stTask").hidden = false;
  let snap;
  for (;;) {
    snap = await call("task", tid);
    const pct = snap.total ? snap.done / snap.total * 100 : 0;
    bar.style.width = pct + "%"; $("#stProg").style.width = pct + "%";
    cur.textContent = `${fmtNum(snap.done)} / ${fmtNum(snap.total)}  ${snap.current}`;
    $("#stTaskLbl").textContent = title;
    if (snap.state !== "running") break;
    await new Promise(r => setTimeout(r, 100));
  }
  $("#stTask").hidden = true;
  cur.remove(); cancelBtn.hidden = true; closeBtn.hidden = false;
  const okState = snap.state === "done";
  result.append(h("div", { style: { margin: "12px 0 4px", fontWeight: 600, color: okState ? "var(--ok)" : "var(--err)" } }, snap.state === "cancelled" ? t("cancelled") : okState ? t("done") : t("failed")));
  if (okState || snap.state === "cancelled") result.append(render(snap));
  if (snap.error_count) result.append(h("div", { class: "err-text" }, t("errors_n", { n: snap.error_count })), h("div", { class: "errlist" }, snap.errors.join("\n")));
  await new Promise(r => { closeBtn.onclick = () => { bg.remove(); r(); }; closeBtn.focus(); });
  return snap;
}

// ---------- extract ---------------------------------------------------------------------------------------------------------------------
async function onExtractButton() {
  const rows = (S.sel.size ? selectedRows() : S.list).filter(r => r.st !== "added");
  extractRows(rows, S.settings.convert || "raw");
}
async function extractRows(rows, preset) {
  rows = rows.filter(r => r.st !== "added");
  if (!rows.length) return;
  const groups = groupByArchive(rows);
  const hasTex = rows.some(r => r.e === "tex");
  let convert = hasTex ? preset : "raw";
  const dest = h("input", { class: "input", readonly: true, value: S.settings.last_out_dir || "", style: { flex: 1 } });
  const browse = h("button", { class: "btn", onclick: async () => { try { const d = await call("pick_folder", "last_out_dir"); if (d) dest.value = d; } catch (e) { fail(e); } } }, t("ex_browse"));
  const opts = [["raw", "ex_raw"], ["dds", "ex_dds"], ["png", "ex_png"]].map(([v, k]) => {
    const radio = h("input", { type: "radio", name: "cv", value: v, ...(v === convert ? { checked: true } : {}) });
    const el = h("label", { class: "opt" + (v === convert ? " on" : "") }, radio, h("div", {}, h("b", {}, t(k)), h("small", {}, t(k + "_d"))));
    radio.addEventListener("change", () => { convert = v; $$(".opt").forEach(o => o.classList.toggle("on", $("input", o).checked)); });
    return el;
  });
  const sub = h("input", { type: "checkbox", ...(S.settings.subfolder !== false ? { checked: true } : {}) });
  const over = h("input", { type: "checkbox", ...(S.settings.overwrite !== false ? { checked: true } : {}) });
  const body = [
    h("div", { class: "field" }, h("span", {}, t("ex_dest")), h("div", { class: "frow", style: { margin: 0 } }, dest, browse)),
    hasTex ? h("div", { class: "field" }, h("span", {}, t("ex_fmt")), h("div", {}, opts)) : null,
    h("div", { class: "field" }, h("label", { class: "chk" }, sub, t("ex_sub")), h("label", { class: "chk" }, over, t("ex_over"))),
  ];
  const go = await modal(t("ex_title"), t("ex_scope", { n: fmtNum(rows.length), m: groups.size }), body, t("ex_start"));
  if (!go) return;
  if (!dest.value) return toast(t("ex_no_dest"), "err");
  try {
    const items = [...groups.entries()].map(([archive, rs]) => ({ archive, paths: rs.map(r => r.p) }));
    const tid = await call("extract", items, dest.value, convert, sub.checked, over.checked);
    S.settings = await call("set_settings", {});
    await runTaskWithOpen(tid, t("extract"), s => h("div", {}, t("ex_done", { w: fmtNum(s.result.written || 0), s: fmtNum(s.result.skipped || 0) })), dest.value);
  } catch (e) { fail(e); }
}
async function runTaskWithOpen(tid, title, render, dir) {
  return runTask(tid, title, s => h("div", {}, render(s), h("div", { class: "frow" }, h("button", { class: "btn", onclick: () => call("reveal", dir).catch(fail) }, h("span", { html: icon("folder"), style: { display: "flex" } }), t("open_dir")))));
}
async function verifyArchive(a) {
  try {
    const tid = await call("verify", a.id);
    await runTask(tid, t("m_verify"), s => h("div", {}, s.result.bad ? t("verify_bad", { n: s.result.bad }) : t("verify_ok", { n: fmtNum(s.result.checked) })));
  } catch (e) { fail(e); }
}

// ---------- repack view -------------------------------------------------------------------------------------------------------------------
const R = { aid: "", folder: "", includeNew: true, scan: null, saved: null, pending: [] };
async function renderRepack() {
  const root = $("#repackInner");
  if (!S.archives.find(a => a.id === R.aid)) { R.aid = S.archives[0] ? S.archives[0].id : ""; R.scan = null; }
  R.pending = R.aid ? await call("pending", R.aid).catch(() => []) : [];
  const aSel = h("select", { class: "input", style: { flex: 1 }, onchange: e => { R.aid = e.target.value; R.scan = null; R.saved = null; renderRepack(); } },
    S.archives.length ? S.archives.map(a => h("option", { value: a.id, ...(a.id === R.aid ? { selected: true } : {}) }, `${a.name}  (${fmtNum(a.count)})${a.edits ? "  •" : ""}`)) : [h("option", {}, t("rp_none_arc"))]);
  const fIn = h("input", { class: "input", value: R.folder, placeholder: "D:\\mods\\extracted", oninput: e => { R.folder = e.target.value; } });
  const scanBtn = h("button", { class: "btn primary", disabled: !R.aid, onclick: doScan }, h("span", { html: icon("search"), style: { display: "flex" } }), t("rp_scan"));
  const newChk = h("input", { type: "checkbox", ...(R.includeNew ? { checked: true } : {}), onchange: e => { R.includeNew = e.target.checked; } });
  const canSave = R.aid && R.pending.length > 0;
  root.replaceChildren(
    h("div", { class: "card" }, h("h2", {}, h("span", { class: "n" }, "1"), t("rp_1")), h("p", { class: "hint" }, t("rp_1h")), h("div", { class: "frow" }, aSel, !S.archives.length ? h("button", { class: "btn", onclick: pickAndOpen }, t("open_arc")) : null)),
    h("div", { class: "card" }, h("h2", {}, h("span", { class: "n" }, "2"), t("rp_2")), h("p", { class: "hint" }, t("rp_2h") + " " + t("hint_dds")),
      h("div", { class: "frow" }, fIn, h("button", { class: "btn", onclick: async () => { try { const d = await call("pick_folder", "last_out_dir"); if (d) { R.folder = d; fIn.value = d; } } catch (e) { fail(e); } } }, t("ex_browse")), scanBtn),
      h("div", { class: "frow" }, h("label", { class: "chk" }, newChk, t("rp_new"))),
      R.scan ? scanResult() : null),
    h("div", { class: "card" }, h("h2", {}, h("span", { class: "n" }, "3"), t("rp_3")), h("p", { class: "hint" }, t("rp_3h")),
      pendingTable(),
      h("div", { class: "frow" },
        h("button", { class: "btn primary", disabled: !canSave, onclick: () => doSave(false) }, t("rp_saveas")),
        h("button", { class: "btn", disabled: !canSave, onclick: () => doSave(true) }, t("rp_overwrite")),
        h("span", { class: "spacer" }),
        R.pending.length ? h("button", { class: "btn ghost", onclick: async () => { await call("unstage", R.aid); R.scan = null; await refreshArchive(R.aid); } }, t("discard_all")) : null),
      R.saved ? h("div", { style: { marginTop: "12px" } }, h("div", { class: "pill modified", style: { color: "var(--ok)", borderColor: "var(--ok)" } }, t("done")),
        h("div", { class: "mono", style: { margin: "6px 0", userSelect: "text" } }, t("rp_saved", { out: R.saved.out })),
        h("div", { class: "muted" }, t("rp_saved_d", { m: R.saved.modified, a: R.saved.added, r: R.saved.removed, e: fmtNum(R.saved.entries), s: fmtSize(R.saved.size) })),
        R.saved.backup ? h("div", { class: "muted mono" }, t("rp_bak", { b: R.saved.backup })) : null) : null));
}
function scanResult() {
  const s = R.scan;
  const rows = s.results.filter(r => r.status !== "unchanged" && r.status !== "ignored");
  const chip = (label, n, color) => h("span", { class: "chip" }, label, h("b", { style: color && n ? { color } : {} }, n));
  return h("div", {},
    h("div", { class: "muted mono", style: { marginTop: "8px", userSelect: "text" } }, s.root),
    h("div", { class: "chips" }, chip(t("rp_modified"), s.modified, "var(--warn)"), chip(t("rp_newf"), s.new, "var(--ok)"), chip(t("rp_err"), s.errors, "var(--err)"),
      chip(t("rp_unch"), s.results.filter(r => r.status === "unchanged").length), chip(t("rp_ign"), s.ignored)),
    rows.length ? h("div", { class: "tbl-wrap" }, h("table", { class: "tbl" }, h("thead", {}, h("tr", {}, h("th", {}, t("col_state")), h("th", {}, t("col_path")))),
      h("tbody", {}, rows.map(r => h("tr", {}, h("td", {}, h("span", { class: "pill " + r.status }, t("st_" + r.status))),
        h("td", { class: "p" }, r.path, r.error ? h("div", { class: "err-text" }, r.error) : null)))))) : null);
}
function pendingTable() {
  if (!R.pending.length) return h("div", { class: "muted", style: { marginBottom: "4px" } }, t("rp_none_pending"));
  return h("div", {}, h("div", { class: "muted", style: { marginBottom: "6px" } }, t("rp_pending") + " · " + R.pending.length),
    h("div", { class: "tbl-wrap" }, h("table", { class: "tbl" }, h("tbody", {}, R.pending.map(p => h("tr", {},
      h("td", { style: { width: "80px" } }, h("span", { class: "pill " + (p.kind === "replace" ? "modified" : p.kind === "add" ? "added" : "deleted") }, t(p.kind === "replace" ? "st_modified" : p.kind === "add" ? "st_added" : "st_deleted"))),
      h("td", { class: "p" }, p.path), h("td", { style: { width: "60px", textAlign: "right" } }, h("button", { class: "btn sm ghost", onclick: async () => { await call("unstage", R.aid, [p.path]); R.scan = null; await refreshArchive(R.aid); } }, t("rp_remove")))))))));
}
async function doScan() {
  if (!R.folder) { try { const d = await call("pick_folder", "last_out_dir"); if (!d) return; R.folder = d; } catch (e) { return fail(e); } }
  try { R.scan = await call("stage_folder", R.aid, R.folder, R.includeNew); R.saved = null; await reloadArchives(); await loadRows(R.aid); recompute(); renderAll(); }
  catch (e) { fail(e); }
}
async function doSave(overwrite) {
  const arc = S.archives.find(a => a.id === R.aid); if (!arc) return;
  try {
    let out = arc.path;
    if (overwrite) { if (!await modal(t("rp_overwrite"), arc.path, [], t("rp_overwrite"))) return; }
    else { out = await call("pick_save", arc.name); if (!out) return; }
    const tid = await call("save", R.aid, out, true);
    const snap = await runTask(tid, t("save_arc"), s => h("div", {}, t("rp_saved_d", { m: s.result.modified, a: s.result.added, r: s.result.removed, e: fmtNum(s.result.entries), s: fmtSize(s.result.size) })));
    if (snap.state === "done") { R.saved = snap.result; R.scan = null; if (snap.result.reloaded) await refreshArchive(R.aid); else { await reloadArchives(); renderAll(); } }
  } catch (e) { fail(e); }
}
async function pickAndOpen() {
  try { const f = await call("pick_arcs"); if (f.length) await openPaths(f); } catch (e) { fail(e); }
}
async function pickFolderAndOpen() {
  try { const d = await call("pick_folder", "last_open_dir"); if (d) await openPaths([d]); } catch (e) { fail(e); }
}

// ---------- tabs / theme / lang / layout --------------------------------------------------------------------------------------------------
function setTab(tab) {
  $$(".tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  $("#viewBrowse").hidden = tab !== "browse"; $("#viewRepack").hidden = tab !== "repack";
  if (tab === "repack") renderRepack(); else renderList();
}
function applyTheme(mode) {
  const dark = mode === "dark" || (mode === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  $("#btnTheme svg").innerHTML = ICONS[dark ? "moon" : "sun"];
}
function setView(v) {
  S.view = v; S.settings.view = v; call("set_settings", { view: v }).catch(() => {});
  $$("#viewSeg button").forEach(b => b.classList.toggle("on", b.dataset.view === v));
  renderHead(); $("#scroller").scrollTop = 0; renderList();
}
function setPreviewVisible(on) {
  S.showPreview = on; $("#prev").hidden = !on; $("#btnPrev").classList.toggle("on", on);
  call("set_settings", { preview: on }).catch(() => {}); renderList(); if (on) schedulePreview();
}
function renderAll() {
  applyI18n(); renderTree(); renderHead(); renderList(); updateExtractButton(); updatePending(); showPreview();
  if (!$("#viewRepack").hidden) renderRepack();
}
function initResizer() {
  const rz = $("#resizer"), side = $("#side");
  rz.addEventListener("mousedown", e => {
    e.preventDefault(); rz.classList.add("drag");
    const move = ev => { side.style.width = Math.max(200, Math.min(560, ev.clientX)) + "px"; renderList(); };
    const up = () => { rz.classList.remove("drag"); removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
    addEventListener("mousemove", move); addEventListener("mouseup", up);
  });
}

// ---------- boot ---------------------------------------------------------------------------------------------------------------------------------
window.App = { onDropped: paths => { $("#drop").hidden = true; openPaths(paths); }, S, call };

const reportError = msg => { try { call("log_js", String(msg)); } catch { /* ignore */ } };
addEventListener("error", e => reportError(`error: ${e.message} @ ${e.filename}:${e.lineno}`));
addEventListener("unhandledrejection", e => reportError(`rejection: ${e.reason && e.reason.message || e.reason}`));

async function boot() {
  hydrateIcons();
  let info = { settings: {}, initial: [] };
  try { info = await call("app_info"); } catch (e) { fail(e); reportError("app_info failed: " + e.message); }
  S.settings = info.settings; LANG = S.settings.lang || "zh"; S.recursive = S.settings.recursive !== false;
  $("#recur").checked = S.recursive; S.view = S.settings.view || "details";
  applyTheme(S.settings.theme || "auto"); $$("#viewSeg button").forEach(b => b.classList.toggle("on", b.dataset.view === S.view));
  setPreviewVisible(S.settings.preview !== false);

  $("#btnOpen").onclick = pickAndOpen; $("#emptyOpen").onclick = pickAndOpen; $("#btnOpenDir").onclick = pickFolderAndOpen;
  $("#btnLang").onclick = () => { LANG = LANG === "zh" ? "en" : "zh"; call("set_settings", { lang: LANG }); renderAll(); rebuildExtSelect(); };
  $("#btnTheme").onclick = () => { const cur = document.documentElement.dataset.theme; const next = cur === "dark" ? "light" : "dark"; call("set_settings", { theme: next }); applyTheme(next); };
  $("#btnPrev").onclick = () => setPreviewVisible(!S.showPreview);
  $$(".tabs button").forEach(b => b.onclick = () => setTab(b.dataset.tab));
  $$("#viewSeg button").forEach(b => b.onclick = () => setView(b.dataset.view));
  $("#q").oninput = debounce(e => { S.q = e.target.value; recompute(); renderList(); updateExtractButton(); }, 120);
  $("#rx").onclick = e => { S.rx = !S.rx; e.currentTarget.classList.toggle("on", S.rx); recompute(); renderList(); };
  $("#extSel").onchange = e => { S.ext = e.target.value; recompute(); renderList(); updateExtractButton(); };
  $("#recur").onchange = e => { S.recursive = e.target.checked; call("set_settings", { recursive: S.recursive }); recompute(); renderList(); updateExtractButton(); };
  $("#btnExtract").onclick = onExtractButton;
  $("#pendingReview").onclick = () => setTab("repack");
  $("#pendingDiscard").onclick = async () => { for (const a of S.archives.filter(x => x.edits)) { await call("unstage", a.id); await loadRows(a.id); } await reloadArchives(); R.scan = null; recompute(); renderAll(); };

  const sc = $("#scroller");
  sc.addEventListener("scroll", renderList, { passive: true });
  sc.addEventListener("click", onListClick); sc.addEventListener("contextmenu", onListContext);
  sc.addEventListener("dblclick", e => { const i = rowFromEvent(e); if (i >= 0 && !S.showPreview) setPreviewVisible(true); });
  new ResizeObserver(renderList).observe(sc);
  addEventListener("keydown", onKey); addEventListener("mousedown", e => { if (!e.target.closest(".ctx")) closeMenu(); }); addEventListener("blur", closeMenu);
  addEventListener("dragenter", e => { if (e.dataTransfer && [...e.dataTransfer.types].includes("Files")) $("#drop").hidden = false; });
  addEventListener("dragleave", e => { if (!e.relatedTarget) $("#drop").hidden = true; });
  addEventListener("drop", () => { $("#drop").hidden = true; });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if ((S.settings.theme || "auto") === "auto") applyTheme("auto"); });
  initResizer();

  try { await reloadArchives(); for (const a of S.archives) await loadRows(a.id); } catch (e) { fail(e); }
  recompute(); renderAll();
  if (info.initial && info.initial.length) openPaths(info.initial);
}
boot();
