const api = (path) => fetch(`/api${path}`).then(r => r.json());

async function initList() {
  fetch("/api/me")
    .then(r => {
      if (r.status === 401) {
        window.location.href = "/login.html";
        return null;
      }
      return r.json();
    })
    .then(me => {
      if (!me) return;
      const el = document.getElementById("me");
      if (el && me.user) el.textContent = `${me.user} (${me.role_label || me.role})`;
    })
    .catch(() => {});

  const logoutBtn = document.getElementById("logout");
  if (logoutBtn) logoutBtn.addEventListener("click", async () => {
    await fetch("/api/logout", {method: "POST"});
    window.location.href = "/login.html";
  });

  const tbody = document.querySelector("#traces tbody");
  if (!tbody) return;

  const btn = document.getElementById("btn-apply");
  if (btn) btn.addEventListener("click", load);

  async function load() {
    // собираем фильтры в query-string — фильтрация server-side по трейсам
    const params = new URLSearchParams();
    const fService = document.getElementById("f-service")?.value || "";
    const fStatus  = document.getElementById("f-status")?.value  || "";
    const fMinDur  = document.getElementById("f-min-dur")?.value || "";

    if (fService) params.set("service", fService);
    if (fStatus)  params.set("status",  fStatus);
    if (fMinDur)  params.set("min_duration_ms", fMinDur);
    params.set("limit", "1000");

    const data = await api(`/spans?${params.toString()}`);
    const spans = data.spans || [];

    const byTrace = new Map();
    for (const s of spans) {
      if (!byTrace.has(s.trace_id)) byTrace.set(s.trace_id, []);
      byTrace.get(s.trace_id).push(s);
    }

    const rows = [];
    for (const [traceId, group] of byTrace) {
      const root = group.find(s => !s.parent_span_id) || group[0];
      const durationMs = (root.end_time_unix_nano - root.start_time_unix_nano) / 1e6;
      const hasError = group.some(s => s.status === "ERROR");
      rows.push({ traceId, root, durationMs, hasError });
    }

    rows.sort((a, b) => b.durationMs - a.durationMs);

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

    const oldNote = document.getElementById("truncated-note");
    if (oldNote) oldNote.remove();
    if (data.truncated) {
      const note = document.createElement("p");
      note.id = "truncated-note";
      note.textContent =
        `Показаны первые ${rows.length} из ${data.total} трейсов. Уточните фильтры, чтобы увидеть больше.`;
      note.style.cssText = "color:#e67e22; font-size:13px; margin:8px 0;";
      tbody.parentNode.insertBefore(note, tbody.nextSibling);
    }

    renderServiceMatrix(spans);
  }

  await load();
}

function renderServiceMatrix(spans) {
  const container = document.getElementById("service-matrix");
  if (!container) return;

  // 1) собираем все сервисы
  const services = Array.from(new Set(spans.map(s => s.service_name))).sort();
  if (services.length === 0) {
    container.innerHTML = '<div class="matrix-hint">Нет данных</div>';
    return;
  }

  const byId = new Map(spans.map(s => [s.span_id, s]));

  const counts = new Map();
  for (const s of spans) {
    if (!s.parent_span_id) continue;
    const parent = byId.get(s.parent_span_id);
    if (!parent) continue;
    if (parent.service_name === s.service_name) continue;
    const key = `${parent.service_name}|${s.service_name}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }

  const max = Math.max(1, ...counts.values());

  const n = services.length;
  const cellSize = 80;
  container.style.gridTemplateColumns = `120px repeat(${n}, ${cellSize}px)`;

  const parts = [];

  parts.push('<div class="cell corner"></div>');
  for (const svc of services) {
    parts.push(`<div class="cell header">${svc}</div>`);
  }

  for (const from of services) {
    parts.push(`<div class="cell header">${from}</div>`);
    for (const to of services) {
      if (from === to) {
        parts.push('<div class="cell self">—</div>');
        continue;
      }
      const raw = counts.get(`${from}|${to}`) || 0;
      const value = raw === 0 ? 0 : raw / max;
      const alpha = value === 0 ? 0 : 0.15 + 0.75 * value;
      const bg = value === 0
        ? ""
        : `style="background: rgba(37,99,235,${alpha.toFixed(3)}); color:${value > 0.6 ? "#fff" : "#1a1a1a"}"`;
      parts.push(
        `<div class="cell value-${value === 0 ? "0" : "n"}" ${bg} title="${from} → ${to}: ${raw}">` +
        `${value.toFixed(2)}</div>`
      );
    }
  }

  container.innerHTML = parts.join("");
}

async function initTrace() {
  const svg = document.getElementById("waterfall");
  if (!svg) return;

  const traceId = new URLSearchParams(location.search).get("trace_id");
  if (!traceId) {
    svg.innerHTML = `<text x="10" y="20">Не указан trace_id</text>`;
    return;
  }
  document.getElementById("title").textContent = `Трейс ${traceId}`;

  const data = await api(`/spans?trace_id=${traceId}`);
  const spans = data.spans || [];
  if (!spans.length) {
    svg.innerHTML = `<text x="10" y="20">Спаны не найдены</text>`;
    return;
  }

  const byId = new Map(spans.map(s => [s.span_id, s]));
  const children = new Map();
  for (const s of spans) {
    const p = s.parent_span_id || "__root__";
    if (!children.has(p)) children.set(p, []);
    children.get(p).push(s);
  }
  for (const arr of children.values()) {
    arr.sort((a, b) => a.start_time_unix_nano - b.start_time_unix_nano);
  }

  const ordered = [];
  const depth = new Map();
  function walk(id, d) {
    ordered.push(id);
    depth.set(id, d);
    for (const c of children.get(id) || []) walk(c.span_id, d + 1);
  }
  for (const r of children.get("__root__") || []) walk(r.span_id, 0);

  const t0 = Math.min(...spans.map(s => s.start_time_unix_nano));
  const t1 = Math.max(...spans.map(s => s.end_time_unix_nano));
  const total = t1 - t0 || 1;

  const PAD = 10, ROW = 24, LABEL_W = 220;
  const width = svg.clientWidth || 900;
  const chartW = width - LABEL_W - PAD;
  svg.setAttribute("height", ordered.length * ROW + PAD * 2);

  const SLOW_MS = 50;
  const selected = { id: null };

  function render() {
    svg.innerHTML = ordered.map((id, i) => {
      const s = byId.get(id);
      const d = depth.get(id) || 0;
      const start = ((s.start_time_unix_nano - t0) / total) * chartW;
      const w = Math.max(2, ((s.end_time_unix_nano - s.start_time_unix_nano) / total) * chartW);
      const y = PAD + i * ROW;
      const durMs = (s.end_time_unix_nano - s.start_time_unix_nano) / 1e6;

      let cls = "span-bar";
      if (s.status === "ERROR") cls += " error";
      else if (durMs > SLOW_MS) cls += " slow";
      if (selected.id === id) cls += " selected";

      const indent = d * 12;
      return `
        <text class="span-label" x="${PAD + indent}" y="${y + 16}">${s.service_name}: ${s.name}</text>
        <rect class="${cls}" data-span="${s.span_id}"
              x="${LABEL_W + start}" y="${y + 4}" width="${w}" height="${ROW - 8}" rx="2"></rect>
      `;
    }).join("");
  }

  render();

  svg.addEventListener("click", (e) => {
    const rect = e.target.closest("rect.span-bar");
    if (!rect) return;
    selected.id = rect.dataset.span;
    const span = byId.get(selected.id);
    document.getElementById("attrs-content").textContent = JSON.stringify(span, null, 2);
    render();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initList();
  initTrace();
});