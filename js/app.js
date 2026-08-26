/* ============================================================
   RN EM MOVIMENTO 2.0 — lógica do ranking
   Lê data/weeks.json (snapshots semanais capturados do Strava)
   e monta pódios + tabela, com filtro por semana e acumulado.
   ============================================================ */

const DATA_URL = "data/weeks.json";

const state = {
  weeks: [],        // [{id, label, start, end, athletes: [{name, distance, activities, elevation, time}]}]
  selected: "all",  // "all" | week id
  sortKey: "distance",
  sortDir: "desc",
  search: "",
};

const fmt = {
  km(m)  { return (m / 1000).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }); },
  int(n) { return n.toLocaleString("pt-BR"); },
  elev(m){ return Math.round(m).toLocaleString("pt-BR"); },
  time(s){
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
  },
  dateRange(start, end) {
    const f = (d) => new Date(d + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
    return `${f(start)} – ${f(end)}`;
  },
};

/* ---------- agregação ---------- */
function aggregate(weeks) {
  const map = new Map();
  for (const week of weeks) {
    for (const a of week.athletes) {
      const key = a.name.trim().toLowerCase();
      if (!map.has(key)) {
        map.set(key, { name: a.name.trim(), distance: 0, activities: 0, elevation: 0, time: 0 });
      }
      const t = map.get(key);
      t.distance   += a.distance   || 0;
      t.activities += a.activities || 0;
      t.elevation  += a.elevation  || 0;
      t.time       += a.time       || 0;
    }
  }
  return [...map.values()];
}

function currentAthletes() {
  if (state.selected === "all") return aggregate(state.weeks);
  const week = state.weeks.find((w) => w.id === state.selected);
  return week ? aggregate([week]) : [];
}

/* ---------- hero stats ---------- */
function renderHeroStats() {
  const all = aggregate(state.weeks);
  const km = all.reduce((s, a) => s + a.distance, 0) / 1000;
  const acts = all.reduce((s, a) => s + a.activities, 0);
  const elev = all.reduce((s, a) => s + a.elevation, 0);
  document.getElementById("stat-athletes").textContent = fmt.int(all.length);
  document.getElementById("stat-km").textContent = km.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  document.getElementById("stat-activities").textContent = fmt.int(acts);
  document.getElementById("stat-elev").textContent = fmt.elev(elev);
}

/* ---------- filtro de semanas ---------- */
function renderWeekFilter() {
  const nav = document.getElementById("week-filter");
  nav.innerHTML = "";

  const mkBtn = (id, title, range) => {
    const b = document.createElement("button");
    b.className = "week-btn" + (state.selected === id ? " active" : "");
    b.innerHTML = `${title}<span class="week-btn-range">${range}</span>`;
    b.addEventListener("click", () => { state.selected = id; render(); });
    return b;
  };

  nav.appendChild(mkBtn("all", "Acumulado", "todas as semanas"));
  state.weeks.forEach((w, i) => {
    nav.appendChild(mkBtn(w.id, w.label || `Semana ${i + 1}`, fmt.dateRange(w.start, w.end)));
  });
}

/* ---------- pódios ---------- */
const METRICS = {
  distance:   { value: (a) => a.distance,   display: (a) => `${fmt.km(a.distance)} km` },
  activities: { value: (a) => a.activities, display: (a) => `${fmt.int(a.activities)} atividades` },
  elevation:  { value: (a) => a.elevation,  display: (a) => `${fmt.elev(a.elevation)} m` },
};

function renderPodiums(athletes) {
  document.querySelectorAll(".podium-stage").forEach((stage) => {
    const metric = METRICS[stage.dataset.metric];
    const top3 = [...athletes]
      .filter((a) => metric.value(a) > 0)
      .sort((x, y) => metric.value(y) - metric.value(x))
      .slice(0, 3);

    stage.innerHTML = "";
    if (top3.length === 0) {
      stage.innerHTML = `<p class="podium-empty">Sem dados nesta semana ainda.</p>`;
      return;
    }

    const medals = ["🥇", "🥈", "🥉"];
    const cls = ["first", "second", "third"];
    top3.forEach((a, i) => {
      const slot = document.createElement("div");
      slot.className = `podium-slot ${cls[i]}`;
      slot.innerHTML = `
        <div class="medal">${medals[i]}</div>
        <div class="p-name">${escapeHtml(a.name)}</div>
        <div class="p-value">${metric.display(a)}</div>
        <div class="pillar">${i + 1}</div>`;
      stage.appendChild(slot);
    });
  });
}

