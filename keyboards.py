from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from translations import t, ts
from config import CHANNEL_LINK, WEBSITE_LINK, WEBAPP_URL, ADMIN_CHAT_ID


# ─── LANGUAGE ────────────────────────────────────────────────────────────────

def lang_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    builder.button(text="🇬🇧 English", callback_data="lang:en")
    builder.adjust(2)
    return builder.as_markup()


# ─── START / WELCOME ─────────────────────────────────────────────────────────

def start_form_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "start_form"), callback_data="form:start")
    return builder.as_markup()


# ─── FORM NAVIGATION ─────────────────────────────────────────────────────────

def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn_back"), callback_data="form:back")
    return builder.as_markup()


# ─── MAIN MENU ───────────────────────────────────────────────────────────────

def main_menu(lang: str, tg_id: int) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=t(lang, "btn_profile"))
    builder.button(text=t(lang, "btn_referrals"))
    builder.button(text=t(lang, "btn_bonus"))
    builder.button(text=t(lang, "btn_channel"))
    builder.button(text="📱 Личный кабинет")
    builder.button(text=t(lang, "btn_lang"))
    builder.button(text=t(lang, "btn_write_manager"))
    if tg_id == ADMIN_CHAT_ID:
        builder.button(text=t(lang, "btn_admin"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def webapp_inline_keyboard(signed_url: str) -> InlineKeyboardMarkup:
    """Inline-кнопка открывающая Mini App с подписанной ссылкой."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Открыть кабинет", web_app=WebAppInfo(url=signed_url))
    return builder.as_markup()


# ─── PROFILE ─────────────────────────────────────────────────────────────────

ANKETA_FIELDS = [
    "full_name", "height", "weight", "phone_model",
    "socials", "location", "limits", "desired_income",
    "experience", "goals", "photo_file_id"
]


def profile_edit_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    field_names = ts(lang, "field_names")
    for field in ANKETA_FIELDS:
        builder.button(
            text=f"✏️ {field_names.get(field, field)}",
            callback_data=f"edit:{field}"
        )
    builder.adjust(2)
    return builder.as_markup()


def cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn_cancel"), callback_data="edit:cancel")
    return builder.as_markup()


# ─── CHANNEL / WEBSITE ───────────────────────────────────────────────────────

def channel_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn_channel"), url=CHANNEL_LINK)
    return builder.as_markup()


def website_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn_website"), url=WEBSITE_LINK)
    return builder.as_markup()


def webapp_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Открыть кабинет", web_app=WebAppInfo(url=WEBAPP_URL))
    return builder.as_markup()


# ─── MANAGER ─────────────────────────────────────────────────────────────────

def manager_keyboard(lang: str, manager_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t(lang, "btn_write_manager"),
        url=f"https://t.me/{manager_username}"
    )
    return builder.as_markup()


# ─── ADMIN ───────────────────────────────────────────────────────────────────

def admin_main_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика",      callback_data="adm:stats")
    builder.button(text="💰 Заработок",       callback_data="adm:earnings")
    builder.button(text="🆕 Новые заявки",    callback_data="adm:list:reviewing:0")
    builder.button(text="📋 Все модели",      callback_data="adm:list:all:0")
    builder.button(text="✅ Одобренные",      callback_data="adm:list:approved:0")
    builder.button(text="🟢 Активные",        callback_data="adm:list:active:0")
    builder.adjust(2, 1, 1, 1, 1)
    return builder.as_markup()


def admin_model_keyboard(tg_id: int, status: str, list_status: str, offset: int, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    action_count = 0
    # Show Approve for new/filling/reviewing/rejected (not already approved or active)
    if status in ("new", "filling", "reviewing", "rejected"):
        builder.button(text=t(lang, "btn_approve"),  callback_data=f"adm:set:{tg_id}:approved")
        action_count += 1
    # Show Activate only for approved models
    if status == "approved":
        builder.button(text=t(lang, "btn_activate"), callback_data=f"adm:set:{tg_id}:active")
        action_count += 1
    # Show Reject for everyone except already rejected
    if status != "rejected":
        builder.button(text=t(lang, "btn_reject"),   callback_data=f"adm:set:{tg_id}:rejected")
        action_count += 1
    builder.button(text=t(lang, "btn_back_list"),  callback_data=f"adm:list:{list_status}:{offset}")
    builder.button(text=t(lang, "btn_back_admin"), callback_data="adm:home")
    builder.button(text="📝 Заметки",   callback_data=f"adm:notes:{tg_id}")
    builder.button(text="📋 История",   callback_data=f"adm:history:{tg_id}")
    builder.adjust(action_count if action_count > 0 else 1, 1, 1, 2)
    return builder.as_markup()


def admin_list_keyboard(
    models: list,
    status_filter: str,
    offset: int,
    total: int,
    page_size: int = 5,
    lang: str = "ru"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in models:
        name = m.get("full_name") or m.get("tg_username") or str(m["tg_id"])
        label = f"👤 {name} — {m['status']}"
        builder.button(
            text=label,
            callback_data=f"adm:view:{m['tg_id']}:{status_filter}:{offset}"
        )
    # pagination
    row = []
    if offset > 0:
        row.append(InlineKeyboardButton(
            text=t(lang, "btn_prev"),
            callback_data=f"adm:list:{status_filter}:{offset - page_size}"
        ))
    if offset + page_size < total:
        row.append(InlineKeyboardButton(
            text=t(lang, "btn_next"),
            callback_data=f"adm:list:{status_filter}:{offset + page_size}"
        ))
    builder.adjust(1)
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(
        text=t(lang, "btn_back_admin"),
        callback_data="adm:home"
    ))
    return builder.as_markup()
