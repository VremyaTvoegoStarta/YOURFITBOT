import os
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import db
from bot.keyboards import (
    yes_no_kb, contact_method_kb, contact_time_kb,
    client_cabinet_kb, trainer_cabinet_kb,
)

router = Router()

TRAINER_TG_ID = int(os.getenv("TRAINER_TG_ID", "0"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")


class Onboarding(StatesGroup):
    name = State()
    age = State()
    goal = State()
    existing = State()
    contact_method = State()
    contact_time = State()


def is_trainer(tg_id: int) -> bool:
    return TRAINER_TG_ID != 0 and tg_id == TRAINER_TG_ID


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    role = "trainer" if is_trainer(tg_id) else "client"
    user = db.upsert_user_start(tg_id, role=role)

    if role == "trainer":
        await message.answer(
            "Привет! Это ваш кабинет тренера.\n\n"
            "— Чтобы добавить видео упражнения в библиотеку, просто пришлите видео сюда, "
            "в подписи укажите название (и через | теги, например: «Присед со штангой | ноги,база»).\n"
            "— Собирать программы и смотреть клиентов — через кнопку ниже.",
            reply_markup=trainer_cabinet_kb(PUBLIC_URL),
        )
        return

    if user.get("onboarded"):
        await message.answer(
            f"С возвращением, {user.get('name') or ''}! Открыть кабинет — кнопкой ниже.",
            reply_markup=client_cabinet_kb(PUBLIC_URL),
        )
        return

    await message.answer(
        "Привет! Я бот вашего тренера 💪\n"
        "Заполним короткую анкету перед началом.\n\n"
        "Как вас зовут?"
    )
    await state.set_state(Onboarding.name)


@router.message(Onboarding.name)
async def onb_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Сколько вам лет?")
    await state.set_state(Onboarding.age)


@router.message(Onboarding.age)
async def onb_age(message: Message, state: FSMContext):
    age_text = message.text.strip()
    age = int(age_text) if age_text.isdigit() else None
    await state.update_data(age=age)
    await message.answer("Какая у вас цель? (например: похудение, набор массы, тонус, реабилитация)")
    await state.set_state(Onboarding.goal)


@router.message(Onboarding.goal)
async def onb_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text.strip())
    await message.answer("Вы уже занимаетесь с тренером или начинаете заново?", reply_markup=yes_no_kb())
    await state.set_state(Onboarding.existing)


@router.message(Onboarding.existing)
async def onb_existing(message: Message, state: FSMContext):
    is_existing = message.text.strip().lower().startswith("да")
    await state.update_data(existing=is_existing)
    await message.answer("Как вам удобнее держать связь?", reply_markup=contact_method_kb())
    await state.set_state(Onboarding.contact_method)


@router.message(Onboarding.contact_method)
async def onb_contact_method(message: Message, state: FSMContext):
    await state.update_data(contact_method=message.text.strip())
    await message.answer("В какое время удобнее звонить/писать?", reply_markup=contact_time_kb())
    await state.set_state(Onboarding.contact_time)


@router.message(Onboarding.contact_time)
async def onb_contact_time(message: Message, state: FSMContext):
    data = await state.update_data(contact_time=message.text.strip())
    db.save_questionnaire(
        tg_id=message.from_user.id,
        name=data.get("name"),
        age=data.get("age"),
        goal=data.get("goal"),
        is_existing_client=data.get("existing", False),
        contact_method=data.get("contact_method"),
        contact_time=data.get("contact_time"),
    )
    await state.clear()
    await message.answer(
        "Спасибо! Анкета сохранена, тренер получит уведомление.\n"
        "Личный кабинет — кнопкой ниже.",
        reply_markup=client_cabinet_kb(PUBLIC_URL),
    )
    if TRAINER_TG_ID:
        try:
            await message.bot.send_message(
                TRAINER_TG_ID,
                f"🆕 Новая анкета от {data.get('name')} (@{message.from_user.username or '—'})\n"
                f"Возраст: {data.get('age')}\n"
                f"Цель: {data.get('goal')}\n"
                f"Уже клиент: {'да' if data.get('existing') else 'нет'}\n"
                f"Связь: {data.get('contact_method')}, {data.get('contact_time')}",
            )
        except Exception:
            pass


# --- Тренер присылает видео в чат боту -> сохраняем в библиотеку упражнений ---
@router.message(F.video)
async def on_trainer_video(message: Message):
    if not is_trainer(message.from_user.id):
        await message.answer("Видео получено, но добавлять упражнения в библиотеку может только тренер.")
        return
    caption = message.caption or "Без названия"
    if "|" in caption:
        title, tags = caption.split("|", 1)
    else:
        title, tags = caption, ""
    db.add_exercise(
        trainer_tg_id=message.from_user.id,
        title=title.strip(),
        file_id=message.video.file_id,
        tags=tags.strip(),
    )
    await message.answer(f"Сохранено в библиотеку: «{title.strip()}»")


# --- Клиент присылает фото еды в чат боту -> сохраняем как отчёт по питанию ---
@router.message(F.photo)
async def on_client_photo(message: Message):
    if is_trainer(message.from_user.id):
        return
    user = db.get_user(message.from_user.id)
    if not user or not user.get("onboarded"):
        await message.answer("Сначала пройдите короткую анкету — отправьте /start")
        return
    largest = message.photo[-1]
    db.add_nutrition_report(
        client_tg_id=message.from_user.id,
        description=message.caption or "Фото без комментария",
        photo_file_id=largest.file_id,
    )
    await message.answer("Записала в отчёт по питанию 🍽 Можно посмотреть историю в личном кабинете.")
