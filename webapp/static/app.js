/* SignalGuard local web app — vanilla JS, no build step, no emoji: SVG line icons only. */
(() => {
  "use strict";

  // ------------------------------------------------------------------ icons (24px line icons, Lucide-style)
  const P = {
    dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    play: '<polygon points="7 4 20 12 7 20 7 4"/>',
    chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    workflow: '<rect x="3" y="3" width="8" height="8" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect x="13" y="13" width="8" height="8" rx="2"/>',
    database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    rss: '<path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/>',
    filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    trend: '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    down: '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
    arrowRight: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
    activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    split: '<path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8.3a4 4 0 0 0-1.172-2.872L3 3"/><path d="m15 9 6-6"/>',
    flask: '<path d="M9 3h6"/><path d="M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7 15h10"/>',
    radar: '<path d="M19.07 4.93A10 10 0 0 0 6.99 3.34"/><path d="M4 6h.01"/><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35"/><path d="M16.24 7.76A6 6 0 1 0 8.23 16.67"/><path d="M12 18h.01"/><path d="M17.99 11.66A6 6 0 0 1 15.77 16.67"/><circle cx="12" cy="12" r="2"/><path d="m13.41 10.59 5.66-5.66"/>',
    star: '<path d="m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
    news: '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>',
    refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  };
  const icon = (name, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || ""}</svg>`;

  // ------------------------------------------------------------------ utils
  const $ = (sel, root = document) => root.querySelector(sel);
  const app = $("#app"), pagebar = $("#pagebar");
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const api = async (path, opts) => {
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  };
  const fmt = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
  const pct = (v, d = 0) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(d)} %`);
  const SOURCE = { github: "GitHub", github_releases: "Releases", arxiv: "arXiv", hackernews: "Hacker News", medium: "Medium", huggingface: "Hugging Face" };
  const VCOLOR = { v0: "var(--v0)", "v1.1": "var(--v11)", v2: "var(--v2)" };
  const state = { overview: null, bench: null, signals: null, run: null, poll: null };

  const riskBadge = (r) => (r && r.risk_level ? `<span class="badge ${esc(r.risk_level)}">${esc(r.risk_level)}</span>` : '<span class="faint">—</span>');
  const catTag = (c) => (c && c !== "NONE" ? `<span class="tag">${esc(c.toLowerCase())}</span>` : "");
  const srcTag = (s) => `<span class="tag">${esc(SOURCE[s] || s)}</span>`;
  const meter = (v) => `<div class="score"><div class="meter"><span style="width:${Math.max(0, Math.min(100, v || 0))}%"></span></div><span class="mono">${v ?? "—"}</span></div>`;
  const header = (crumb, title, sub, actions = "") => {
    pagebar.innerHTML = `<div><div class="crumb">${esc(crumb)}</div><h1>${esc(title)}</h1>${sub ? `<p>${sub}</p>` : ""}</div><div class="actions">${actions}</div>`;
  };
  const emptyState = (ic, title, text) => `<div class="empty"><div><div class="ico" style="margin:0 auto 12px">${icon(ic, "lg")}</div><h4>${title}</h4><p>${text}</p></div></div>`;
  const skeleton = () => `<div class="grid g4">${'<div class="panel kpi"><div class="skeleton" style="height:14px;width:60%"></div><div class="skeleton" style="height:30px;width:45%;margin-top:16px"></div><div class="skeleton" style="height:12px;width:70%;margin-top:12px"></div></div>'.repeat(4)}</div>`;

  // ------------------------------------------------------------------ navigation
  const NAV = [["", "Vue d'ensemble", "dashboard"], ["news", "Actualités", "news"], ["run", "Analyse", "play"], ["benchmarks", "Benchmarks", "chart"], ["architecture", "Architecture", "workflow"], ["explorer", "Dataset", "database"]];
  $("#nav").innerHTML = NAV.map(([k, label, ic]) => `<a href="#/${k}" data-page="${k}">${icon(ic)}<span>${label}</span></a>`).join("");

  // ------------------------------------------------------------------ theme
  const themeBtn = $("#theme-toggle");
  const paintTheme = () => {
    const dark = document.documentElement.dataset.theme === "dark";
    themeBtn.innerHTML = `${icon(dark ? "sun" : "moon", "sm")}<span>${dark ? "Thème clair" : "Thème sombre"}</span>`;
  };
  try { const saved = localStorage.getItem("sg-theme"); if (saved === "dark") document.documentElement.dataset.theme = "dark"; } catch { /* ignore */ }
  paintTheme();
  themeBtn.addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark";
    if (dark) delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = "dark";
    try { localStorage.setItem("sg-theme", dark ? "light" : "dark"); } catch { /* ignore */ }
    paintTheme();
  });

  // ------------------------------------------------------------------ drawer
  const drawer = $("#drawer"), backdrop = $("#drawer-backdrop");
  const closeDrawer = () => { drawer.classList.remove("open"); backdrop.classList.remove("open"); drawer.setAttribute("aria-hidden", "true"); };
  backdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => e.key === "Escape" && closeDrawer());
  const openDrawer = (head, body) => {
    drawer.innerHTML = `<div class="drawer-head"><button class="icon-btn close" aria-label="Fermer">${icon("x", "sm")}</button>${head}</div><div class="drawer-body">${body}</div>`;
    $(".close", drawer).addEventListener("click", closeDrawer);
    drawer.classList.add("open"); backdrop.classList.add("open"); drawer.setAttribute("aria-hidden", "false"); drawer.scrollTop = 0;
  };

  const RUBRIC = [["novelty", "Nouveauté", 25], ["technical_relevance", "Pertinence technique", 30], ["applicability", "Applicabilité", 25], ["timeliness", "Actualité", 20]];
  const rubricHtml = (r) => (!r || r.novelty === undefined || r.novelty === null ? "" :
    `<div class="block-title">Rubric de pertinence</div><div class="rubric">${RUBRIC.map(([k, label, max]) =>
      `<div class="row"><span class="muted">${label}</span><div class="meter"><span style="width:${(100 * (r[k] || 0)) / max}%"></span></div><span class="mono">${r[k] ?? "—"}/${max}</span></div>`).join("")}</div>`);
  const listHtml = (title, items) => (items && items.length ? `<div class="block-title">${title}</div><ul class="list">${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "");
  const profileTags = (p) => {
    if (!p) return "";
    const t = [];
    if (p.is_lure) t.push(["ko", `Dépôt-leurre · score ${p.lure_score}`]);
    if (p.injection_detected) t.push(["ko", "Injection de prompt détectée"]);
    if (p.explicit_breaking_marker) t.push(["info", "Marqueur de compatibilité"]);
    if (p.security_marker) t.push(["MEDIUM", "Marqueur de sécurité"]);
    if (p.release && p.release.bump) t.push(["neutral", `Release ${p.release.bump}${p.release.integration_package ? " · sous-paquet" : ""}`]);
    return t.length ? `<div class="chips" style="margin-top:10px">${t.map(([c, l]) => `<span class="badge plain ${c}">${esc(l)}</span>`).join("")}</div>` : "";
  };

  function signalDrawer(s, gold) {
    const rel = s.relevance || {}, risk = s.risk || {}, llm = risk.llm_view;
    const head = `<div class="eyebrow">${esc(s.signal_id)}</div><h3>${esc(s.title)}</h3>
      <div class="chips" style="margin-top:0">${srcTag(s.source)} ${riskBadge(risk)} ${catTag(risk.risk_category)}
        ${risk.breaking_changes ? '<span class="badge plain info">Breaking change</span>' : ""}
        ${risk.triaged ? '<span class="badge plain neutral">Chemin rapide</span>' : ""}
        ${rel.used_fallback || risk.used_fallback ? '<span class="badge plain ko">Fallback</span>' : ""}</div>${profileTags(s.profile)}`;
    const body = `
      <div class="block-title">Évaluation</div>
      <div class="kv">
        <span class="k">Pertinence</span><span class="v">${meter(rel.score)}</span>
        ${gold ? `<span class="k">Référence</span><span class="v">${meter(gold.relevance_score)}</span>
        <span class="k">Risque attendu</span><span class="v">${riskBadge(gold)} ${catTag(gold.risk_category)}</span>` : ""}
        ${llm ? `<span class="k">Avis brut du LLM</span><span class="v">${riskBadge(llm)} ${catTag(llm.risk_category)}</span>` : ""}
        ${risk.evidence_strength ? `<span class="k">Force des preuves</span><span class="v mono">${esc(risk.evidence_strength)}</span>` : ""}
      </div>
      ${rel.reasoning ? `<div class="block-title">Raisonnement</div><p style="margin:0;color:var(--text-2)">${esc(rel.reasoning)}</p>` : ""}
      ${rubricHtml(rel)}
      ${listHtml("Préoccupations", risk.concerns)}
      ${listHtml("Preuves vérifiées dans le signal", risk.evidence)}
      ${listHtml("Citations rejetées (introuvables)", risk.rejected_evidence)}
      ${listHtml("Ajustements déterministes du risque", risk.adjustments)}
      ${listHtml("Ajustements déterministes de la pertinence", rel.adjustments)}
      ${s.description ? `<div class="block-title">Contenu du signal</div><div class="desc">${esc(s.description)}</div>` : ""}
      ${s.url ? `<p style="margin-top:18px"><a class="btn" href="${esc(s.url)}" target="_blank" rel="noopener">${icon("external", "sm")}Ouvrir la source</a></p>` : ""}`;
    openDrawer(head, body);
  }

  // ------------------------------------------------------------------ charts
  function barChart(rows, { max = 1, digits = 3, lowerIsBetter = false } = {}) {
    const w = 300, h = 180, pad = { t: 26, b: 30, l: 8, r: 8 }, n = rows.length;
    const plotH = h - pad.t - pad.b, slot = (w - pad.l - pad.r) / n, bw = Math.min(56, slot - 26);
    const vals = rows.map((r) => r.mean).filter((v) => v !== null && v !== undefined);
    const best = vals.length ? (lowerIsBetter ? Math.min(...vals) : Math.max(...vals)) : null;
    const y = (v) => pad.t + plotH - (plotH * Math.max(0, Math.min(v, max))) / max;
    const grid = [0.5, 1].map((f) => `<line class="grid-line" x1="${pad.l}" x2="${w - pad.r}" y1="${y(max * f)}" y2="${y(max * f)}" stroke-dasharray="3 4"/>`).join("");
    const bars = rows.map((r, i) => {
      const cx = pad.l + slot * (i + 0.5);
      const label = `<text x="${cx}" y="${h - 9}" text-anchor="middle">${esc(r.label)}${r.n > 1 ? ` · n=${r.n}` : ""}</text>`;
      if (r.mean === null || r.mean === undefined) return `${label}<text x="${cx}" y="${pad.t + plotH - 6}" text-anchor="middle">n/a</text>`;
      const top = y(r.mean), isBest = n > 1 && r.mean === best;
      const err = r.std ? `<g stroke="var(--text)" stroke-opacity=".45" stroke-width="1.4"><line x1="${cx}" x2="${cx}" y1="${y(r.mean + r.std)}" y2="${y(Math.max(0, r.mean - r.std))}"/><line x1="${cx - 5}" x2="${cx + 5}" y1="${y(r.mean + r.std)}" y2="${y(r.mean + r.std)}"/><line x1="${cx - 5}" x2="${cx + 5}" y1="${y(Math.max(0, r.mean - r.std))}" y2="${y(Math.max(0, r.mean - r.std))}"/></g>` : "";
      return `<rect x="${cx - bw / 2}" y="${top}" width="${bw}" height="${Math.max(1, pad.t + plotH - top)}" rx="5" fill="${r.color}" opacity="${isBest || n === 1 ? 1 : 0.75}"/>${err}
        <text class="val" x="${cx}" y="${Math.max(14, (r.std ? y(r.mean + r.std) : top) - 7)}" text-anchor="middle">${fmt(r.mean, digits)}</text>${label}`;
    }).join("");
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img">${grid}<line x1="${pad.l}" x2="${w - pad.r}" y1="${pad.t + plotH}" y2="${pad.t + plotH}" stroke="var(--border-strong)"/>${bars}</svg>`;
  }

  // ------------------------------------------------------------------ data
  const metric = (s, key) => (s && s.metrics && s.metrics[key]) || null;
  const findSummary = (bench, gold, split, version) => ((bench.gold[gold] || {})[split] || []).find((s) => s.version === version);
  async function loadOverview() { state.overview = await api("/api/overview"); paintStatus(); return state.overview; }
  async function loadBench() { if (!state.bench) state.bench = await api("/api/benchmarks"); return state.bench; }
  async function loadSignals() { if (!state.signals) state.signals = (await api("/api/signals")).signals; return state.signals; }
  function paintStatus() {
    const o = state.overview; if (!o) return;
    $("#provider-status").classList.toggle("warn", !o.api_key);
    $("#provider-sub").textContent = `${o.provider} · ${o.api_key ? "clé active" : "aucune clé"}`;
  }

  // ------------------------------------------------------------------ overview
  async function pageHome() {
    header("Plateforme", "Vue d'ensemble", "Veille IA/ML multi-agents : pertinence, risque et synthèse vérifiée.",
      `<a class="btn" href="#/benchmarks">${icon("chart", "sm")}Benchmarks</a><a class="btn primary" href="#/run">${icon("play", "sm")}Nouvelle analyse</a>`);
    app.innerHTML = skeleton();
    const [o, b] = await Promise.all([loadOverview(), loadBench()]);
    const gold = b.gold["v4.1"] ? "v4.1" : "v4";
    const get = (split, v, key) => metric(findSummary(b, gold, split, v), key);
    const inj = b.injection || {};
    const kpi = (ic, label, to, from, deltaText, positive, foot) => `
      <div class="panel kpi fade-in"><div class="label"><span class="ico">${icon(ic, "sm")}</span>${label}</div>
        <div class="value">${to}</div>
        <div class="foot">${deltaText ? `<span class="delta ${positive ? "" : "neg"}">${deltaText}</span>` : ""}<span>${from ? `contre ${from} · ` : ""}${foot}</span></div></div>`;
    const a0 = get("test", "v0", "risk.accuracy"), a2 = get("test", "v2", "risk.accuracy");
    const r0 = get("test", "v0", "risk.medium_recall"), r2 = get("test", "v2", "risk.medium_recall");
    const m0 = get("dev", "v0", "relevance.mae"), m2 = get("dev", "v2", "relevance.mae");
    const i1 = inj["v1.1"] ? inj["v1.1"].risky_signals_predicted_low_under_attack : null;
    const i2 = inj.v2 ? inj.v2.risky_signals_predicted_low_under_attack : null;
    const d = (a, b2, k = 1, digits = 3) => (a && b2 ? `${b2.mean - a.mean >= 0 ? "+" : ""}${((b2.mean - a.mean) * k).toFixed(digits)}` : "");

    const evalRows = o.evaluation.items.map((it) => {
      const done = it.runs_done * it.signals + it.current_run_signals;
      const ratio = Math.min(1, done / (o.evaluation.target_runs * it.signals));
      return `<div class="eval-row"><span class="mono">${esc(it.version)} · ${it.split.toUpperCase()}</span><div class="progress"><span style="width:${(ratio * 100).toFixed(1)}%"></span></div><span class="mono faint" style="text-align:right">${it.runs_done}/3</span></div>`;
    }).join("");

    const steps = [
      ["rss", "Collecte et normalisation", "6 sources, déduplication par source:id", "Python"],
      ["filter", "Profilage et tri du risque", "Leurres, injections, releases, marqueurs", "Python"],
      ["gauge", "Pertinence", "Rubric à 4 critères, sortie Pydantic", "LLM"],
      ["shield", "Risque", "Preuves ancrées, arbitrage tracé", "LLM"],
      ["zap", "Chemin rapide", "Mêmes règles sans appel LLM", "Python"],
      ["doc", "Synthèse vérifiée", "Faits calculés, identifiants contrôlés", "LLM"],
    ];

    app.innerHTML = `
      <div class="intro fade-in">
        <div class="panel"><div class="panel-body">
          <div class="eyebrow">AI signals · Risk · Agno workflow</div>
          <h2>Des signaux tech <span>fiables, explicables</span> et protégés contre la manipulation.</h2>
          <p>SignalGuard collecte les nouveautés IA/ML, les note avec un rubric explicite, évalue leurs risques à partir de preuves vérifiées,
            neutralise les injections de prompt et produit un digest dont chaque affirmation est rattachée à un signal réel.</p>
          <div class="actions"><a class="btn primary" href="#/run">${icon("play", "sm")}Lancer une analyse</a><a class="btn" href="#/architecture">${icon("workflow", "sm")}Voir l'architecture</a></div>
        </div></div>
        <div class="panel"><div class="panel-head"><div><h3>Pipeline</h3><div class="sub">Le LLM n'intervient que là où un jugement est nécessaire</div></div></div>
          <div class="panel-body" style="padding-top:4px;padding-bottom:4px"><ul class="pipeline">${steps.map(([ic, t, dsc, kind]) =>
            `<li><span class="ico">${icon(ic, "sm")}</span><div><div class="t">${t}</div><div class="d">${dsc}</div></div><span class="badge plain ${kind === "LLM" ? "ok" : "neutral"}">${kind}</span></li>`).join("")}</ul></div></div>
      </div>

      <div class="section-head"><div><h2>Impact mesuré</h2><p>Référence ${gold}. TEST = signaux non utilisés pendant le développement.</p></div></div>
      <div class="grid g4">
        ${kpi("target", "Accuracy du risque · TEST", fmt(a2 && a2.mean), a0 && fmt(a0.mean), d(a0, a2), true, "v0")}
        ${kpi("alert", "Rappel MEDIUM · TEST", fmt(r2 && r2.mean), r0 && fmt(r0.mean), d(r0, r2), true, "v0")}
        ${kpi("lock", "Risques masqués par injection", pct(i2), i1 !== null ? pct(i1) : null, i1 !== null && i2 !== null ? `${((i2 - i1) * 100).toFixed(0)} pts` : "", true, "v1.1")}
        ${kpi("trend", "Erreur de pertinence · DEV", fmt(m2 && m2.mean, 1), m0 && fmt(m0.mean, 1), d(m0, m2, 1, 1), true, "v0 · MAE")}
      </div>

      <div class="grid g3 section">
        <div class="panel fade-in"><div class="panel-head"><div><h3>Configuration LLM</h3><div class="sub">Fournisseur et modèles par rôle</div></div><span class="ico">${icon("cpu", "sm")}</span></div>
          <div class="panel-body"><div class="kv">
            <span class="k">Fournisseur</span><span class="v">${esc(o.provider)}</span>
            <span class="k">Pertinence</span><span class="v mono">${esc(o.models.relevance)}</span>
            <span class="k">Risque</span><span class="v mono">${esc(o.models.risk)}</span>
            <span class="k">Synthèse</span><span class="v mono">${esc(o.models.synthesis)}</span>
            <span class="k">Cadence</span><span class="v">${o.max_rpm ? `${o.max_rpm} req/min · offre gratuite` : "illimitée"}</span>
          </div></div></div>
        <div class="panel fade-in"><div class="panel-head"><div><h3>Qualité logicielle</h3><div class="sub">Mesuré, testé, reproductible</div></div><span class="ico">${icon("flask", "sm")}</span></div>
          <div class="panel-body"><div class="kv">
            <span class="k">Tests automatisés</span><span class="v"><b>${o.tests}</b> hors ligne</span>
            <span class="k">Dataset figé</span><span class="v">${o.dataset.signals} signaux · DEV ${o.dataset.dev} / TEST ${o.dataset.test}</span>
            <span class="k">Appels LLM de risque</span><span class="v"><b>−50 %</b> grâce au tri</span>
            <span class="k">Citations inventées</span><span class="v">rejetées automatiquement</span>
          </div></div></div>
      </div>`;
  }

  // ------------------------------------------------------------------ run page
  const STEPS = { load_signals: "Chargement des signaux", normalize: "Normalisation et déduplication", profile_and_triage: "Profilage et tri du risque",
    analysis: "Analyse parallèle", merge_assessments: "Fusion des évaluations", synthesis: "Synthèse vérifiée" };

  async function pageRun() {
    header("Plateforme", "Analyse", "Exécute le vrai pipeline sur cette machine. Chaque lancement consomme le quota du fournisseur LLM.");
    const o = state.overview || await loadOverview();
    app.innerHTML = `
      <div class="run-layout">
        <div class="panel"><div class="panel-head"><div><h3>Paramètres</h3><div class="sub">Version, données et modèle</div></div></div>
          <div class="panel-body">
            <div class="field"><label>Version</label>
              <div class="seg" id="f-version"><button data-v="v2" class="on">v2 · Workflow</button><button data-v="v1.1">v1.1</button><button data-v="v0">v0</button></div></div>
            <div class="field"><label for="f-mode">Source des signaux</label>
              <select class="input" id="f-mode"><option value="frozen">Dataset figé (reproductible)</option><option value="live">Sources en direct</option></select></div>
            <div class="field" id="row-split"><label for="f-split">Sous-ensemble</label>
              <select class="input" id="f-split"><option value="dev">DEV · 48 signaux</option><option value="test">TEST · 24 signaux</option><option value="">Tout · 72 signaux</option></select></div>
            <div class="field" id="row-max"><label for="f-max">Nombre de signaux</label><input class="input" id="f-max" type="number" min="1" max="72" value="8" /></div>
            <div class="field" id="row-limit" hidden><label for="f-limit">Signaux par source</label><input class="input" id="f-limit" type="number" min="1" max="10" value="3" /></div>
            <div class="field"><label for="f-model">Modèle (optionnel, toutes les étapes v2)</label>
              <input class="input" id="f-model" placeholder="${esc(o.models.relevance)}" list="models" />
              <datalist id="models"><option value="openai/gpt-oss-20b"></option><option value="openai/gpt-oss-120b"></option></datalist></div>
            <label class="check" style="margin:4px 0 16px"><input type="checkbox" id="f-llm" checked />Synthèse rédigée par le LLM</label>
            <button class="btn primary block" id="f-run">${icon("play", "sm")}Lancer l'analyse</button>
            <div class="stepper" id="stepper"></div>
          </div></div>
        <div id="run-output" class="panel">${emptyState("inbox", "Aucune analyse en cours", "Configure les paramètres puis lance une analyse. Le digest et chaque signal évalué apparaîtront ici.")}</div>
      </div>`;

    let version = "v2";
    $("#f-version").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      version = b.dataset.v; [...$("#f-version").children].forEach((x) => x.classList.toggle("on", x === b));
    });
    $("#f-mode").addEventListener("change", (e) => {
      const live = e.target.value === "live";
      $("#row-split").hidden = live; $("#row-max").hidden = live; $("#row-limit").hidden = !live;
    });
    $("#f-run").addEventListener("click", async () => {
      const body = { version, mode: $("#f-mode").value, split: $("#f-split").value || null, max_signals: +$("#f-max").value,
        limit: +$("#f-limit").value, llm_synthesis: $("#f-llm").checked, model: $("#f-model").value };
      $("#f-run").disabled = true;
      try {
        const { job_id } = await api("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        pollRun(job_id);
      } catch (err) {
        $("#run-output").innerHTML = `<div class="panel-body"><div class="callout error">${icon("alert", "sm")}<span>${esc(err.message)}</span></div></div>`;
        $("#f-run").disabled = false;
      }
    });
    if (state.run && state.run.status === "done") renderRunResult(state.run);
  }

  function renderStepper(job) {
    const el = $("#stepper"); if (!el) return;
    const done = new Set(job.stage.completed);
    el.innerHTML = Object.entries(STEPS).map(([k, label]) => {
      const cls = done.has(k) ? "done" : (job.status === "running" && job.stage.current === k ? "current" : "");
      return `<div class="step ${cls}"><span class="dot">${done.has(k) ? icon("check", "sm") : ""}</span>${label}</div>`;
    }).join("") + `<div class="meta-line">${job.elapsed_s}s${job.triage ? ` · risque LLM ${job.triage.risk_llm.length} · chemin rapide ${job.triage.risk_fast_path.length}` : ""}</div>`;
    el.querySelectorAll(".step.done svg").forEach((s) => { s.style.width = "12px"; s.style.height = "12px"; s.style.strokeWidth = "3"; });
  }

  function pollRun(jobId) {
    clearInterval(state.poll);
    $("#run-output").innerHTML = emptyState("activity", "Analyse en cours", "Les étapes du workflow Agno s'affichent dans le panneau de gauche.");
    state.poll = setInterval(async () => {
      let job; try { job = await api(`/api/runs/${jobId}`); } catch { return; }
      renderStepper(job);
      if (job.status === "done" || job.status === "error") {
        clearInterval(state.poll);
        const btn = $("#f-run"); if (btn) btn.disabled = false;
        if (job.status === "error") { $("#run-output").innerHTML = `<div class="panel-body"><div class="callout error">${icon("alert", "sm")}<span>${esc(job.error)}</span></div></div>`; return; }
        state.run = job; renderRunResult(job);
      }
    }, 1200);
  }

  const mult = (s) => ({ CRITICAL: 2, HIGH: 1.5, MEDIUM: 1, LOW: 0.8 }[s.risk.risk_level] || 1);

  function renderRunResult(job) {
    const out = $("#run-output"); if (!out) return;
    out.classList.remove("panel");
    const r = job.result, d = r.digest, f = d.facts || {}, syn = d.synthesis || {};
    const byId = Object.fromEntries(r.signals.map((s) => [s.signal_id, s]));
    const ranked = [...r.signals].sort((a, b) => (b.relevance.score || 0) * mult(b) - (a.relevance.score || 0) * mult(a));
    const recs = (d.recommendations || []).map((rec) => (typeof rec === "string" ? { action: rec, signal_ids: [] } : rec));
    const keys = (d.key_signals || []).filter((k) => typeof k === "object");
    out.innerHTML = `
      <div class="stack fade-in">
        <div class="panel"><div class="panel-head"><div><h3>Digest · ${esc(job.params.version)}</h3><div class="sub">${d.total_signals} signaux · ${job.elapsed_s}s · ${r.fallbacks} fallback(s)</div></div>
          <span class="badge plain ${syn.mode === "llm" ? "ok" : "neutral"}">Synthèse ${esc(syn.mode || "—")}</span></div>
          <div class="panel-body">
            ${syn.used_fallback ? `<div class="callout info" style="margin-bottom:12px">${icon("info", "sm")}<span>Synthèse déterministe utilisée : ${esc(syn.fallback_reason || "")}</span></div>` : ""}
            ${syn.rejected_signal_ids && syn.rejected_signal_ids.length ? `<div class="callout info" style="margin-bottom:12px">${icon("info", "sm")}<span>Identifiants inventés par le LLM et rejetés : ${syn.rejected_signal_ids.map(esc).join(", ")}</span></div>` : ""}
            <p class="summary">${esc(d.executive_summary)}</p>
            <div class="chips">
              ${f.high_relevance_signals !== undefined ? `<span class="chip">Haute pertinence <b>${f.high_relevance_signals}</b></span>` : ""}
              ${f.risk_levels ? Object.entries(f.risk_levels).filter(([, n]) => n).map(([k, n]) => `<span class="chip">${k} <b>${n}</b></span>`).join("") : ""}
              ${f.breaking_changes ? `<span class="chip">Breaking changes <b>${f.breaking_changes}</b></span>` : ""}
              ${r.triage ? `<span class="chip">Risque via LLM <b>${r.triage.risk_llm.length}</b></span><span class="chip">Chemin rapide <b>${r.triage.risk_fast_path.length}</b></span>` : ""}
            </div></div></div>
        <div class="grid g2">
          <div class="panel"><div class="panel-head"><div><h3>Signaux clés</h3><div class="sub">Cités par la synthèse</div></div></div><div class="panel-body" style="padding-top:4px;padding-bottom:4px">
            ${keys.map((k, i) => `<div class="item"><span class="n">${i + 1}</span><div><div class="t">${esc(k.title || k.signal_id)}</div><div class="d">${esc(k.why_it_matters || "")}</div>
              <div class="refs"><span class="ref" data-id="${esc(k.signal_id)}">${esc(k.signal_id)}</span></div></div></div>`).join("") || '<p class="muted">Aucun.</p>'}</div></div>
          <div class="panel"><div class="panel-head"><div><h3>Recommandations</h3><div class="sub">Chaque action est rattachée à des signaux réels</div></div></div><div class="panel-body" style="padding-top:4px;padding-bottom:4px">
            ${recs.map((rec, i) => `<div class="item"><span class="n">${i + 1}</span><div><div class="t">${esc(rec.action)}</div>
              <div class="refs">${(rec.signal_ids || []).slice(0, 6).map((id) => `<span class="ref" data-id="${esc(id)}">${esc(((byId[id] || {}).title || id).slice(0, 40))}</span>`).join("")}</div></div></div>`).join("")}</div></div>
        </div>
        <div class="panel"><div class="panel-head"><div><h3>Signaux évalués</h3><div class="sub">Classés par priorité · cliquer pour le détail</div></div>
          <div class="seg" id="risk-filter"><button class="on" data-f="all">Tous</button><button data-f="risk">Avec risque</button><button data-f="high">Haute pertinence</button></div></div>
          <div class="table-wrap"><table><thead><tr><th>Source</th><th>Signal</th><th>Pertinence</th><th>Risque</th><th>Traitement</th></tr></thead><tbody id="sig-body"></tbody></table></div></div>
      </div>`;
    const draw = (filter) => {
      const rows = ranked.filter((s) => filter === "all" || (filter === "risk" ? s.risk.risk_level !== "LOW" || s.risk.risk_category !== "NONE" : (s.relevance.score || 0) >= 70));
      $("#sig-body").innerHTML = rows.map((s) => `<tr class="clickable" data-id="${esc(s.signal_id)}">
        <td>${srcTag(s.source)}</td>
        <td class="title-cell"><div class="t">${esc(s.title)}</div><div class="s">${esc(s.relevance.reasoning || "")}</div></td>
        <td>${meter(s.relevance.score)}</td>
        <td>${riskBadge(s.risk)} ${catTag(s.risk.risk_category)}</td>
        <td>${s.risk.triaged ? '<span class="badge plain neutral">Chemin rapide</span>' : '<span class="badge plain ok">LLM</span>'}</td></tr>`).join("")
        || `<tr><td colspan="5" class="muted">Aucun signal pour ce filtre.</td></tr>`;
    };
    draw("all");
    $("#risk-filter").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      [...$("#risk-filter").children].forEach((x) => x.classList.toggle("on", x === b)); draw(b.dataset.f);
    });
    out.addEventListener("click", (e) => { const el = e.target.closest("[data-id]"); if (el && byId[el.dataset.id]) signalDrawer(byId[el.dataset.id]); });
  }

  // ------------------------------------------------------------------ benchmarks
  const METRICS = [
    ["risk.accuracy", "Accuracy du risque", 1, false, 3], ["risk.macro_f1_observed", "Macro-F1 du risque", 1, false, 3],
    ["risk.medium_recall", "Rappel MEDIUM", 1, false, 3], ["risk.category_accuracy", "Exactitude des catégories", 1, false, 3],
    ["relevance.mae", "Erreur de pertinence (MAE)", 40, true, 1], ["relevance.spearman", "Corrélation de Spearman", 1, false, 3],
    ["relevance.ndcg_at_10", "NDCG@10", 1, false, 3], ["risk.breaking_f1", "F1 des breaking changes", 1, false, 3],
  ];

  async function pageBenchmarks() {
    const b = await loadBench();
    const golds = Object.keys(b.gold);
    let split = "test", gold = golds.includes("v4.1") ? "v4.1" : golds[0];
    header("Évaluation", "Benchmarks", "Mêmes signaux, mêmes annotations et même modèle pour toutes les versions.",
      `<div class="seg" id="b-split"><button data-v="dev">DEV · 48</button><button data-v="test" class="on">TEST · 24</button></div>
       ${golds.length > 1 ? `<div class="seg" id="b-gold">${golds.map((g) => `<button data-v="${g}" class="${g === gold ? "on" : ""}">Référence ${g}</button>`).join("")}</div>` : ""}`);
    app.innerHTML = `
      <div class="toolbar" style="justify-content:space-between;margin-bottom:14px">
        <div class="legend"><span><i style="background:var(--v0)"></i>v0 · original</span><span><i style="background:var(--v11)"></i>v1.1</span><span><i style="background:var(--v2)"></i>v2 · SignalGuard</span></div></div>
      <div id="b-notes"></div>
      <div class="grid g4" id="b-grid"></div>
      <div class="section"><div class="section-head"><div><h2>Robustesse aux injections de prompt</h2><p>Des consignes malveillantes sont ajoutées au texte de vrais signaux du DEV.</p></div></div>
        <div class="grid g3" id="b-inj"></div></div>`;
    const draw = () => {
      const summaries = (b.gold[gold] || {})[split] || [];
      const notes = [];
      if (summaries.some((s) => s.archived)) notes.push("v2 affiché en version 2.0, avant la calibration des releases.");
      if (summaries.some((s) => s.runs < 3)) notes.push("Les écarts inférieurs à 0,05 restent dans le bruit d'un LLM et ne sont pas significatifs.");
      $("#b-notes").innerHTML = notes.map((n) => `<p class="note">${icon("info", "sm")}<span>${esc(n)}</span></p>`).join("");
      $("#b-grid").innerHTML = METRICS.map(([key, label, max, lower, digits]) => {
        const rows = ["v0", "v1.1", "v2"].map((v) => {
          const s = summaries.find((x) => x.version === v), m = metric(s, key);
          return { label: s ? s.label : v, mean: m ? m.mean : null, std: m ? m.std : 0, n: m ? m.n : 0, color: VCOLOR[v] };
        });
        return `<div class="panel metric fade-in"><div class="panel-head"><h3>${label}</h3><span class="dir">${lower ? "plus bas = mieux" : "plus haut = mieux"}</span></div>
          <div class="panel-body" style="padding-top:6px">${barChart(rows, { max, digits, lowerIsBetter: lower })}</div></div>`;
      }).join("");
    };
    draw();
    $("#b-split").addEventListener("click", (e) => { const x = e.target.closest("button"); if (!x) return; split = x.dataset.v; [...$("#b-split").children].forEach((c) => c.classList.toggle("on", c === x)); draw(); });
    const bg = $("#b-gold");
    if (bg) bg.addEventListener("click", (e) => { const x = e.target.closest("button"); if (!x) return; gold = x.dataset.v; [...bg.children].forEach((c) => c.classList.toggle("on", c === x)); draw(); });

    const inj = b.injection;
    if (!inj) { $("#b-inj").innerHTML = `<div class="panel span-2">${emptyState("lock", "Pas encore de résultats", "Le benchmark d'injection n'a pas encore été exécuté.")}</div>`; return; }
    const rows = (key) => Object.keys(inj).map((v) => ({ label: v, mean: inj[v][key], std: 0, n: 1, color: VCOLOR[v] || "var(--v0)" }));
    const card = (title, sub, chart) => `<div class="panel metric"><div class="panel-head"><div><h3>${title}</h3><div class="sub">${sub}</div></div></div><div class="panel-body" style="padding-top:6px">${chart}</div></div>`;
    $("#b-inj").innerHTML =
      card("Risques masqués sous attaque", "Signaux à risque classés LOW après injection · plus bas = mieux", barChart(rows("risky_signals_predicted_low_under_attack"), { max: 1, digits: 2, lowerIsBetter: true })) +
      card("Gonflement de la pertinence", "Points ajoutés par l'attaque · plus bas = mieux", barChart(rows("mean_relevance_inflation"), { max: 20, digits: 1, lowerIsBetter: true })) +
      card("Injections détectées", "Détectées et neutralisées avant le LLM · plus haut = mieux", barChart(rows("injection_detection_rate"), { max: 1, digits: 2 }));
  }

  // ------------------------------------------------------------------ architecture
  function pageArchitecture() {
    header("Conception", "Architecture", "Workflow Agno : Step, Parallel, Condition et Router partagent un session_state.");
    const node = (ic, kind, title, text, llm = false) => `<div class="node ${llm ? "llm" : ""}"><div class="k">${icon(ic, "sm")}${kind}</div><h4>${title}</h4><p>${text}</p></div>`;
    const conn = `<div class="connector">${icon("down", "sm")}</div>`;
    app.innerHTML = `
      <div class="flow fade-in">
        <div class="flow-row grid g3">
          ${node("rss", "Step · Python", "load_signals", "Dataset figé ou 6 sources en direct. Une source en panne n'interrompt pas le pipeline.")}
          ${node("layers", "Step · Python", "normalize", "Schéma unifié et déduplication déterministe par clé source:id.")}
          ${node("filter", "Step · Python", "profile_and_triage", "Leurres, injections, marqueurs, type de release. Décide quels signaux nécessitent le LLM de risque.")}
        </div>${conn}
        <div class="group"><div class="label">Parallel · analysis</div><div class="grid g3">
          ${node("gauge", "Agent · LLM", "score_relevance", "Rubric ancré à 4 critères, sortie Pydantic, bornes appliquées aux releases, leurres plafonnés.", true)}
          ${node("shield", "Agent · LLM", "assess_risk_llm", "Artefacts et signaux marqués : avis du modèle puis arbitrage déterministe tracé, citations vérifiées.", true)}
          ${node("zap", "Step · Python", "assess_risk_fast_path", "Articles et posts sans marqueur : mêmes règles, sans appel LLM. 50 % d'appels en moins.")}
        </div></div>${conn}
        <div class="flow-row grid g2">
          ${node("layers", "Step · Python", "merge_assessments", "Assemble pertinence et risque, comptabilise les fallbacks.")}
          ${node("split", "Condition", "has_signals", "Sans signal : digest vide explicite. Sinon : routeur de synthèse.")}
        </div>${conn}
        <div class="group"><div class="label">Router · synthesis_router</div><div class="grid g2">
          ${node("doc", "Agent · LLM", "llm_synthesis", "Python calcule les faits, le modèle rédige. Identifiants inventés rejetés, nombres non calculés interdits.", true)}
          ${node("doc", "Step · Python", "deterministic_synthesis", "Digest entièrement calculé si la synthèse LLM est désactivée ou invalide. Fallback explicite.")}
        </div></div>
      </div>
      <div class="section"><div class="section-head"><div><h2>Couches de fiabilité</h2><p>Ce qui encadre chaque appel au modèle.</p></div></div>
        <div class="grid g4">
          ${node("check", "Contrat", "Sorties Pydantic", "output_schema Agno, bornes validées, total calculé en Python.")}
          ${node("activity", "Résilience", "Retries et quotas", "Backoff exponentiel, limiteur par modèle, reprise après quota épuisé.")}
          ${node("lock", "Sécurité", "Anti-injection", "Normalisation, détection et neutralisation avant le modèle, délimiteurs protégés.")}
          ${node("target", "Vérité", "Preuves ancrées", "Chaque citation du modèle est recherchée dans le texte réel, sinon rejetée.")}
        </div></div>`;
  }

  // ------------------------------------------------------------------ dataset explorer
  async function pageExplorer() {
    header("Évaluation", "Dataset", "72 signaux figés : annotation de référence (v4.1) face à la dernière prédiction de v2.");
    app.innerHTML = `<div class="panel" style="padding:20px"><div class="skeleton" style="height:16px;width:40%"></div><div class="skeleton" style="height:220px;margin-top:16px"></div></div>`;
    const rows = await loadSignals();
    let split = "all", source = "all", onlyDiff = false;
    const sources = [...new Set(rows.map((r) => r.source))];
    const agree = (r) => r.prediction && r.prediction.risk_level === r.gold.risk_level && r.prediction.risk_category === r.gold.risk_category;
    const disagreements = rows.filter((r) => r.prediction && !agree(r)).length;
    app.innerHTML = `
      <div class="panel"><div class="panel-head">
        <div><h3>Signaux</h3><div class="sub">${rows.length} signaux · ${disagreements} désaccord(s) sur le risque</div></div>
        <div class="toolbar">
          <div class="seg" id="e-split"><button data-v="all" class="on">Tous</button><button data-v="dev">DEV</button><button data-v="test">TEST</button></div>
          <select class="input compact" id="e-source"><option value="all">Toutes les sources</option>${sources.map((s) => `<option value="${s}">${esc(SOURCE[s] || s)}</option>`).join("")}</select>
          <label class="check"><input type="checkbox" id="e-diff" />Désaccords uniquement</label>
        </div></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Split</th><th>Source</th><th>Signal</th><th>Pertinence réf. / v2</th><th>Risque attendu</th><th>Risque v2</th><th>Accord</th></tr></thead>
          <tbody id="e-body"></tbody></table></div></div>`;
    const draw = () => {
      const view = rows.filter((r) => (split === "all" || r.split === split) && (source === "all" || r.source === source) && (!onlyDiff || (r.prediction && !agree(r))));
      $("#e-body").innerHTML = view.map((r) => `<tr class="clickable" data-i="${rows.indexOf(r)}">
        <td class="mono faint">${r.split.toUpperCase()}</td><td>${srcTag(r.source)}</td>
        <td class="title-cell"><div class="t">${esc(r.title)}</div></td>
        <td class="mono">${r.gold.relevance_score} <span class="faint">/</span> ${r.prediction ? r.prediction.relevance_score : "—"}</td>
        <td>${riskBadge(r.gold)} ${catTag(r.gold.risk_category)}</td>
        <td>${r.prediction ? `${riskBadge(r.prediction)} ${catTag(r.prediction.risk_category)}` : '<span class="faint">—</span>'}</td>
        <td>${r.prediction ? (agree(r) ? '<span class="badge plain ok">Accord</span>' : '<span class="badge plain ko">Écart</span>') : ""}</td></tr>`).join("")
        || `<tr><td colspan="7" class="muted">Aucun signal pour ces filtres.</td></tr>`;
    };
    draw();
    $("#e-split").addEventListener("click", (e) => { const x = e.target.closest("button"); if (!x) return; split = x.dataset.v; [...$("#e-split").children].forEach((c) => c.classList.toggle("on", c === x)); draw(); });
    $("#e-source").addEventListener("change", (e) => { source = e.target.value; draw(); });
    $("#e-diff").addEventListener("change", (e) => { onlyDiff = e.target.checked; draw(); });
    $("#e-body").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-i]"); if (!tr) return;
      const r = rows[+tr.dataset.i], p = r.prediction || {}, v2 = r.v2 || {};
      signalDrawer({
        signal_id: r.signal_id, source: r.source, title: r.title, url: r.url, description: r.description,
        relevance: { score: p.relevance_score, reasoning: p.relevance_reasoning, ...(p.relevance_rubric || {}), adjustments: v2.relevance_adjustments },
        risk: { risk_level: p.risk_level, risk_category: p.risk_category, breaking_changes: p.breaking_changes, concerns: p.concerns,
          evidence: p.evidence, evidence_strength: p.evidence_strength, adjustments: v2.risk_adjustments, llm_view: v2.llm_view, rejected_evidence: v2.rejected_evidence },
        profile: v2.profile,
      }, r.gold);
    });
  }

  // ------------------------------------------------------------------ news feed
  const HIGH_RELEVANCE = 70;
  const fmtDate = (v) => {
    if (!v) return "";
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? String(v).slice(0, 10) : d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
  };
  const riskReason = (it) => {
    const r = it.risk || {}, p = it.profile || {};
    if (p.injection_detected) return "Tentative d'injection de prompt détectée dans le contenu.";
    if (p.is_lure) return "Profil de dépôt-leurre (triche, crack ou logiciel usurpé).";
    if (r.breaking_changes) return "Changement incompatible : vérifier avant de mettre à jour.";
    return (r.concerns && r.concerns[0]) || (r.evidence && r.evidence[0]) || "";
  };

  async function pageNews() {
    header("Veille", "Actualités", "Signaux évalués, classés par pertinence. Les signaux à risque restent affichés et sont signalés.",
      `<span class="faint" style="font-size:12px" id="news-status"></span><button class="btn primary" id="news-refresh">${icon("refresh", "sm")}Actualiser depuis les sources</button>`);
    app.innerHTML = skeleton();
    const feed = await api("/api/feed");
    const items = feed.items;
    const c = feed.counts;
    const last = items.filter((i) => i.origin !== "dataset").map((i) => i.assessed_at).sort().pop();
    const watch = items.filter((i) => i.elevated_risk).sort((a, b) => b.risk_rank - a.risk_rank || (b.relevance.score || 0) - (a.relevance.score || 0));
    const stat = (ic, label, value, sub) => `<div class="panel kpi"><div class="label"><span class="ico">${icon(ic, "sm")}</span>${label}</div><div class="value" style="font-size:24px">${value}</div><div class="foot">${sub}</div></div>`;

    app.innerHTML = `
      <div class="grid g4">
        ${stat("news", "Signaux suivis", c.total, `${c.from_runs} issus de tes analyses · ${c.from_dataset} du dataset`)}
        ${stat("star", "Haute pertinence", items.filter((i) => (i.relevance.score || 0) >= HIGH_RELEVANCE).length, `score supérieur ou égal à ${HIGH_RELEVANCE}`)}
        ${stat("alert", "Risque à surveiller", c.elevated_risk, "MEDIUM et plus, ou breaking change")}
        ${stat("clock", "Dernière analyse", last ? fmtDate(last) : "—", last ? "depuis l'application" : "aucune analyse en direct pour l'instant")}
      </div>

      <div class="section panel">
        <div class="panel-head"><div><h3>À surveiller</h3><div class="sub">Signaux à risque, du plus grave au moins grave. Ils figurent aussi dans le fil ci-dessous à leur rang de pertinence.</div></div>
          <span class="badge plain ${watch.length ? "MEDIUM" : "ok"}">${watch.length} signal(s)</span></div>
        <div class="table-wrap"><table><thead><tr><th>Risque</th><th>Signal</th><th>Raison</th><th>Pertinence</th></tr></thead><tbody>
          ${watch.slice(0, 8).map((it) => `<tr class="clickable" data-id="${esc(it.signal_id)}">
            <td>${riskBadge(it.risk)} ${catTag(it.risk.risk_category)}</td>
            <td class="title-cell"><div class="t">${esc(it.title)}</div><div class="s">${esc(SOURCE[it.source] || it.source)}${it.published ? ` · ${fmtDate(it.published)}` : ""}</div></td>
            <td class="muted" style="max-width:380px;font-size:12.5px">${esc(riskReason(it))}</td>
            <td>${meter(it.relevance.score)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Aucun signal à risque.</td></tr>`}
        </tbody></table></div>
      </div>

      <div class="section panel">
        <div class="panel-head" style="flex-wrap:wrap">
          <div><h3>Fil d'actualité</h3><div class="sub" id="feed-count"></div></div>
          <div class="toolbar">
            <div style="position:relative"><span style="position:absolute;left:9px;top:8px;color:var(--faint)">${icon("search", "sm")}</span>
              <input class="input" id="n-q" placeholder="Rechercher un signal" style="padding-left:32px;width:220px" /></div>
            <select class="input compact" id="n-source"><option value="all">Toutes les sources</option>${[...new Set(items.map((i) => i.source))].map((s) => `<option value="${s}">${esc(SOURCE[s] || s)}</option>`).join("")}</select>
            <select class="input compact" id="n-min"><option value="0">Toute pertinence</option><option value="50">Pertinence 50 et plus</option><option value="70">Pertinence 70 et plus</option></select>
            <select class="input compact" id="n-origin"><option value="all">Toutes les origines</option><option value="recent">Mes analyses</option><option value="dataset">Dataset de référence</option></select>
            <label class="check"><input type="checkbox" id="n-risk" />Risque uniquement</label>
          </div></div>
        <div id="feed-list"></div>
      </div>`;

    const byId = Object.fromEntries(items.map((i) => [i.signal_id, i]));
    const draw = () => {
      const q = $("#n-q").value.trim().toLowerCase(), src = $("#n-source").value, min = +$("#n-min").value;
      const origin = $("#n-origin").value, riskOnly = $("#n-risk").checked;
      const view = items.filter((i) => (src === "all" || i.source === src) && (i.relevance.score || 0) >= min
        && (origin === "all" || (origin === "dataset" ? i.origin === "dataset" : i.origin !== "dataset"))
        && (!riskOnly || i.elevated_risk) && (!q || `${i.title} ${i.description}`.toLowerCase().includes(q)));
      $("#feed-count").textContent = `${view.length} signal(s) · classés par pertinence décroissante`;
      $("#feed-list").innerHTML = view.map((it, k) => `
        <article class="feed-item ${it.elevated_risk ? `risk-${esc(it.risk.risk_level || "MEDIUM")}` : ""}" data-id="${esc(it.signal_id)}">
          <div class="rank mono">${String(k + 1).padStart(2, "0")}</div>
          <div class="body">
            <div class="meta">${srcTag(it.source)}${it.published ? `<span class="faint">${fmtDate(it.published)}</span>` : ""}
              <span class="badge plain ${it.origin === "dataset" ? "neutral" : "info"}">${it.origin === "dataset" ? "Dataset" : it.origin === "live" ? "En direct" : "Analyse"}</span></div>
            <h4>${esc(it.title)}</h4>
            <p>${esc(it.relevance.reasoning || (it.description || "").slice(0, 220))}</p>
            ${it.elevated_risk ? `<div class="risk-line">${icon("alert", "sm")}<span>${esc(riskReason(it))}</span></div>` : ""}
          </div>
          <div class="side">
            <div class="score-big">${it.relevance.score ?? "—"}<span>/100</span></div>
            <div class="meter" style="width:100%"><span style="width:${Math.max(0, Math.min(100, it.relevance.score || 0))}%"></span></div>
            <div class="chips" style="margin-top:8px;justify-content:flex-end">${riskBadge(it.risk)}${it.risk.breaking_changes ? '<span class="badge plain info">Breaking</span>' : ""}</div>
            ${it.url ? `<a class="src-link" href="${esc(it.url)}" target="_blank" rel="noopener">${icon("external", "sm")}Source</a>` : ""}
          </div>
        </article>`).join("") || emptyState("search", "Aucun signal", "Aucun signal ne correspond à ces filtres.");
    };
    draw();
    ["n-q", "n-source", "n-min", "n-origin", "n-risk"].forEach((id) => $(`#${id}`).addEventListener(id === "n-q" ? "input" : "change", draw));
    app.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      const el = e.target.closest("[data-id]"); if (el && byId[el.dataset.id]) signalDrawer(byId[el.dataset.id]);
    });

    $("#news-refresh").addEventListener("click", async () => {
      const btn = $("#news-refresh"), status = $("#news-status");
      btn.disabled = true; status.textContent = "Collecte et analyse en cours…";
      try {
        const { job_id } = await api("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ version: "v2", mode: "live", limit: 3, llm_synthesis: false }) });
        clearInterval(state.poll);
        state.poll = setInterval(async () => {
          let job; try { job = await api(`/api/runs/${job_id}`); } catch { return; }
          const stage = job.stage && job.stage.current ? STEPS[job.stage.current] || job.stage.current : "";
          status.textContent = `${stage ? stage + " · " : ""}${job.elapsed_s}s`;
          if (job.status === "done" || job.status === "error") {
            clearInterval(state.poll);
            if (job.status === "error") { status.textContent = ""; btn.disabled = false;
              app.insertAdjacentHTML("afterbegin", `<div class="callout error" style="margin-bottom:16px">${icon("alert", "sm")}<span>${esc(job.error)}</span></div>`); return; }
            pageNews();
          }
        }, 1500);
      } catch (err) {
        status.textContent = ""; btn.disabled = false;
        app.insertAdjacentHTML("afterbegin", `<div class="callout error" style="margin-bottom:16px">${icon("alert", "sm")}<span>${esc(err.message)}</span></div>`);
      }
    });
  }

  // ------------------------------------------------------------------ router
  const ROUTES = { "": pageHome, news: pageNews, run: pageRun, benchmarks: pageBenchmarks, architecture: pageArchitecture, explorer: pageExplorer };
  async function route() {
    const key = location.hash.replace(/^#\/?/, "").split("?")[0] || "";
    const page = ROUTES[key] ? key : "";
    document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
    closeDrawer();
    if (page !== "run") clearInterval(state.poll);
    try { await ROUTES[page](); window.scrollTo(0, 0); }
    catch (err) { app.innerHTML = `<div class="callout error">${icon("alert", "sm")}<span>Erreur : ${esc(err.message)}</span></div>`; }
  }
  window.addEventListener("hashchange", route);
  loadOverview().catch(() => {});
  route();
})();
