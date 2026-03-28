"""
handlers_new.py
───────────────
Новый роутер с дополнительными функциями:
- Rate limiting
- Photo upload via EditState
- Payout request
- Write to manager
- Admin broadcast
- Admin notes
- Status history

Подключается в bot.py:
    from handlers_new import router as new_router
    dp.include_router(new_router)
"""

import logging
import time

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import ADMIN_CHAT_ID, MANAGER_USERNAME
from translations import t, ts
from keyboards import payout_confirm_keyboard, manager_keyboard

logger = logging.getLogger(__name__)
router = Router()

# ─── RATE LIMITING ────────────────────────────────────────────────────────────

_rate_limit: dict[int, float] = {}


def check_rate(tg_id: int, seconds: float = 2.0) -> bool:
    """
    Returns True if the user is allowed to proceed (not rate-limited).
    Updates the timestamp for the user.
    """
    now = time.time()
    last = _rate_limit.get(tg_id, 0.0)
    if now - last < seconds:
        return False
    _rate_limit[tg_id] = now
    return True


# ─── FSM STATES ──────────────────────────────────────────────────────────────

class BroadcastState(StatesGroup):
    enter_text = State()


class NoteState(StatesGroup):
    enter = State()


# ─── HELPERS ─────────────────────────────────────────────────────────────────

async def get_lang(tg_id: int) -> str:
    user = await db.get_user(tg_id)
    return user["language"] if user else "ru"


# ─── PHOTO UPLOAD (EditState.waiting) ────────────────────────────────────────
# Import EditState from handlers to reuse — we handle photo messages in that state.
# We use a separate handler that checks state data for edit_field == photo_file_id.

from handlers import EditState  # noqa: E402  (import after router definition is fine)


@router.message(EditState.waiting, F.photo)
async def edit_photo_save(message: Message, state: FSMContext):
    """Handle photo upload when editing photo_file_id field."""
    tg_id = message.from_user.id
    lang = await get_lang(tg_id)
    data = await state.get_data()
    field = data.get("edit_field")

    if field != "photo_file_id":
        # Not editing photo field — ignore photo, let text handler deal with it
        await message.answer(t(lang, "photo_prompt"))
        return

    file_id = message.photo[-1].file_id
    await db.upsert_anketa(tg_id, photo_file_id=file_id)
    await state.clear()
    await message.answer(t(lang, "photo_saved"))


# ─── WRITE TO MANAGER ────────────────────────────────────────────────────────

@router.message(F.text.in_(["💬 Написать менеджеру", "💬 Write to manager"]))
async def menu_write_manager(message: Message):
    tg_id = message.from_user.id
    if not check_rate(tg_id):
        return
    lang = await get_lang(tg_id)
    text = t(lang, "manager_link", username=MANAGER_USERNAME)
    await message.answer(text, reply_markup=manager_keyboard(lang, MANAGER_USERNAME))


# ─── PAYOUT REQUEST ──────────────────────────────────────────────────────────

@router.message(F.text.in_(["💸 Запросить выплату", "💸 Request payout"]))
async def menu_payout(message: Message):
    tg_id = message.from_user.id
    if not check_rate(tg_id):
        return
    lang = await get_lang(tg_id)
    user = await db.get_user(tg_id)
    if not user:
        return
    balance = user.get("balance", 0) or 0
    if balance <= 0:
        await message.answer(t(lang, "payout_no_balance"))
        return
    text = t(lang, "payout_balance", balance=balance)
    await message.answer(text, reply_markup=payout_confirm_keyboard(lang))


