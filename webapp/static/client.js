const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const INIT_DATA = tg.initData || "";
const DAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": INIT_DATA,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function showTab(id, btn) {
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

async function loadMe() {
  try {
    const me = await api("/api/client/me");
    document.getElementById("userName").textContent = me.name || "Без имени";
    document.getElementById("greeting").textContent = me.goal ? `Цель: ${me.goal}` : "Личный кабинет";
  } catch (e) {
    document.getElementById("userName").textContent = "Отправьте /start боту";
  }
}

async function loadPlan() {
  const el = document.getElementById("planContent");
  try {
    const plan = await api("/api/client/plan");
    if (!plan.items || plan.items.length === 0) {
      el.innerHTML = `<div class="empty">Тренер ещё не собрал программу на эту неделю</div>`;
      return;
    }
    const byDay = {};
    plan.items.forEach(it => {
      (byDay[it.day_of_week] ??= []).push(it);
    });
    let html = "";
    Object.keys(byDay).sort((a, b) => a - b).forEach(d => {
      html += `<div class="day-block"><div class="day-label">${DAY_NAMES[d]}</div>`;
      byDay[d].forEach(it => {
        html += `<div class="exercise-item">
          <div>
            <div class="name">${esc(it.title)}</div>
            <div class="meta">${esc(it.sets_reps || "")} ${it.notes ? "· " + esc(it.notes) : ""}</div>
          </div>
          <a class="play" target="_blank" href="/api/video/${it.exercise_id}">▶ смотреть</a>
        </div>`;
      });
      html += `</div>`;
    });
    el.outerHTML = html;
  } catch (e) {
    el.innerHTML = `<div class="empty">Не удалось загрузить программу</div>`;
  }
}

async function loadTips() {
  try {
    const tips = await api("/api/client/nutrition-tips");
    document.getElementById("tipsContent").innerHTML = tips.map(t =>
      `<div class="tip-row"><h3>${esc(t.title)}</h3><p>${esc(t.content)}</p></div>`
    ).join("") || `<div class="empty">Пока нет советов</div>`;
  } catch (e) {}
}

async function loadWarmups() {
  try {
    const items = await api("/api/client/warmups");
    document.getElementById("warmupContent").innerHTML = items.map(t =>
      `<div class="tip-row"><h3>${esc(t.title)}</h3><p>${esc(t.content)}</p></div>`
    ).join("") || `<div class="empty">Пока нет рекомендаций</div>`;
  } catch (e) {}
}

async function submitWeight() {
  const weight = document.getElementById("weightInput").value;
  const note = document.getElementById("weightNote").value;
  if (!weight) return;
  await api("/api/client/weight-report", { method: "POST", body: JSON.stringify({ weight, note }) });
  document.getElementById("weightInput").value = "";
  document.getElementById("weightNote").value = "";
  loadWeightHistory();
  tg.HapticFeedback?.notificationOccurred("success");
}

async function loadWeightHistory() {
  const rows = await api("/api/client/weight-reports");
  document.getElementById("weightHistory").innerHTML = rows.length
    ? `<div class="card">${rows.map(r => `<div class="history-row"><span class="date">${r.report_date}</span><span>${r.weight} кг${r.note ? " · " + esc(r.note) : ""}</span></div>`).join("")}</div>`
    : "";
}

async function submitNutrition() {
  const description = document.getElementById("nutritionInput").value;
  if (!description) return;
  await api("/api/client/nutrition-report", { method: "POST", body: JSON.stringify({ description }) });
  document.getElementById("nutritionInput").value = "";
  loadNutritionHistory();
  tg.HapticFeedback?.notificationOccurred("success");
}

async function loadNutritionHistory() {
  const rows = await api("/api/client/nutrition-reports");
  document.getElementById("nutritionHistory").innerHTML = rows.length
    ? `<div class="card">${rows.map(r => `<div class="history-row"><span class="date">${r.report_date}</span><span>${esc(r.description)}</span></div>`).join("")}</div>`
    : "";
}

async function setupChatLink() {
  try {
    const { username } = await api("/api/client/trainer-link");
    document.getElementById("openChatBtn").onclick = () => {
      if (username) tg.openTelegramLink(`https://t.me/${username}`);
    };
  } catch (e) {}
}

loadMe();
loadPlan();
loadTips();
loadWarmups();
loadWeightHistory();
loadNutritionHistory();
setupChatLink();
