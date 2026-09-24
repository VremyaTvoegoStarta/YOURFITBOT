import json
import os
import time
from datetime import date, timedelta

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
from webapp.auth import parse_and_validate

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TRAINER_TG_ID = int(os.getenv("TRAINER_TG_ID", "0"))
TRAINER_USERNAME = os.getenv("TRAINER_USERNAME", "")

# Меняется при каждом запуске сервера (=при каждом деплое), чтобы Telegram
# не показывал закэшированную старую версию JS/CSS мини-приложения.
BUILD_VERSION = str(int(time.time()))

app = FastAPI()
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

HERE = os.path.dirname(__file__)


def read_template(name: str) -> str:
    with open(os.path.join(HERE, "templates", name), encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{VERSION}}", BUILD_VERSION)


def current_tg_id(request: Request) -> int:
    """
    Достаём и проверяем Telegram-пользователя из заголовка X-Init-Data,
    который присылает JS мини-приложения (см. static/*.js).
    """
    init_data = request.headers.get("X-Init-Data", "")
    data = parse_and_validate(init_data, BOT_TOKEN)
    if not data:
        raise HTTPException(status_code=401, detail="Не удалось подтвердить пользователя Telegram")
    user = json.loads(data.get("user", "{}"))
    tg_id = user.get("id")
    if not tg_id:
        raise HTTPException(status_code=401, detail="Нет данных пользователя")
    return int(tg_id)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ---------------- страницы ----------------

@app.get("/client", response_class=HTMLResponse)
async def client_page():
    return HTMLResponse(read_template("client.html"), headers={"Cache-Control": "no-store"})


@app.get("/trainer", response_class=HTMLResponse)
async def trainer_page():
    return HTMLResponse(read_template("trainer.html"), headers={"Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h3>FitBot backend работает. Откройте приложение через кнопку в Telegram-боте.</h3>"


# ---------------- видео (прокси к Telegram, т.к. видео хранится в Telegram) ----------------

@app.get("/api/video/{exercise_id}")
async def video_redirect(exercise_id: int):
    ex = db.get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile", params={"file_id": ex["file_id"]})
        data = r.json()
        if not data.get("ok"):
            raise HTTPException(502, "Не удалось получить файл из Telegram")
        file_path = data["result"]["file_path"]
    return RedirectResponse(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}")


# ---------------- API: клиент ----------------

@app.get("/api/client/me")
async def api_client_me(request: Request):
    tg_id = current_tg_id(request)
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден. Отправьте /start в бота.")
    return user


@app.get("/api/client/nutrition-tips")
async def api_nutrition_tips(request: Request):
    current_tg_id(request)
    return db.list_nutrition_tips()


@app.get("/api/client/warmups")
async def api_warmups(request: Request):
    current_tg_id(request)
    return db.list_warmups()


@app.get("/api/client/plan")
async def api_client_plan(request: Request):
    tg_id = current_tg_id(request)
    week_start = monday_of(date.today()).isoformat()
    plan = db.get_plan_with_items(tg_id, week_start)
    return plan or {"week_start": week_start, "items": []}


@app.post("/api/client/weight-report")
async def api_add_weight(request: Request):
    tg_id = current_tg_id(request)
    body = await request.json()
    db.add_weight_report(tg_id, weight=float(body["weight"]), note=body.get("note", ""))
    return {"ok": True}


@app.get("/api/client/weight-reports")
async def api_weight_history(request: Request):
    tg_id = current_tg_id(request)
    return db.list_weight_reports(tg_id)


@app.post("/api/client/nutrition-report")
async def api_add_nutrition(request: Request):
    tg_id = current_tg_id(request)
    body = await request.json()
    db.add_nutrition_report(tg_id, description=body.get("description", ""))
    return {"ok": True}


@app.get("/api/client/nutrition-reports")
async def api_nutrition_history(request: Request):
    tg_id = current_tg_id(request)
    return db.list_nutrition_reports(tg_id)


@app.get("/api/client/trainer-link")
async def api_trainer_link(request: Request):
    current_tg_id(request)
    return {"username": TRAINER_USERNAME}


# ---------------- API: тренер ----------------

def require_trainer(request: Request) -> int:
    tg_id = current_tg_id(request)
    if tg_id != TRAINER_TG_ID:
        raise HTTPException(403, "Доступно только тренеру")
    return tg_id


@app.get("/api/trainer/clients")
async def api_trainer_clients(request: Request):
    require_trainer(request)
    return db.list_clients()


@app.get("/api/trainer/exercises")
async def api_trainer_exercises(request: Request):
    tg_id = require_trainer(request)
    return db.list_exercises(tg_id)


@app.get("/api/trainer/recommend")
async def api_trainer_recommend(request: Request, client_tg_id: int):
    tg_id = require_trainer(request)
    return db.recommended_exercise_order(tg_id, client_tg_id)


@app.get("/api/trainer/plan")
async def api_trainer_get_plan(request: Request, client_tg_id: int, week_start: str):
    require_trainer(request)
    plan = db.get_plan_with_items(client_tg_id, week_start)
    return plan or {"week_start": week_start, "items": []}


@app.post("/api/trainer/plan")
async def api_trainer_save_plan(request: Request):
    require_trainer(request)
    body = await request.json()
    client_tg_id = body["client_tg_id"]
    week_start = body["week_start"]
    items = body["items"]  # [{day_of_week, exercise_id, sets_reps, notes}]
    plan = db.get_or_create_plan(client_tg_id, week_start)
    db.replace_plan_items(plan["id"], items)
    try:
        from aiogram import Bot
        bot = Bot(BOT_TOKEN)
        await bot.send_message(client_tg_id, "Тренер обновил вашу программу на неделю 📋 Загляните в кабинет.")
        await bot.session.close()
    except Exception:
        pass
    return {"ok": True}


@app.get("/api/trainer/client-reports")
async def api_trainer_client_reports(request: Request, client_tg_id: int):
    require_trainer(request)
    return {
        "weight": db.list_weight_reports(client_tg_id, limit=60),
        "nutrition": db.list_nutrition_reports(client_tg_id, limit=60),
    }
