"""
handlers_earnings.py
────────────────────
Новый роутер — подключается к боту рядом с основным router.
Добавь в bot.py:

    from handlers_earnings import router as earnings_router
    dp.include_router(earnings_router)

Не трогает существующий handlers.py.
"""

import asyncio
import logging
from datetime import date, datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)
router = Router()

# ─── FSM ─────────────────────────────────────────────────────────────────────

class AddEarningState(StatesGroup):
    choose_model    = State()   # admin выбирает модель
    choose_platform = State()   # admin выбирает площадку
    enter_date      = State()   # admin вводит дату
    enter_amount    = State()   # admin вводит сумму

class SetPlatformState(StatesGroup):
    choose = State()            # модель выбирает площадки


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def is_admin(tg_id: int) -> bool:
    return tg_id == ADMIN_CHAT_ID


def current_ym() -> tuple[int, int]:
    now = datetime.now()
    return now.year, now.month


def month_name(month: int, lang: str = "ru") -> str:
    names_ru = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
    names_en = ["January","February","March","April","May","June",
                "July","August","September","October","November","December"]
    return (names_ru if lang == "ru" else names_en)[month - 1]


def build_calendar_text(earnings: list[dict], year: int, month: int, month_total: float) -> str:
    """Текстовый календарь заработка для модели."""
    # Группируем по дням
    by_day: dict[str, list] = {}
    for e in earnings:
        d = e["date"]
        by_day.setdefault(d, []).append(e)

    lines = [f"📅 <b>{month_name(month)} {year}</b>\n💵 Итого: <b>${month_total:.0f}</b>\n"]

    for day_str in sorted(by_day.keys()):
        day_entries = by_day[day_str]
        day_total = sum(e["amount"] for e in day_entries)
        day_num = day_str.split("-")[2]

        if len(day_entries) == 1:
            # Одна площадка — всё в одну строку
            e = day_entries[0]
            lines.append(f"<b>{day_num}</b>  📌 {e['platform_name']}: <b>${e['amount']:.0f}</b>")
        else:
            # Несколько площадок — разбиваем по строкам
            lines.append(f"<b>{day_num}</b>  💵 <b>${day_total:.0f}</b>")
            for e in day_entries:
                lines.append(f"     • {e['platform_name']}: ${e['amount']:.0f}")

    if not by_day:
        lines.append("Данных за этот месяц пока нет.")
    return "\n".join(lines)


