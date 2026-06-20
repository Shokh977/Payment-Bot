"""Admin-only commands. Only work if sender's Telegram ID is in ADMIN_TELEGRAM_IDS."""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import settings
from bot.services import api_client
from bot.keyboards.inline import admin_notification_kb

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_TELEGRAM_IDS


def _fmt_money(tiyin: int) -> str:
    return f"{tiyin // 100:,} so'm".replace(",", " ")


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    if not _is_admin(message.from_user.id):
        return

    try:
        stats = await api_client.get_admin_stats()
    except Exception as exc:
        await message.answer(f"❌ Xato: {exc}")
        return

    await message.answer(
        f"📊 <b>Platforma statistikasi</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{stats.get('total_users', 0):,}</b>\n"
        f"📚 Jami kurslar: <b>{stats.get('total_courses', 0):,}</b>\n"
        f"🆕 Bugungi yangi foydalanuvchilar: <b>{stats.get('users_today', 0)}</b>\n"
        f"📝 Bugungi yangi yozilishlar: <b>{stats.get('enrollments_today', 0)}</b>\n"
        f"⏳ Kutilayotgan to'lovlar: <b>{stats.get('pending_payments', 0)}</b>\n\n"
        f"💰 Oylik daromad: <b>{_fmt_money(stats.get('monthly_revenue', 0))}</b>\n\n"
        f"🌐 To'liq statistika: sahifalab.uz/admin/stats",
        parse_mode="HTML",
    )


@router.message(Command("admin_pending"))
async def cmd_admin_pending(message: Message):
    if not _is_admin(message.from_user.id):
        return

    try:
        items = await api_client.get_pending_paid_enrollments()
    except Exception as exc:
        await message.answer(f"❌ Xato: {exc}")
        return

    if not items:
        await message.answer("✅ Tasdiqlanish kutilayotgan so'rovlar yo'q.")
        return

    await message.answer(f"⏳ <b>Tasdiqlanish kutilayotganlar ({len(items)} ta):</b>", parse_mode="HTML")

    for item in items[:10]:
        code  = item.get("reference_code", "—")
        user  = item.get("user", {}) or {}
        course = item.get("course", {}) or {}
        name   = user.get("first_name", f"#{item['user_id']}")
        uname  = f" (@{user['username']})" if user.get("username") else ""
        title  = course.get("title", f"Kurs #{item['course_id']}")
        price  = _fmt_money(item.get("expected_amount", 0))

        text = (
            f"📋 <code>{code}</code>\n"
            f"👤 {name}{uname}\n"
            f"📚 {title}\n"
            f"💰 {price}"
        )
        admin_url = f"https://sahifalab.uz/admin"
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_notification_kb(item["id"], admin_url),
        )


@router.message(Command("admin_user"))
async def cmd_admin_user(message: Message):
    if not _is_admin(message.from_user.id):
        return

    # Expect: /admin_user @username  or  /admin_user 123456789
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: /admin_user @username yoki /admin_user TELEGRAM_ID")
        return

    arg = parts[1].strip().lstrip("@")
    await message.answer(
        f"Foydalanuvchi ma'lumotlarini ko'rish uchun:\n"
        f"sahifalab.uz/admin → Foydalanuvchilar → {arg} bo'yicha qidiring",
        parse_mode="HTML",
    )
