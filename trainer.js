let tg;
if (window.Telegram && window.Telegram.WebApp) {
  tg = window.Telegram.WebApp;
  tg.ready();
  tg.expand();
} else {
  document.body.innerHTML = `<div style="padding:24px;font-family:sans-serif;">
    Не удалось загрузить Telegram WebApp SDK. Откройте это приложение только
    через кнопку в боте Telegram, не по прямой ссылке в браузере.
  </div>`;
  throw new Error("Telegram WebApp SDK not available");
}

const INIT_DATA = tg.initData || "";
const DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

let clients = [];
let exercises = [];
let planDraft = {}; // {day_of_week: [{exercise_id, title, sets_reps, notes}]}
let currentDay = 0;
let selectedExerciseId = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": INIT_DATA,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    const err = new Error(`${res.status}: ${text || res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function showTab(id, btn) {
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
}

function mondayISO(d = new Date()) {
  const day = (d.getDay() + 6) % 7;
  const monday = new Date(d);
  monday.setDate(d.getDate() - day);
  return monday.toISOString().slice(0, 10);
}

// ---------- клиенты ----------

async function loadClients() {
  const list = document.getElementById("clientsList");
  try {
    clients = await api("/api/trainer/clients");
  } catch (e) {
    list.innerHTML = `<div class="empty">Не удалось загрузить клиентов (${esc(e.message)}).<br>Если это 401 — не открыт как WebApp кнопка бота. Если 403 — TRAINER_TG_ID не совпадает.</div>`;
    return;
  }
  list.outerHTML = clients.length
    ? clients.map(c => `
        <div class="client-row" onclick="openClientDetail(${c.tg_id})" style="cursor:pointer;">
          <div>
            <div class="name">${esc(c.name)}</div>
            <div class="goal">${esc(c.goal || "")}</div>
          </div>
          <span class="badge">${c.is_existing_client ? "действующий" : "новый"}</span>
        </div>
      `).join("")
    : `<div class="empty">Пока нет клиентов</div>`;

  const select = document.getElementById("clientSelect");
  select.innerHTML = clients.map(c => `<option value="${c.tg_id}">${esc(c.name)}</option>`).join("");
  if (clients.length) {
    select.onchange = () => loadBuilderData();
    document.getElementById("weekStart").value = mondayISO();
    document.getElementById("weekStart").onchange = () => loadBuilderData();
    loadBuilderData();
  }
}

async function openClientDetail(tgId) {
  const c = clients.find(x => x.tg_id === tgId);
  document.getElementById("detailName").textContent = c ? c.name : "";
  const { weight, nutrition } = await api(`/api/trainer/client-reports?client_tg_id=${tgId}`);
  document.getElementById("detailWeight").innerHTML = weight.length
    ? weight.map(r => `<div class="history-row"><span class="date">${r.report_date}</span><span>${r.weight} кг${r.note ? " · " + esc(r.note) : ""}</span></div>`).join("")
    : `<div class="empty">Нет отчётов</div>`;
  document.getElementById("detailNutrition").innerHTML = nutrition.length
    ? nutrition.map(r => `<div class="history-row"><span class="date">${r.report_date}</span><span>${esc(r.description)}</span></div>`).join("")
    : `<div class="empty">Нет отчётов</div>`;
  showTab("tab-client-detail", null);
}

// ---------- билдер программы ----------

function renderDayPicker() {
  document.getElementById("dayPicker").innerHTML = DAY_NAMES.map((d, i) =>
    `<button class="${i === currentDay ? "active" : ""}" onclick="selectDay(${i})">${d}</button>`
  ).join("");
}

function selectDay(i) {
  currentDay = i;
  renderDayPicker();
  renderSelectedDayItems();
}

