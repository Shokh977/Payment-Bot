"""Bot entry point."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.middleware.throttling import ThrottlingMiddleware
from bot.middleware.logging import AuditLoggingMiddleware
from bot.handlers import start, payment_flow, status, cancel, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _get_storage():
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(settings.REDIS_URL)
        logger.info("Using Redis FSM storage: %s", settings.REDIS_URL)
        return storage
    except Exception as exc:
        logger.warning("Redis unavailable (%s), falling back to MemoryStorage", exc)
        return MemoryStorage()


async def main():
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Set it in .env and restart.")
        sys.exit(1)
    if not settings.BOT_SECRET:
        logger.warning("PAYMENT_BOT_SECRET is not set — API calls will fail auth.")
    if not settings.PAYMENT_CARD_NUMBER:
        logger.warning("PAYMENT_CARD_NUMBER is not set — users won't see card details.")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=_get_storage())

    # Middleware
    dp.message.middleware(ThrottlingMiddleware(rate=1.0, burst=5))
    dp.message.middleware(AuditLoggingMiddleware())
    dp.callback_query.middleware(AuditLoggingMiddleware())

    # Routers (order matters — specific before generic)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(status.router)
    dp.include_router(cancel.router)
    dp.include_router(payment_flow.router)

    logger.info("Starting Sahifalab Payment Bot (polling)...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
