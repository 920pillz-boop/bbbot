import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from handlers import router
from handlers_earnings import router as earnings_router
from web_server import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

    # Запускаем веб-сервер для Mini App (параллельно с ботом)
    web_runner = await start_web_server(bot=bot)

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await web_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