function renderSelectedDayItems() {
  const items = planDraft[currentDay] || [];
  document.getElementById("selectedDayItems").innerHTML = items.length
    ? items.map((it, idx) => `
        <div class="exercise-item">
          <div>
            <div class="name">${esc(it.title)}</div>
            <div class="meta">
              <input style="width:70px;border:1px solid var(--line);border-radius:6px;padding:3px 6px;font-size:12px;"
                     value="${esc(it.sets_reps || "")}" placeholder="3x12"
                     onchange="updateSetsReps(${idx}, this.value)">
            </div>
          </div>
          <span style="color:var(--danger);font-weight:700;cursor:pointer;" onclick="removeItem(${idx})">убрать</span>
        </div>
      `).join("")
    : `<div class="empty">На этот день пока ничего не добавлено</div>`;
}

function updateSetsReps(idx, value) {
  planDraft[currentDay][idx].sets_reps = value;
}

function removeItem(idx) {
  planDraft[currentDay].splice(idx, 1);
  renderSelectedDayItems();
}

async function loadBuilderData() {
  const clientTgId = document.getElementById("clientSelect").value;
  const weekStart = document.getElementById("weekStart").value || mondayISO();
  if (!clientTgId) return;

  exercises = await api(`/api/trainer/recommend?client_tg_id=${clientTgId}`);
  renderExerciseChips();

  const plan = await api(`/api/trainer/plan?client_tg_id=${clientTgId}&week_start=${weekStart}`);
  planDraft = {};
  (plan.items || []).forEach(it => {
    (planDraft[it.day_of_week] ??= []).push({
      exercise_id: it.exercise_id, title: it.title, sets_reps: it.sets_reps, notes: it.notes,
    });
  });
  currentDay = 0;
  renderDayPicker();
  renderSelectedDayItems();
}

function renderExerciseChips() {
  const el = document.getElementById("exerciseChips");
  if (!exercises.length) {
    el.innerHTML = `<div class="empty">Библиотека пуста — отправьте видео боту</div>`;
    return;
  }
  el.innerHTML = exercises.map((e, i) => `
    <div class="chip ${selectedExerciseId === e.id ? "selected" : ""}" onclick="selectExercise(${e.id})">
      ${i < 3 ? '<span class="rec-flag">★ </span>' : ""}${esc(e.title)}
    </div>
  `).join("");
}

function selectExercise(id) {
  selectedExerciseId = id;
  renderExerciseChips();
}

function addSelectedExercise() {
  if (!selectedExerciseId) return;
  const ex = exercises.find(e => e.id === selectedExerciseId);
  (planDraft[currentDay] ??= []).push({ exercise_id: ex.id, title: ex.title, sets_reps: "", notes: "" });
  renderSelectedDayItems();
}

async function savePlan() {
  const clientTgId = parseInt(document.getElementById("clientSelect").value, 10);
  const weekStart = document.getElementById("weekStart").value || mondayISO();
  const items = [];
  Object.keys(planDraft).forEach(day => {
    planDraft[day].forEach(it => {
      items.push({ day_of_week: parseInt(day, 10), exercise_id: it.exercise_id, sets_reps: it.sets_reps, notes: it.notes });
    });
  });
  await api("/api/trainer/plan", {
    method: "POST",
    body: JSON.stringify({ client_tg_id: clientTgId, week_start: weekStart, items }),
  });
  tg.HapticFeedback?.notificationOccurred("success");
  tg.showAlert ? tg.showAlert("Программа сохранена, клиент получит уведомление") : alert("Сохранено");
}

// ---------- библиотека видео ----------

async function loadLibrary() {
  const el = document.getElementById("libraryList");
  let list;
  try {
    list = await api("/api/trainer/exercises");
  } catch (e) {
    el.innerHTML = `<div class="empty">Не удалось загрузить библиотеку (${esc(e.message)})</div>`;
    return;
  }
  el.innerHTML = list.length
    ? list.map(e => `
        <div class="exercise-item card">
          <div>
            <div class="name">${esc(e.title)}</div>
            <div class="meta">${esc(e.tags || "")}</div>
          </div>
          <a class="play" target="_blank" href="/api/video/${e.id}">▶ смотреть</a>
        </div>
      `).join("")
    : `<div class="empty">Пока нет видео — отправьте их боту в чат</div>`;
}

loadClients();
loadLibrary();
