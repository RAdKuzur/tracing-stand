const api = (path) => fetch(`/api${path}`).then(r => r.json());

// ---------- страница списка трейсов ----------
async function initList() {
  const tbody = document.querySelector("#traces tbody");
  if (!tbody) return;

  const btn = document.getElementById("btn-apply");
  btn.addEventListener("click", load);

  async function load() {
    const data = await api("/spans");
    const spans = data.spans || [];

    // группируем по trace_id
    const byTrace = new Map();
    for (const s of spans) {
      if (!byTrace.has(s.trace_id)) byTrace.set(s.trace_id, []);
      byTrace.get(s.trace_id).push(s);
    }

    const fService = document.getElementById("f-service").value;
    const fStatus  = document.getElementById("f-status").value;
    const fMinDur  = Number(document.getElementById("f-min-dur").value || 0);

    const rows = [];
    for (const [traceId, group] of byTrace) {
      const root = group.find(s => !s.parent_span_id) || group[0];
      const durationMs = (root.end_time_unix_nano - root.start_time_unix_nano) / 1e6;
      const hasError = group.some(s => s.status === "ERROR");

      if (fService && !group.some(s => s.service_name === fService)) continue;
      if (fStatus === "error" && !hasError) continue;
      if (fStatus === "ok" && hasError) continue;
      if (durationMs < fMinDur) continue;

      rows.push({ traceId, root, durationMs, hasError });
    }

    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><a href="/trace.html?trace_id=${r.traceId}">${r.traceId.slice(0, 8)}…</a></td>
        <td>${r.root.service_name}</td>
        <td>${r.root.name}</td>
        <td>${r.durationMs.toFixed(1)}</td>
        <td class="${r.hasError ? "status-error" : "status-ok"}">
          ${r.hasError ? "ERROR" : "OK"}
        </td>
        <td><a href="/trace.html?trace_id=${r.traceId}">открыть</a></td>
      </tr>
    `).join("") || `<tr><td colspan="6">Нет трейсов</td></tr>`;
  }

  await load();
}

// ---------- страница трейса (waterfall) ----------
async function initTrace() {
  const svg = document.getElementById("waterfall");
  if (!svg) return;

  const traceId = new URLSearchParams(location.search).get("trace_id");
  document.getElementById("title").textContent = `Трейс ${traceId}`;

  const data = await api(`/spans?trace_id=${traceId}`);
  const spans = data.spans || [];
  if (!spans.length) {
    svg.innerHTML = `<text x="10" y="20">Спаны не найдены</text>`;
    return;
  }

  // строим дерево по parent_span_id
  const byId = new Map(spans.map(s => [s.span_id, s]));
  const children = new Map();
  for (const s of spans) {
    const p = s.parent_span_id || "__root__";
    if (!children.has(p)) children.set(p, []);
    children.get(p).push(s);
  }

  // раскладываем в порядке обхода в глубину
  const ordered = [];
  function walk(id) {
    ordered.push(id);
    for (const c of children.get(id) || []) walk(c.span_id);
  }
  for (const r of children.get("__root__") || []) walk(r.span_id);

  // временные границы трейса
  const t0 = Math.min(...spans.map(s => s.start_time_unix_nano));
  const t1 = Math.max(...spans.map(s => s.end_time_unix_nano));
  const total = t1 - t0 || 1;

  const PAD = 10, ROW = 24, LABEL_W = 180;
  const width = svg.clientWidth || 800;
  const chartW = width - LABEL_W - PAD;
  svg.setAttribute("height", ordered.length * ROW + PAD * 2);

  // порог "медленного" спана — 50 мс
  const SLOW_MS = 50;

  svg.innerHTML = ordered.map((id, i) => {
    const s = byId.get(id);
    const start = ((s.start_time_unix_nano - t0) / total) * chartW;
    const w = Math.max(2, ((s.end_time_unix_nano - s.start_time_unix_nano) / total) * chartW);
    const y = PAD + i * ROW;
    const durMs = (s.end_time_unix_nano - s.start_time_unix_nano) / 1e6;
    const cls = s.status === "ERROR" ? "error" : (durMs > SLOW_MS ? "slow" : "");
    return `
      <text class="span-label" x="${PAD}" y="${y + 16}">${s.service_name}: ${s.name}</text>
      <rect class="span-bar ${cls}" data-span="${s.span_id}"
            x="${LABEL_W + start}" y="${y + 4}" width="${w}" height="${ROW - 8}" rx="2"></rect>
    `;
  }).join("");

  svg.addEventListener("click", (e) => {
    const rect = e.target.closest("rect.span-bar");
    if (!rect) return;
    const span = byId.get(rect.dataset.span);
    document.getElementById("attrs-content").textContent =
      JSON.stringify(span, null, 2);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initList();
  initTrace();
});