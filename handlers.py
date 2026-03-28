import asyncio
import math
import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from translations import t, ts
from keyboards import (
    lang_keyboard, start_form_keyboard, back_keyboard,
    main_menu, profile_edit_keyboard, cancel_keyboard,
    channel_keyboard, website_keyboard, webapp_keyboard, webapp_inline_keyboard,
    admin_main_keyboard, admin_model_keyboard, admin_list_keyboard,
    ANKETA_FIELDS
)
from config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 5

_bot_username: str | None = None

# ─── FORM FIELD KEYS (ordered) ──────────────────────────────────────────────

FORM_QUESTIONS = [
    "q1", "q2", "q3", "q4", "q5",
    "q6", "q7", "q8", "q9", "q10"
]
# maps question index -> anketa field name
Q_TO_FIELD = {
    0: "full_name",
    1: "height",
    2: "weight",
    3: "phone_model",
    4: "socials",
    5: "location",
    6: "limits",
    7: "desired_income",
    8: "experience",
    9: "goals",
}


# ─── FSM STATES ──────────────────────────────────────────────────────────────

class FormState(StatesGroup):
    filling = State()   # answering form questions; step stored in DB


class EditState(StatesGroup):
    waiting = State()   # waiting for new field value


# ─── HELPERS ─────────────────────────────────────────────────────────────────

async def get_lang(tg_id: int) -> str:
    user = await db.get_user(tg_id)
    return user["language"] if user else "ru"


async def send_question(message_or_callback, lang: str, step: int, state: FSMContext):
    """Send the question for the given step (0-indexed)."""
    question_key = FORM_QUESTIONS[step]
    text = t(lang, question_key)
    kb = back_keyboard(lang) if step > 0 else None
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=kb)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=kb)


def build_profile_text(lang: str, anketa: dict, status: str) -> str:
    field_names = ts(lang, "field_names")
    statuses = ts(lang, "statuses")
    has_photo = bool(anketa.get("photo_file_id"))
    photo_status = "✅" if has_photo else "—"
    text = t(lang, "profile_title")
    text += t(lang, "profile_status", status=statuses.get(status, status)) + "\n"
    text += f"📷 <b>Фото:</b> {photo_status}\n\n"
    for field in ANKETA_FIELDS:
        if field == "photo_file_id":
            continue  # показываем фото отдельно, не как текст
        val = anketa.get(field) or "—"
        text += f"<b>{field_names.get(field, field)}:</b> {val}\n"
    return text


def build_model_card(lang: str, user: dict, anketa: dict | None, refs_count: int) -> str:
    a = anketa or {}
    return t(
        lang, "admin_model_card",
        name=a.get("full_name") or user.get("tg_username") or str(user["tg_id"]),
        tg_id=user["tg_id"],
        username=user.get("tg_username") or "—",
        status=ts(lang, "statuses").get(user["status"], user["status"]),
        refs=refs_count,
        income=user.get("income", 0) or 0,
        full_name=a.get("full_name") or "—",
        height=a.get("height") or "—",
        weight=a.get("weight") or "—",
        phone_model=a.get("phone_model") or "—",
        socials=a.get("socials") or "—",
        location=a.get("location") or "—",
        limits=a.get("limits") or "—",
        desired_income=a.get("desired_income") or "—",
        experience=a.get("experience") or "—",
        goals=a.get("goals") or "—",
    )


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    tg_id = message.from_user.id
    username = message.from_user.username

    # Parse referral param
    ref_by = None
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_by = int(args[1][4:])
            if ref_by == tg_id:
                ref_by = None
        except ValueError:
            pass

    user = await db.get_user(tg_id)
    if not user:
        await db.create_user(tg_id, username, ref_by=ref_by)
        user = await db.get_user(tg_id)
    lang = user["language"]

    # If already filled form — show main menu
    if user["status"] not in ("new", "filling"):
        await message.answer(
            t(lang, "welcome"),
            reply_markup=main_menu(lang, tg_id)
        )
        return

    # Show language selection if new
    if not lang or user["status"] == "new":
        await message.answer(
            t("ru", "choose_lang"),
            reply_markup=lang_keyboard()
        )
    else:
        await message.answer(
            t(lang, "welcome"),
            reply_markup=start_form_keyboard(lang)
        )


