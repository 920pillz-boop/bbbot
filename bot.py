import asyncio
import logging
import os
import time
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_CHAT_ID
from database import (
    init_db,
    get_all_active_models_for_summary,
    get_reviewing_users_older_than,
    get_monthly_total,
    get_monthly_ref_bonus_total,
    get_earnings_for_month,
)
from handlers import router
from handlers_earnings import router as earnings_router
from handlers_new import router as new_router
from web_server import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Tracking sets / timestamps ──────────────────────────────────────────────
_summary_sent_dates: set[str] = set()   # "YYYY-MM-DD:weekly" / "YYYY-MM-DD:monthly"
_reminder_last_sent: float = 0.0        # unix timestamp of last admin reminder


def get_proxy() -> str | None:
    """
    Читает прокси из переменных окружения.
    Приоритет: TELEGRAM_PROXY > ALL_PROXY > HTTPS_PROXY
    Поддерживает socks5://, socks4://, http://
    """
    for var in ("TELEGRAM_PROXY", "ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy"):
        val = os.getenv(var, "").strip()
        if val:
            logger.info(f"Proxy detected from {var}: {val}")
            return val
    return None


def _month_name(month: int, lang: str = "ru") -> str:
    names_ru = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    names_en = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    names = names_ru if lang == "ru" else names_en
    return names[month - 1]


# ─── BACKGROUND TASK: weekly/monthly summary ─────────────────────────────────

async def weekly_monthly_summary(bot: Bot):
    """
    Runs every hour.
    - Monday at 09:xx  → weekly earnings summary to all active models.
    - 1st of month at 09:xx → monthly earnings summary to all active models.
    Uses a set to prevent duplicate sends within the same day.
    """
    global _summary_sent_dates

    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            hour = now.hour
            weekday = now.weekday()   # 0 = Monday
            day = now.day
            year, month = now.year, now.month

            if hour == 9:
                # ── Weekly summary (Monday) ──────────────────────────────
                weekly_key = f"{today_str}:weekly"
                if weekday == 0 and weekly_key not in _summary_sent_dates:
                    _summary_sent_dates.add(weekly_key)
                    models = await get_all_active_models_for_summary()
                    for m in models:
                        tg_id = m["tg_id"]
                        lang = m.get("language", "ru")
                        try:
                            earnings = await get_earnings_for_month(tg_id, year, month)
                            week_start = f"{year}-{month:02d}-{max(1, now.day - 6):02d}"
                            week_total = sum(
                                e["amount"] for e in earnings
                                if e["date"] >= week_start
                            )
                            month_total = await get_monthly_total(tg_id, year, month)
                            from translations import t as tr
                            text = tr(
                                lang, "weekly_summary",
                                week_total=week_total,
                                month_total=month_total,
                                month_name=_month_name(month, lang)
                            )
                            await bot.send_message(tg_id, text)
                        except Exception as e:
                            logger.warning(f"Weekly summary failed for {tg_id}: {e}")

                # ── Monthly summary (1st of month) ───────────────────────
                monthly_key = f"{today_str}:monthly"
                if day == 1 and monthly_key not in _summary_sent_dates:
                    _summary_sent_dates.add(monthly_key)
                    # Report covers the previous month
                    if month == 1:
                        rep_month, rep_year = 12, year - 1
                    else:
                        rep_month, rep_year = month - 1, year

                    models = await get_all_active_models_for_summary()
                    for m in models:
                        tg_id = m["tg_id"]
                        lang = m.get("language", "ru")
                        try:
                            month_total = await get_monthly_total(tg_id, rep_year, rep_month)
                            ref_total = await get_monthly_ref_bonus_total(tg_id, rep_year, rep_month)
                            from translations import t as tr
                            text = tr(
                                lang, "monthly_summary",
                                month_total=month_total,
                                ref_total=ref_total,
                                month_name=_month_name(rep_month, lang)
                            )
                            await bot.send_message(tg_id, text)
                        except Exception as e:
                            logger.warning(f"Monthly summary failed for {tg_id}: {e}")

            # Purge stale keys (keep only entries for today to limit memory)
            _summary_sent_dates = {k for k in _summary_sent_dates if k.startswith(today_str)}

        except Exception as e:
            logger.error(f"weekly_monthly_summary error: {e}")

        await asyncio.sleep(3600)


# ─── BACKGROUND TASK: admin reminder ─────────────────────────────────────────

async def admin_reminder_task(bot: Bot):
    """
    Runs every hour.
    If there are 'reviewing' applications older than 24 hours,
    notifies ADMIN_CHAT_ID. Throttled to once per 6 hours.
    """
    global _reminder_last_sent

    while True:
        try:
            now_ts = time.time()
            # Throttle: at most once per 6 hours
            if now_ts - _reminder_last_sent >= 6 * 3600:
                stale_users = await get_reviewing_users_older_than(24)
                if stale_users:
                    count = len(stale_users)
                    from translations import t as tr
                    text = tr("ru", "admin_reminder", count=count)
                    try:
                        await bot.send_message(ADMIN_CHAT_ID, text)
                        _reminder_last_sent = now_ts
                        logger.info(f"Admin reminded: {count} stale reviewing applications")
                    except Exception as e:
                        logger.warning(f"Cannot send admin reminder: {e}")
        except Exception as e:
            logger.error(f"admin_reminder_task error: {e}")

        await asyncio.sleep(3600)


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def main():
    await init_db()

    proxy = get_proxy()

    if proxy:
        # AiohttpSession поддерживает socks5:// через aiohttp-socks
        session = AiohttpSession(proxy=proxy)
        bot = Bot(
            token=BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        logger.info(f"Bot starting with proxy: {proxy}")
    else:
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        logger.info("Bot starting without proxy")

    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(earnings_router)
    dp.include_router(new_router)

    # Запускаем веб-сервер для Mini App (параллельно с ботом)
    web_runner = await start_web_server(bot=bot)

    # Запускаем фоновые задачи
    asyncio.create_task(weekly_monthly_summary(bot))
    asyncio.create_task(admin_reminder_task(bot))

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
    finally:
        await web_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