def earnings_nav_kb(tg_id: int, year: int, month: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    # предыдущий месяц
    pm, py = (month - 1, year) if month > 1 else (12, year - 1)
    nm, ny = (month + 1, year) if month < 12 else (1, year + 1)
    builder.button(text="◀", callback_data=f"earn:cal:{tg_id}:{py}:{pm}")
    builder.button(text=f"{month_name(month)} {year}", callback_data="earn:noop")
    builder.button(text="▶", callback_data=f"earn:cal:{tg_id}:{ny}:{nm}")
    builder.adjust(3)
    return builder


# ═══════════════════════════════════════════════════════════════════════════════
# МОДЕЛЬ: кнопка «📊 Мои доходы» в главном меню
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(F.text.in_(["📊 Мои доходы", "📊 My earnings"]))
async def menu_earnings(message: Message):
    tg_id = message.from_user.id
    year, month = current_ym()
    pm, py = (month - 1, year) if month > 1 else (12, year - 1)

    earnings, month_total, prev_total, platforms = await asyncio.gather(
        db.get_earnings_for_month(tg_id, year, month),
        db.get_monthly_total(tg_id, year, month),
        db.get_monthly_total(tg_id, py, pm),
        db.get_model_platforms(tg_id),
    )

    text = build_calendar_text(earnings, year, month, month_total)
    text += f"\n\n📌 Прошлый месяц: <b>${prev_total:.0f}</b>"
    if platforms:
        plat_names = ", ".join(p["platform_name"] for p in platforms)
        text += f"\n🔗 Площадки: {plat_names}"

    builder = earnings_nav_kb(tg_id, year, month)
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("earn:cal:"))
async def cb_earnings_nav(callback: CallbackQuery):
    parts = callback.data.split(":")
    tg_id = int(parts[2])
    year  = int(parts[3])
    month = int(parts[4])

    # Проверка: модель видит только своё, админ — любого
    if callback.from_user.id != tg_id and not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return

    earnings = await db.get_earnings_for_month(tg_id, year, month)
    month_total = await db.get_monthly_total(tg_id, year, month)
    text = build_calendar_text(earnings, year, month, month_total)

    builder = earnings_nav_kb(tg_id, year, month)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "earn:noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# МОДЕЛЬ: управление своими площадками
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(F.text.in_(["🔗 Мои площадки", "🔗 My platforms"]))
async def menu_platforms(message: Message):
    tg_id = message.from_user.id
    all_platforms = await db.get_all_platforms()
    my_platforms  = await db.get_model_platforms(tg_id)
    my_ids = {p["platform_id"] for p in my_platforms}

    builder = InlineKeyboardBuilder()
    for p in all_platforms:
        tick = "✅" if p["id"] in my_ids else "⬜"
        builder.button(
            text=f"{tick} {p['name']}",
            callback_data=f"plat:toggle:{p['id']}"
        )
    builder.adjust(2)
    await message.answer("Выбери площадки на которых ты работаешь:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("plat:toggle:"))
async def cb_platform_toggle(callback: CallbackQuery):
    tg_id = callback.from_user.id
    platform_id = int(callback.data.split(":")[2])

    my_platforms = await db.get_model_platforms(tg_id)
    my_ids = {p["platform_id"] for p in my_platforms}

    if platform_id in my_ids:
        await db.remove_model_platform(tg_id, platform_id)
    else:
        await db.set_model_platform(tg_id, platform_id)

    # Обновляем клавиатуру
    all_platforms = await db.get_all_platforms()
    my_platforms  = await db.get_model_platforms(tg_id)
    my_ids = {p["platform_id"] for p in my_platforms}

    builder = InlineKeyboardBuilder()
    for p in all_platforms:
        tick = "✅" if p["id"] in my_ids else "⬜"
        builder.button(
            text=f"{tick} {p['name']}",
            callback_data=f"plat:toggle:{p['id']}"
        )
    builder.adjust(2)
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN: внести заработок (FSM)
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:add_earning")
async def adm_add_earning_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return

    models = await db.get_all_users(status="active")
    if not models:
        await callback.answer("Нет активных моделей")
        return

    builder = InlineKeyboardBuilder()
    for m in models:
        name = m.get("full_name") or m.get("tg_username") or str(m["tg_id"])
        builder.button(text=f"👤 {name}", callback_data=f"admadd:model:{m['tg_id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardBuilder().button(text="❌ Отмена", callback_data="admadd:cancel").as_markup().inline_keyboard[0][0])

    await state.set_state(AddEarningState.choose_model)
    await callback.message.edit_text("Выбери модель:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admadd:model:"), AddEarningState.choose_model)
async def adm_add_choose_platform(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return

    tg_id = int(callback.data.split(":")[2])
    await state.update_data(target_tg_id=tg_id)

    platforms = await db.get_all_platforms()
    builder = InlineKeyboardBuilder()
    for p in platforms:
        builder.button(text=p["name"], callback_data=f"admadd:plat:{p['id']}")
    builder.adjust(2)
    builder.row(InlineKeyboardBuilder().button(text="❌ Отмена", callback_data="admadd:cancel").as_markup().inline_keyboard[0][0])

    await state.set_state(AddEarningState.choose_platform)
    await callback.message.edit_text("Выбери площадку:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admadd:plat:"), AddEarningState.choose_platform)
async def adm_add_enter_date(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return

    platform_id = int(callback.data.split(":")[2])
    await state.update_data(platform_id=platform_id)

    today = date.today().strftime("%d.%m.%Y")
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📅 Сегодня ({today})", callback_data=f"admadd:date:today")
    builder.button(text="❌ Отмена", callback_data="admadd:cancel")
    builder.adjust(1)

    await state.set_state(AddEarningState.enter_date)
    await callback.message.edit_text(
        f"Введи дату в формате <b>ДД.ММ.ГГГГ</b>\n\nИли нажми кнопку для сегодняшней даты:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admadd:date:today", AddEarningState.enter_date)
async def adm_add_date_today(callback: CallbackQuery, state: FSMContext):
    today = date.today().strftime("%Y-%m-%d")
    await state.update_data(earn_date=today)
    await state.set_state(AddEarningState.enter_amount)
    await callback.message.edit_text("Введи сумму заработка в $:\n\n<i>Например: 150 или 89.50</i>")
    await callback.answer()


@router.message(AddEarningState.enter_date)
async def adm_add_date_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        parsed = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        earn_date = parsed.strftime("%Y-%m-%d")
    except ValueError:
        await message.answer("❌ Неверный формат. Введи дату как <b>ДД.ММ.ГГГГ</b>")
        return

    await state.update_data(earn_date=earn_date)
    await state.set_state(AddEarningState.enter_amount)
    await message.answer("Введи сумму заработка в $:\n\n<i>Например: 150 или 89.50</i>")


@router.message(AddEarningState.enter_amount)
async def adm_add_amount(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи корректную сумму, например: <b>250</b> или <b>89.50</b>")
        return

    data = await state.get_data()
    tg_id       = data["target_tg_id"]
    platform_id = data["platform_id"]
    earn_date   = data["earn_date"]

    await db.upsert_earning(tg_id, platform_id, earn_date, amount, added_by="admin")
    await state.clear()

    # Получаем название площадки и имя модели для подтверждения
    platform = await db.get_platform_by_id(platform_id)
    anketa   = await db.get_anketa(tg_id)
    model_name = (anketa or {}).get("full_name") or str(tg_id)
    plat_name  = (platform or {}).get("name", str(platform_id))

    display_date = datetime.strptime(earn_date, "%Y-%m-%d").strftime("%d.%m.%Y")

    await message.answer(
        f"✅ Сохранено!\n\n"
        f"👤 Модель: <b>{model_name}</b>\n"
        f"🏷 Площадка: <b>{plat_name}</b>\n"
        f"📅 Дата: <b>{display_date}</b>\n"
        f"💵 Сумма: <b>${amount:.2f}</b>",
        reply_markup=_back_to_admin_kb()
    )

    # Уведомляем модель
    try:
        await bot.send_message(
            tg_id,
            f"💰 Добавлен новый заработок!\n"
            f"📅 {display_date}  |  {plat_name}  |  <b>${amount:.2f}</b>"
        )
    except Exception as e:
        logger.warning(f"Cannot notify model {tg_id}: {e}")


@router.callback_query(F.data == "admadd:cancel")
async def adm_add_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено.", reply_markup=_back_to_admin_kb())
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN: общая таблица моделей с заработком
# ═══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm:earnings"))
async def adm_earnings_overview(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔")
        return

    parts = callback.data.split(":")
    year  = int(parts[2]) if len(parts) > 2 else datetime.now().year
    month = int(parts[3]) if len(parts) > 3 else datetime.now().month

    models_stats = await db.get_all_models_monthly_stats(year, month)
    plat_stats   = await db.get_earnings_by_platform_month(year, month)

    grand_total = sum(m["month_total"] for m in models_stats)

    lines = [f"📊 <b>Заработок — {month_name(month)} {year}</b>\n"]
    lines.append(f"💵 Итого по всем моделям: <b>${grand_total:.0f}</b>\n")

    # По площадкам
    if plat_stats:
        lines.append("─── По площадкам ───")
        for p in plat_stats:
            if p["total"] > 0:
                lines.append(f"• {p['name']}: <b>${p['total']:.0f}</b> ({p['models_count']} мод.)")
        lines.append("")

    # По моделям
    lines.append("─── По моделям ───")
    for m in models_stats:
        name = m.get("full_name") or m.get("tg_username") or str(m["tg_id"])
        ref_mark = " 🔗" if m.get("ref_by") else ""
        lines.append(f"• {name}{ref_mark}: <b>${m['month_total']:.0f}</b>")

    if not models_stats:
        lines.append("Данных за этот месяц нет.")

    # Навигация
    pm, py = (month - 1, year) if month > 1 else (12, year - 1)
    nm, ny = (month + 1, year) if month < 12 else (1, year + 1)

    builder = InlineKeyboardBuilder()
    builder.button(text="◀", callback_data=f"adm:earnings:{py}:{pm}")
    builder.button(text=f"{month_name(month)[:3]} {year}", callback_data="earn:noop")
    builder.button(text="▶", callback_data=f"adm:earnings:{ny}:{nm}")
    builder.adjust(3)
    builder.row(
        InlineKeyboardBuilder().button(
            text="➕ Внести заработок", callback_data="adm:add_earning"
        ).as_markup().inline_keyboard[0][0]
    )
    builder.row(
        InlineKeyboardBuilder().button(
            text="🏠 Главная", callback_data="adm:home"
        ).as_markup().inline_keyboard[0][0]
    )

    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _back_to_admin_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главная", callback_data="adm:home")
    builder.button(text="📊 Заработок", callback_data=f"adm:earnings:{datetime.now().year}:{datetime.now().month}")
    builder.adjust(2)
    return builder.as_markup()