# ─── LANGUAGE SELECTION ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":")[1]
    tg_id = callback.from_user.id
    await db.update_user(tg_id, language=lang)
    user = await db.get_user(tg_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    if user["status"] not in ("new", "filling"):
        # User already completed form — send new reply keyboard in chosen language
        await callback.message.answer(
            t(lang, "welcome"),
            reply_markup=main_menu(lang, tg_id)
        )
    else:
        await callback.message.answer(
            t(lang, "welcome"),
            reply_markup=start_form_keyboard(lang)
        )
    await callback.answer()


# ─── START FORM ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "form:start")
async def cb_form_start(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    lang = await get_lang(tg_id)
    await db.update_user(tg_id, status="filling", step=0)
    await state.set_state(FormState.filling)
    await state.update_data(step=0)
    await callback.message.delete()
    await send_question(callback.message, lang, 0, state)
    await callback.answer()


# ─── FORM — BACK BUTTON ──────────────────────────────────────────────────────

@router.callback_query(F.data == "form:back", FormState.filling)
async def cb_form_back(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    lang = await get_lang(tg_id)
    data = await state.get_data()
    step = data.get("step", 0)
    if step > 0:
        step -= 1
        await state.update_data(step=step)
        await db.update_user(tg_id, step=step)
    await send_question(callback, lang, step, state)
    await callback.answer()


# ─── FORM — ANSWER ───────────────────────────────────────────────────────────

@router.message(FormState.filling)
async def form_answer(message: Message, state: FSMContext, bot: Bot):
    tg_id = message.from_user.id
    lang = await get_lang(tg_id)
    data = await state.get_data()
    step = data.get("step", 0)

    # Save answer to anketa
    field = Q_TO_FIELD[step]
    await db.upsert_anketa(tg_id, **{field: message.text})

    step += 1
    if step < len(FORM_QUESTIONS):
        await state.update_data(step=step)
        await db.update_user(tg_id, step=step)
        await send_question(message, lang, step, state)
    else:
        # Form completed
        await state.clear()
        await db.update_user(tg_id, status="reviewing", step=len(FORM_QUESTIONS))

        # Notify admin
        anketa = await db.get_anketa(tg_id)
        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                t("ru", "admin_new_anketa",
                  name=anketa.get("full_name") or "—",
                  tg_id=tg_id,
                  username=message.from_user.username or "—")
            )
        except Exception as e:
            logger.warning(f"Cannot notify admin about new anketa {tg_id}: {e}")

        await message.answer(
            t(lang, "form_done"),
            reply_markup=main_menu(lang, tg_id)
        )


# ─── MAIN MENU — PROFILE ─────────────────────────────────────────────────────

@router.message(F.text.in_(["📋 Профиль", "📋 Profile"]))
async def menu_profile(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    lang = await get_lang(tg_id)
    user, anketa = await asyncio.gather(db.get_user(tg_id), db.get_anketa(tg_id))
    if not user:
        await message.answer(t(lang, "start_prompt"))
        return
    anketa = anketa or {}
    text = build_profile_text(lang, anketa, user["status"])
    photo_id = anketa.get("photo_file_id")
    kb = profile_edit_keyboard(lang)
    if photo_id and len(text) <= 1024:
        try:
            await message.answer_photo(photo=photo_id, caption=text, reply_markup=kb)
            return
        except Exception as e:
            logger.warning(f"answer_photo failed for {tg_id}: {e}")
    await message.answer(text, reply_markup=kb)


# ─── EDIT FIELD — REQUEST ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit:") & ~F.data.startswith("edit:cancel"))
async def cb_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    if field == "cancel":
        return
    tg_id = callback.from_user.id
    lang = await get_lang(tg_id)
    edit_prompts = ts(lang, "edit_prompts")
    field_names = ts(lang, "field_names")
    await state.set_state(EditState.waiting)
    await state.update_data(edit_field=field)
    # Используем персональный prompt для каждого поля
    prompt = edit_prompts.get(field) or t(lang, "edit_field", field=field_names.get(field, field))
    await callback.message.answer(prompt, reply_markup=cancel_keyboard(lang))
    await callback.answer()


# ─── EDIT FIELD — CANCEL ─────────────────────────────────────────────────────

@router.callback_query(F.data == "edit:cancel")
async def cb_edit_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(t(lang, "edit_cancelled"))
    await callback.answer()


# ─── EDIT FIELD — SAVE ───────────────────────────────────────────────────────

@router.message(EditState.waiting, F.text)  # только текст — фото перехватывает handlers_new
async def edit_save(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    lang = await get_lang(tg_id)
    data = await state.get_data()
    field = data.get("edit_field")

    if field:
        await db.upsert_anketa(tg_id, **{field: message.text})
    await state.clear()
    user, anketa = await asyncio.gather(db.get_user(tg_id), db.get_anketa(tg_id))
    anketa = anketa or {}
    text = t(lang, "field_updated") + "\n\n" + build_profile_text(lang, anketa, user["status"])
    photo_id = anketa.get("photo_file_id")
    kb = profile_edit_keyboard(lang)
    if photo_id and len(text) <= 1024:
        try:
            await message.answer_photo(photo=photo_id, caption=text, reply_markup=kb)
            return
        except Exception as e:
            logger.warning(f"answer_photo failed for {tg_id}: {e}")
    await message.answer(text, reply_markup=kb)


# ─── MAIN MENU — LANGUAGE ────────────────────────────────────────────────────

@router.message(F.text.in_(["🌍 Язык", "🌍 Language"]))
async def menu_lang(message: Message):
    await message.answer(
        t("ru", "choose_lang"),
        reply_markup=lang_keyboard()
    )


# ─── MAIN MENU — BONUS ──────────────────────────────────────────────────────

@router.message(F.text.in_(["🎁 Получить бонус", "🎁 Get bonus"]))
async def menu_bonus(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "bonus_message"))


# ─── MAIN MENU — REFERRALS ───────────────────────────────────────────────────

@router.message(F.text.in_(["🤝 Рефералы", "🤝 Referrals"]))
async def menu_referrals(message: Message):
    tg_id = message.from_user.id
    lang = await get_lang(tg_id)
    user = await db.get_user(tg_id)
    if not user:
        await message.answer(t(lang, "start_prompt"))
        return
    refs = await db.get_referrals(tg_id)
    bonuses = await db.get_ref_bonuses(tg_id)

    global _bot_username
    if _bot_username is None:
        bot_me = await message.bot.get_me()
        _bot_username = bot_me.username or "your_bot"
    bot_info_name = _bot_username
    ref_link = f"https://t.me/{bot_info_name}?start=ref_{tg_id}"

    text = t(lang, "referrals_title")
    text += t(lang, "ref_link", link=ref_link)
    text += t(lang, "ref_count", count=len(refs))

    # Показываем список рефералов если есть
    if refs:
        text += "\n"
        for r in refs[:10]:  # не больше 10 строк
            ref_name = r.get("tg_username") or str(r["tg_id"])
            text += f"  • @{ref_name}\n"
        if len(refs) > 10:
            text += f"  <i>...и ещё {len(refs) - 10}</i>\n"
        text += "\n"

    text += t(lang, "ref_balance", balance=user.get("balance", 0) or 0)

    if bonuses:
        text += t(lang, "ref_bonuses_title")
        for b in bonuses:
            text += t(lang, "ref_bonus_item", amount=b["amount"])
    else:
        text += t(lang, "ref_no_bonuses")

    text += t(lang, "ref_program_info")
    await message.answer(text)


# ─── MAIN MENU — ЛИЧНЫЙ КАБИНЕТ (Mini App) ───────────────────────────────────

@router.message(F.text == "📱 Личный кабинет")
async def menu_webapp(message: Message):
    from web_server import generate_signed_url
    tg_id = message.from_user.id
    username = message.from_user.username or ""
    is_admin = tg_id == ADMIN_CHAT_ID
    signed_url = generate_signed_url(tg_id, username, is_admin)
    await message.answer(
        "📱 Открой личный кабинет:",
        reply_markup=webapp_inline_keyboard(signed_url)
    )


# ─── MAIN MENU — CHANNEL ─────────────────────────────────────────────────────

@router.message(F.text.in_(["📢 Наш канал", "📢 Our channel"]))
async def menu_channel(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(
        t(lang, "btn_channel"),
        reply_markup=channel_keyboard(lang)
    )


# ─── MAIN MENU — WEBSITE ─────────────────────────────────────────────────────

@router.message(F.text.in_(["🌐 Наш сайт", "🌐 Our website"]))
async def menu_website(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(
        t(lang, "btn_website"),
        reply_markup=website_keyboard(lang)
    )


# ─── /admin + ADMIN BUTTON ───────────────────────────────────────────────────

async def show_admin_home(target, lang: str = "ru"):
    if isinstance(target, Message):
        await target.answer(t(lang, "admin_menu"), reply_markup=admin_main_keyboard())
    else:
        await target.message.edit_text(t(lang, "admin_menu"), reply_markup=admin_main_keyboard())


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await show_admin_home(message)


@router.message(F.text.in_(["🔧 Админка", "🔧 Admin panel"]))
async def menu_admin(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await show_admin_home(message)


# ─── ADMIN — HOME ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:home")
async def adm_home(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return
    await show_admin_home(callback)
    await callback.answer()


# ─── ADMIN — STATS ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:stats")
async def adm_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return
    stats = await db.get_stats()
    builder_kb = admin_main_keyboard()
    await callback.message.edit_text(
        t("ru", "admin_stats", **stats),
        reply_markup=builder_kb
    )
    await callback.answer()


# ─── ADMIN — LIST ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:list:"))
async def adm_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return

    parts = callback.data.split(":")
    # adm:list:<status>:<offset>
    status_filter = parts[2]
    offset = int(parts[3])

    status_arg = None if status_filter == "all" else status_filter
    models = await db.get_all_users(status=status_arg, offset=offset, limit=PAGE_SIZE)
    total = await db.count_users(status=status_arg)

    if not models:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        b = InlineKeyboardBuilder()
        b.button(text=t("ru", "btn_back_admin"), callback_data="adm:home")
        await callback.message.edit_text(
            t("ru", "admin_no_models"),
            reply_markup=b.as_markup()
        )
        await callback.answer()
        return

    page = offset // PAGE_SIZE + 1
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    header = f"📋 {status_filter.upper()} — {t('ru', 'page', page=page, total=total_pages)}\n\n"

    # Build short list text
    lines = []
    statuses_map = ts("ru", "statuses")
    for m in models:
        name = m.get("full_name") or m.get("tg_username") or str(m["tg_id"])
        lines.append(f"• {name} — {statuses_map.get(m['status'], m['status'])}")
    text = header + "\n".join(lines)

    kb = admin_list_keyboard(models, status_filter, offset, total, PAGE_SIZE)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ─── ADMIN — VIEW MODEL ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:view:"))
async def adm_view(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return

    parts = callback.data.split(":")
    # adm:view:<tg_id>:<list_status>:<offset>
    model_tg_id = int(parts[2])
    list_status = parts[3]
    offset = int(parts[4])

    user, anketa, refs = await asyncio.gather(
        db.get_user(model_tg_id),
        db.get_anketa(model_tg_id),
        db.get_referrals(model_tg_id),
    )

    if not user:
        await callback.answer("Пользователь не найден")
        return

    text = build_model_card("ru", user, anketa, len(refs))
    kb = admin_model_keyboard(model_tg_id, user["status"], list_status, offset)
    photo_id = (anketa or {}).get("photo_file_id")

    if photo_id:
        # Удаляем текущее сообщение и отправляем фото с текстом в одном сообщении
        try:
            await callback.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete message: {e}")
        caption = text if len(text) <= 1024 else text[:1021] + "..."
        try:
            await callback.message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb)
        except Exception as e:
            logger.warning(f"answer_photo failed in adm_view: {e}")
            await callback.message.answer(text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ─── ADMIN — SET STATUS ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:set:"))
async def adm_set_status(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return

    parts = callback.data.split(":")
    # adm:set:<tg_id>:<new_status>
    model_tg_id = int(parts[2])
    new_status = parts[3]

    old_model = await db.get_user(model_tg_id)
    old_status = old_model["status"] if old_model else "unknown"
    lang = old_model["language"] if old_model else "ru"
    await db.update_user(model_tg_id, status=new_status)
    await db.add_status_history(model_tg_id, old_status, new_status)

    # Notify the model (lang already set from old_model)
    notify_map = {
        "approved": "notify_approved",
        "rejected": "notify_rejected",
        "active":   "notify_active",
    }
    if new_status in notify_map:
        try:
            await bot.send_message(model_tg_id, t(lang, notify_map[new_status]))
        except Exception as e:
            logger.warning(f"Cannot notify {model_tg_id}: {e}")

    # Refresh view — parallel fetch
    updated_user, anketa, refs = await asyncio.gather(
        db.get_user(model_tg_id),
        db.get_anketa(model_tg_id),
        db.get_referrals(model_tg_id),
    )
    text = build_model_card("ru", updated_user, anketa, len(refs))
    kb = admin_model_keyboard(model_tg_id, new_status, "all", 0)
    # Если текущее сообщение — фото (с caption), редактируем caption; иначе text
    if callback.message.photo:
        caption = text if len(text) <= 1024 else text[:1021] + "..."
        try:
            await callback.message.edit_caption(caption=caption, reply_markup=kb)
        except Exception as e:
            logger.warning(f"edit_caption failed in adm_set_status: {e}")
            await callback.message.answer(text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer(f"✅ Статус изменён на: {new_status}")