/* ---------- tabela ---------- */
function renderTable(athletes) {
  const tbody = document.querySelector("#ranking-table tbody");
  const note = document.getElementById("ranking-note");

  const key = state.sortKey, dir = state.sortDir === "desc" ? -1 : 1;
  const rows = [...athletes]
    .filter((a) => a.name.toLowerCase().includes(state.search))
    .sort((x, y) => ((x[key] || 0) - (y[key] || 0)) * dir);

  document.querySelectorAll("thead th.sortable").forEach((th) => {
    th.classList.toggle("sorted-desc", th.dataset.sort === key && state.sortDir === "desc");
    th.classList.toggle("sorted-asc",  th.dataset.sort === key && state.sortDir === "asc");
  });

  tbody.innerHTML = "";
  if (rows.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="6">Nenhum atleta encontrado.</td></tr>`;
    note.textContent = "";
    return;
  }

  rows.forEach((a, i) => {
    const tr = document.createElement("tr");
    if (state.sortDir === "desc" && i < 3) tr.classList.add(`top-${i + 1}`);
    tr.innerHTML = `
      <td class="col-rank">${i + 1}</td>
      <td class="col-name">${escapeHtml(a.name)}</td>
      <td class="col-num">${fmt.km(a.distance)}<span class="unit">km</span></td>
      <td class="col-num">${fmt.int(a.activities)}</td>
      <td class="col-num">${fmt.elev(a.elevation)}<span class="unit">m</span></td>
      <td class="col-num">${fmt.time(a.time)}</td>`;
    tbody.appendChild(tr);
  });

  const label = state.selected === "all"
    ? "acumulado de todas as semanas"
    : "somente a semana selecionada";
  note.textContent = `${rows.length} atleta(s) · ${label}`;
}

/* ---------- util ---------- */
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- render geral ---------- */
function render() {
  const athletes = currentAthletes();
  renderWeekFilter();
  renderPodiums(athletes);
  renderTable(athletes);
}

/* ---------- eventos ---------- */
document.querySelectorAll("thead th.sortable").forEach((th) => {
  th.addEventListener("click", () => {
    const k = th.dataset.sort;
    if (state.sortKey === k) {
      state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
    } else {
      state.sortKey = k;
      state.sortDir = "desc";
    }
    renderTable(currentAthletes());
  });
});

document.getElementById("search-athlete").addEventListener("input", (e) => {
  state.search = e.target.value.trim().toLowerCase();
  renderTable(currentAthletes());
});

/* ---------- boot ---------- */
(async function init() {
  try {
    const res = await fetch(`${DATA_URL}?t=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.weeks = (data.weeks || []).sort((a, b) => a.start.localeCompare(b.start));

    if (data.updated_at) {
      const d = new Date(data.updated_at);
      const dateStr = d.toLocaleDateString("pt-BR");
      const timeStr = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      document.getElementById("hero-updated").textContent =
        `Atualizado em ${dateStr} às ${timeStr}`;
      document.getElementById("footer-updated").textContent =
        `Dados atualizados em ${dateStr} às ${timeStr} · atualização automática a cada hora`;
    }

    renderHeroStats();
    render();
  } catch (err) {
    document.querySelector("main").insertAdjacentHTML(
      "afterbegin",
      `<p style="margin-top:40px;padding:20px;background:#fff;border-radius:12px;color:#a00;">
         Não foi possível carregar <code>data/weeks.json</code> (${escapeHtml(String(err.message))}).
         Rode o script de atualização e recarregue a página.
       </p>`
    );
  }
})();
