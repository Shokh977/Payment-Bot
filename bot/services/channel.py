"""
Invites to the private channel "SAHIFALAB homiylari".

A bot can't add someone to a channel, so a paid buyer gets their own
join-request link. Anyone can open it, but the bot approves the request only
from a Telegram account with granted access (sponsor.on_join_request), so a
forwarded link is useless. The link is revoked once it has been used.
"""
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot

from bot.config import settings
from bot.keyboards import inline

logger = logging.getLogger(__name__)

LINK_PREFIX = "homiy"
LINK_TTL = timedelta(days=7)
MEMBER_STATUSES = {"member", "administrator", "creator"}


async def is_member(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(settings.SPONSOR_CHANNEL_ID, user_id)
    except Exception:
        return False
    return member.status in MEMBER_STATUSES


async def send_invite(bot: Bot, user_id: int) -> None:
    """DM the user a fresh join-request link. Raises if Telegram refuses
    (bot not a channel admin, or the user blocked the bot)."""
    if await is_member(bot, user_id):
        await bot.send_message(user_id, "✅ Siz allaqachon <b>SAHIFALAB homiylari</b> kanalidasiz.")
        return

    link = await bot.create_chat_invite_link(
        settings.SPONSOR_CHANNEL_ID,
        name=f"{LINK_PREFIX} {user_id}",
        expire_date=datetime.now(timezone.utc) + LINK_TTL,
        creates_join_request=True,
    )
    await bot.send_message(
        user_id,
        "🔒 <b>SAHIFALAB homiylari</b> kanaliga taklif\n\n"
        "Pastdagi tugmani bosing va «Qo'shilish so'rovi»ni yuboring — "
        "bot sizni darhol qabul qiladi.\n\n"
        "⚠️ Havola faqat siz uchun: boshqa odam u orqali kira olmaydi. "
        "7 kun amal qiladi.",
        reply_markup=inline.channel_invite_kb(link.invite_link),
    )


async def revoke(bot: Bot, invite_link: str) -> None:
    try:
        await bot.revoke_chat_invite_link(settings.SPONSOR_CHANNEL_ID, invite_link)
    except Exception as exc:
        logger.warning("revoke invite link failed: %s", exc)
