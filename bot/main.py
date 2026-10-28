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
from aiogram.types import BotCommand

from bot.handlers import start, payment_flow, status, cancel, admin, sponsor, fallback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _get_storage():
    """
    Try Redis first; fall back to MemoryStorage if the URL is unset or
    the server is unreachable.  from_url() is lazy, so we ping explicitly.
    """
    if not settings.REDIS_URL:
        logger.info("REDIS_URL not set — using MemoryStorage")
        return MemoryStorage()
    try:
        import redis.asyncio as aioredis
        from aiogram.fsm.storage.redis import RedisStorage
        client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await client.ping()
        await client.aclose()
        logger.info("Using Redis FSM storage: %s", settings.REDIS_URL)
        return RedisStorage.from_url(settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — falling back to MemoryStorage", exc)
        return MemoryStorage()


DESCRIPTION = (
    "Sahifalab to'lov boti: kurslar, Sahifalab Pro va SAHIFALAB homiylari "
    "yopiq kanali uchun to'lovlar.\n\n"
    "Boshlash uchun pastdagi «START» tugmasini bosing 👇"
)
SHORT_DESCRIPTION = "Sahifalab kurslari, Pro va homiylar kanali uchun to'lovlar"


async def _setup_profile(bot: Bot) -> None:
    """The ☰ Menu commands, and the text shown above START in an empty chat
    (only when none is set, so one written in BotFather is kept)."""
    commands = [BotCommand(command="start", description="Botni ishga tushirish")]
    if settings.SPONSOR_CHANNEL_ID:
        commands.append(BotCommand(command="homiy", description="SAHIFALAB homiylari yopiq kanali"))
    commands += [
        BotCommand(command="status", description="Mening so'rovlarim"),
        BotCommand(command="cancel", description="So'rovni bekor qilish"),
        BotCommand(command="help", description="Yordam"),
    ]
    try:
        await bot.set_my_commands(commands)
        if not (await bot.get_my_description()).description:
            await bot.set_my_description(DESCRIPTION)
        if not (await bot.get_my_short_description()).short_description:
            await bot.set_my_short_description(SHORT_DESCRIPTION)
    except Exception as exc:
        logger.warning("Bot profile setup failed: %s", exc)


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

    dp = Dispatcher(storage=await _get_storage())

    # Middleware
    dp.message.middleware(ThrottlingMiddleware(rate=1.0, burst=5))
    dp.message.middleware(AuditLoggingMiddleware())
    dp.callback_query.middleware(AuditLoggingMiddleware())

    # Routers (order matters — specific before generic)
    dp.include_router(admin.router)
    dp.include_router(sponsor.router)  # before start: it owns /start homiy
    dp.include_router(start.router)
    dp.include_router(status.router)
    dp.include_router(cancel.router)
    dp.include_router(payment_flow.router)
    dp.include_router(fallback.router)  # last: anything nothing else handled

    await _setup_profile(bot)

    logger.info("API_BASE_URL resolved to: %r", settings.API_BASE_URL)
    logger.info("Starting Sahifalab Payment Bot (polling)...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
