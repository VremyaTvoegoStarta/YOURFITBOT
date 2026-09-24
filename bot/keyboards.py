from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


def yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да, я уже занимаюсь"), KeyboardButton(text="Нет, я новый клиент")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def contact_method_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Telegram"), KeyboardButton(text="WhatsApp")],
            [KeyboardButton(text="Звонок")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def contact_time_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Утро"), KeyboardButton(text="День")],
            [KeyboardButton(text="Вечер")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def client_cabinet_kb(public_url: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Открыть личный кабинет", web_app=WebAppInfo(url=f"{public_url}/client"))]],
        resize_keyboard=True,
    )


def trainer_cabinet_kb(public_url: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🗂 Открыть кабинет тренера", web_app=WebAppInfo(url=f"{public_url}/trainer"))]],
        resize_keyboard=True,
    )
