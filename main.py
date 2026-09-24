import asyncio
import os

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

import db
from bot.handlers import router as bot_router
from webapp.server import app as fastapi_app

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "8080"))


async def run_bot():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(bot_router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def run_web():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан. Проверьте переменные окружения (.env или настройки хостинга).")
    db.init_db()
    await asyncio.gather(run_bot(), run_web())


if __name__ == "__main__":
    asyncio.run(main())