@router.callback_query(F.data == "payout:confirm")
async def cb_payout_confirm(callback: CallbackQuery, bot: Bot):
    tg_id = callback.from_user.id
    lang = await get_lang(tg_id)
    user = await db.get_user(tg_id)
    if not user:
        await callback.answer()
        return

    balance = user.get("balance", 0) or 0
    if balance <= 0:
        await callback.message.edit_text(t(lang, "payout_no_balance"))
        await callback.answer()
        return

    request_id = await db.create_payout_request(tg_id, balance)

    # Notify admin
    anketa = await db.get_anketa(tg_id) or {}
    name = anketa.get("full_name") or user.get("tg_username") or str(tg_id)
    try:
        builder = InlineKeyboardBuilder()
        builder.button(
            text="✅ Одобрить выплату",
            callback_data=f"adm:payout:approve:{request_id}"
        )
        await bot.send_message(
            ADMIN_CHAT_ID,
            t("ru", "admin_payout_request", name=name, tg_id=tg_id, amount=balance),
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.warning(f"Cannot notify admin about payout request: {e}")

    await callback.message.edit_text(t(lang, "payout_sent"))
    await callback.answer()


@router.callback_query(F.data == "payout:cancel")
async def cb_payout_cancel(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(t(lang, "edit_cancelled"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:payout:approve:"))
async def cb_adm_payout_approve(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return
    request_id = int(callback.data.split(":")[3])
    await db.update_payout_request(request_id, "approved")

    # Find the request to notify the model
    requests = await db.get_payout_requests(status="approved")
    req = next((r for r in requests if r["id"] == request_id), None)
    if req:
        model_lang = "ru"
        model_user = await db.get_user(req["tg_id"])
        if model_user:
            model_lang = model_user.get("language", "ru")
        try:
            await bot.send_message(
                req["tg_id"],
                f"✅ Ваш запрос на выплату <b>{req['amount']:.2f} ₽</b> одобрен!"
            )
        except Exception as e:
            logger.warning(f"Cannot notify model about payout approval: {e}")

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Одобрено</b>"
    )
    await callback.answer("✅ Выплата одобрена")


# ─── ADMIN BROADCAST ─────────────────────────────────────────────────────────

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await state.set_state(BroadcastState.enter_text)
    await message.answer(t("ru", "broadcast_prompt"))


@router.message(BroadcastState.enter_text)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return

    text = message.text or message.caption or ""
    await state.clear()

    models = await db.get_all_active_models_for_summary()
    count = 0
    for m in models:
        try:
            await bot.send_message(m["tg_id"], text)
            count += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {m['tg_id']}: {e}")

    await message.answer(t("ru", "broadcast_done", count=count))


# ─── ADMIN NOTES ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:notes:"))
async def cb_adm_notes(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return

    model_tg_id = int(callback.data.split(":")[2])
    notes = await db.get_admin_notes(model_tg_id)

    if notes:
        lines = [t("ru", "status_history_title").replace("📋", "📝").replace("История статусов", "Заметки")]
        for n in notes:
            dt = n.get("created_at", "")[:16]
            lines.append(f"• [{dt}] {n['note']}")
        text = "\n".join(lines)
    else:
        text = t("ru", "notes_empty")

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить заметку", callback_data=f"adm:addnote:{model_tg_id}")
    builder.button(text="◀️ Назад", callback_data=f"adm:view:{model_tg_id}:all:0")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm:addnote:"))
async def cb_adm_addnote(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return

    model_tg_id = int(callback.data.split(":")[2])
    await state.set_state(NoteState.enter)
    await state.update_data(note_target_tg_id=model_tg_id)
    await callback.message.answer("✏️ Введите текст заметки:")
    await callback.answer()


@router.message(NoteState.enter)
async def note_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return

    data = await state.get_data()
    model_tg_id = data.get("note_target_tg_id")
    note_text = message.text or ""

    if model_tg_id and note_text:
        await db.add_admin_note(model_tg_id, note_text)

    await state.clear()
    await message.answer(t("ru", "note_added"))


# ─── STATUS HISTORY ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:history:"))
async def cb_adm_history(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔")
        return

    model_tg_id = int(callback.data.split(":")[2])
    history = await db.get_status_history(model_tg_id, limit=10)

    lines = [t("ru", "status_history_title")]
    if history:
        for h in history:
            dt = (h.get("changed_at") or "")[:16]
            old_s = h.get("old_status") or "—"
            new_s = h.get("new_status") or "—"
            lines.append(f"• [{dt}] {old_s} → {new_s}")
    else:
        lines.append("История пуста.")

    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data=f"adm:view:{model_tg_id}:all:0")

    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer("\n".join(lines), reply_markup=builder.as_markup())
    await callback.answer()
