"""
Core payment flow: reference code → payment instructions → screenshot → admin notify.
"""
import html
import re
import logging
from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import httpx

from bot.config import settings
from bot.states.payment import AdminApprovalStates, PaymentStates
from bot.services import api_client, channel, storage
from bot.keyboards import inline

logger = logging.getLogger(__name__)

router = Router()

CODE_PATTERN = re.compile(r"^PAY-[A-Z0-9]{4}-[A-Z0-9]{4}$", re.IGNORECASE)

def _fmt_money(amount: int) -> str:
    return f"{amount:,} so'm".replace(",", " ")


def _item_line(product: str | None, title: str) -> str:
    """'📚 Kurs: …' for a course, '✨ Pro: …' for a Pro pass, '🔒 Kanal: …' for the private channel."""
    if product == "pro":
        return f"✨ Pro: <b>{title}</b>"
    if product == "channel":
        return f"🔒 Kanal: <b>{title}</b>"
    return f"📚 Kurs: <b>{title}</b>"


def instructions_text(enrollment: dict, heading: str = "✅ <b>Kod tasdiqlandi!</b>") -> str:
    """The item, the amount and the card to pay to."""
    amount_str  = _fmt_money(enrollment["expected_amount"])
    card_num    = settings.PAYMENT_CARD_NUMBER or "—"
    card_holder = settings.PAYMENT_CARD_HOLDER
    return (
        f"{heading}\n\n"
        f"{_item_line(enrollment.get('product'), enrollment['course_title'])}\n"
        f"👤 Foydalanuvchi: <b>{enrollment['user_name']}</b>"
        + (f" (@{enrollment['user_username']})" if enrollment.get("user_username") else "")
        + f"\n💰 To'lov summasi: <b>{amount_str}</b>\n\n"
        f"{'━' * 22}\n"
        f"💳 <b>KARTA ORQALI TO'LOV</b>\n"
        f"{'━' * 22}\n\n"
        f"Karta raqami:\n"
        f"<b><code>{card_num}</code></b>\n\n"
        f"Karta egasi:\n"
        f"<b>{card_holder}</b>\n\n"
        f"To'lov turi: Click yoki Payme orqali karta o'tkazma\n\n"
        f"{'━' * 22}\n\n"
        f"⚠️ <b>MUHIM:</b>\n"
        f"• Aniq summa to'lang: <b>{amount_str}</b>\n"
        f"• To'lov izohiga hech narsa yozmang\n\n"
        f"{'━' * 22}\n\n"
        f"📸 To'lovni qilgach, <b>screenshot yuboring</b>.\n"
        f"Tasdiqlash 5–30 daqiqada amalga oshiriladi."
    )


async def await_screenshot(state: FSMContext, enrollment: dict) -> None:
    """Remember the request in the buyer's chat and wait for the receipt."""
    await state.update_data(
        enrollment_id=enrollment["id"],
        expected_amount=enrollment["expected_amount"],
        course_title=enrollment["course_title"],
        product=enrollment.get("product", "course"),
        user_name=enrollment["user_name"],
        user_username=enrollment.get("user_username", ""),
        reference_code=enrollment.get("reference_code", ""),
        user_id=enrollment["user_id"],
    )
    await state.set_state(PaymentStates.waiting_for_screenshot)


# ── Reference code handler ─────────────────────────────────────────────────────

@router.message(F.text.regexp(r"(?i)^PAY-[A-Z0-9]{4}-[A-Z0-9]{4}$"))
async def handle_reference_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    wait_msg = await message.answer("🔍 Kod tekshirilmoqda...")

    try:
        enrollment = await api_client.get_enrollment_by_code(code)
    except httpx.HTTPStatusError as e:
        await wait_msg.delete()
        if e.response.status_code == 404:
            await message.answer(
                "❌ <b>Bu kod topilmadi.</b>\n\n"
                "Iltimos, tekshiring va qaytadan yuboring.\n"
                "Kod Sahifalab ilovasidan olinishi kerak.\n\n"
                "Format: <code>PAY-XXXX-YYYY</code>",
                parse_mode="HTML",
            )
        elif e.response.status_code == 410:
            detail = e.response.json().get("detail", "")
            if "expired" in detail.lower():
                await message.answer(
                    "⏰ <b>Bu kod muddati tugagan</b> (24 soat amal qiladi).\n\n"
                    "Sahifalab ilovasini oching va kursni qaytadan tanlang — "
                    "yangi kod beriladi.",
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    f"ℹ️ Bu kod faol emas. ({detail})\n\n"
                    "Sahifalab ilovasidan yangi kod oling.",
                    parse_mode="HTML",
                )
        else:
            await message.answer("⚠️ Server xatosi. Iltimos, birozdan keyin urinib ko'ring.")
        return
    except Exception as exc:
        logger.error("get_enrollment_by_code failed: %s: %s", type(exc).__name__, exc)
        await wait_msg.delete()
        await message.answer("⚠️ Ulanishda xato. Iltimos, birozdan keyin urinib ko'ring.")
        return

    await wait_msg.delete()

    await await_screenshot(state, enrollment)

    await message.answer(
        instructions_text(enrollment),
        parse_mode="HTML",
        reply_markup=inline.payment_instructions_kb(enrollment["id"], settings.PAYMENT_CARD_NUMBER or "—"),
    )


# ── Copy card number ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("copy_card:"))
async def cb_copy_card(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"<code>{settings.PAYMENT_CARD_NUMBER}</code>\n\n"
        "👆 Yuqoridagi raqamni bosib nusxalang.",
        parse_mode="HTML",
    )


# ── Screenshot handler ─────────────────────────────────────────────────────────

@router.message(PaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    enrollment_id = data.get("enrollment_id")
    if not enrollment_id:
        await message.answer("❌ Xato holat. /start bosing.")
        return

    ack = await message.answer("📸 Screenshot qabul qilindi!\n\nTekshirilmoqda... ⏳")

    # Download from Telegram (highest res)
    photo = message.photo[-1]
    file_id = photo.file_id

    proof_url: str | None = None
    try:
        if settings.BUNNY_STORAGE_ZONE and settings.BUNNY_API_KEY and settings.BUNNY_CDN_HOSTNAME:
            photo_bytes = await storage.download_telegram_photo(bot, file_id)
            ts = int(datetime.now(timezone.utc).timestamp())
            filename = f"{enrollment_id}_{ts}.jpg"
            proof_url = await storage.upload_screenshot(photo_bytes, filename)
    except Exception as exc:
        logger.warning("Screenshot upload failed: %s", exc)

    # Mark as paid
    try:
        await api_client.mark_enrollment_paid(
            enrollment_id,
            proof_url=proof_url,
            telegram_file_id=file_id if not proof_url else None,
        )
    except Exception as exc:
        logger.error("mark_enrollment_paid failed for %s: %s", enrollment_id, exc)
        await ack.delete()
        await message.answer("⚠️ Xato yuz berdi. Iltimos, admin bilan bog'laning: " + settings.SUPPORT_USERNAME)
        return

    await state.clear()
    await ack.delete()

    where = (
        "shu yerga kanalga kirish havolasi keladi."
        if data.get("product") == "channel"
        else "Sahifalab ilovasiga bildirishnoma keladi va xaridingiz ochiladi."
    )
    await message.answer(
        "✅ <b>Screenshot saqlandi!</b>\n\n"
        f"To'lovingiz tekshirilmoqda. Tasdiqlanishi bilan {where}\n\n"
        "⏳ Odatda 5–30 daqiqa kutiladi.\n\n"
        f"Tezroq bo'lishi uchun: {settings.SUPPORT_USERNAME} ga screenshot "
        "yuborib, kodingizni yozing.",
        parse_mode="HTML",
    )

    # Notify admins
    course_title  = data.get("course_title", "—")
    product       = data.get("product", "course")
    user_name     = data.get("user_name", "—")
    user_username = data.get("user_username", "")
    exp_amount    = data.get("expected_amount", 0)
    ref_code      = data.get("reference_code", f"#{enrollment_id}")

    user_display = user_name
    if user_username:
        user_display += f" (@{user_username})"

    admin_text = (
        f"🔔 <b>YANGI TO'LOV TASDIQLASH KERAK</b>\n\n"
        f"📋 Kod: <code>{ref_code}</code>\n"
        f"👤 Foydalanuvchi: {user_display}\n"
        f"{_item_line(product, course_title)}\n"
        f"💰 Kutilgan summa: {_fmt_money(exp_amount)}\n"
        f"🕐 Yuborildi: hozirgina\n\n"
        f"📸 Screenshot pastda ↓"
    )

    admin_url = f"https://sahifalab.uz/admin"
    admin_kb  = inline.admin_notification_kb(enrollment_id, admin_url, exp_amount)

    for admin_id in settings.ADMIN_TELEGRAM_IDS:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML", reply_markup=admin_kb)
            await bot.send_photo(admin_id, photo=file_id)
        except Exception as exc:
            logger.error("Failed to notify admin %s: %s", admin_id, exc)


@router.message(PaymentStates.waiting_for_screenshot)
async def handle_non_photo(message: Message):
    await message.answer(
        "📸 Iltimos, to'lov <b>screenshot'ini yuboring</b> (rasm sifatida).\n\n"
        "Agar to'lovni qilmadingiz va bekor qilmoqchi bo'lsangiz:\n/cancel",
        parse_mode="HTML",
    )


# ── Resend screenshot (from /status menu) ─────────────────────────────────────

@router.callback_query(F.data.startswith("resend_ss:"))
async def cb_resend_screenshot(callback: CallbackQuery, state: FSMContext):
    enrollment_id = int(callback.data.split(":")[1])
    await state.set_state(PaymentStates.waiting_for_screenshot)
    await state.update_data(enrollment_id=enrollment_id)
    await callback.answer()
    await callback.message.answer(
        "📸 Iltimos, to'lov <b>screenshot'ini yuboring</b> (rasm sifatida).\n\n"
        "To'lov tasdiqlanishi uchun to'liq summani ko'rsatadigan rasmni yuboring.",
        parse_mode="HTML",
    )


def _admin_error(exc: Exception) -> str:
    """A 400 means the request was already approved or rejected (e.g. on
    the web dashboard) — say so instead of showing the raw HTTP error."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
        return "ℹ️ Bu so'rov allaqachon ko'rib chiqilgan (tasdiqlangan yoki bekor qilingan)."
    return f"❌ Xato: {exc}"


# ── Admin approval callbacks ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_approve:"))
async def cb_admin_approve(callback: CallbackQuery):
    parts = callback.data.split(":")
    enrollment_id = int(parts[1])
    amount        = int(parts[2]) if len(parts) > 2 else 0
    await callback.answer()

    await callback.message.answer(
        f"To'lovni tasdiqlaysizmi?\n\n"
        f"💰 Summa: <b>{_fmt_money(amount)}</b>\n"
        f"📋 So'rov #{enrollment_id}",
        parse_mode="HTML",
        reply_markup=inline.admin_confirm_kb(enrollment_id, amount),
    )


@router.callback_query(F.data.startswith("grant_ok:"))
async def cb_grant_ok(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":")  # grant_ok:id:amount
    enrollment_id = int(parts[1])
    amount        = int(parts[2])
    await callback.answer("Ishlanmoqda...")

    # The buyer comes from the request itself: this is the admin's chat, so
    # its FSM state holds nothing about the buyer.
    try:
        pending = await api_client.get_enrollment(enrollment_id)
        await api_client.grant_enrollment(enrollment_id, amount, "card_transfer")
    except Exception as exc:
        await callback.message.answer(_admin_error(exc))
        return

    await state.clear()
    product = pending.get("product")

    if product != "channel":
        # The backend sends the buyer the in-app and Telegram notifications.
        await callback.message.answer(
            ("✅ Pro ochildi" if product == "pro" else "✅ Kurs ochildi") + " va foydalanuvchiga bildirishnoma yuborildi."
        )
        return

    user_tg_id = pending["user_id"]
    try:
        await channel.send_invite(bot, user_tg_id)
    except Exception as exc:
        logger.warning("Channel invite to %s failed: %s", user_tg_id, exc)
        await callback.message.answer(
            "✅ To'lov tasdiqlandi, lekin kanal havolasi yuborilmadi.\n\n"
            f"Sabab: {exc}\n\n"
            "Bot kanalda admin ekanini va «Invite users via link» huquqi borligini tekshiring.",
            reply_markup=inline.channel_resend_kb(user_tg_id),
        )
        return
    await callback.message.answer("✅ To'lov tasdiqlandi — foydalanuvchiga kanalga kirish havolasi yuborildi.")


@router.callback_query(F.data.startswith("grant_cancel:"))
async def cb_grant_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Bekor qilindi")
    await callback.message.answer("Tasdiqlash bekor qilindi.")
    await state.clear()


# ── Admin rejection callbacks ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_reject:"))
async def cb_admin_reject(callback: CallbackQuery, state: FSMContext):
    enrollment_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.answer(
        "Sababini tanlang:",
        reply_markup=inline.reject_reason_kb(enrollment_id),
    )
    await state.update_data(enrollment_id=enrollment_id)
    await state.set_state(AdminApprovalStates.selecting_reject_reason)


REJECT_LABELS = {
    "payment_not_found": "To'lov topilmadi",
    "wrong_amount":      "Noto'g'ri summa",
    "fake_screenshot":   "Soxta screenshot",
    "wrong_user":        "Noto'g'ri foydalanuvchi",
}


@router.callback_query(F.data.startswith("rej:"))
async def cb_reject_reason(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":", 2)
    enrollment_id = int(parts[1])
    reason_key    = parts[2]
    await callback.answer()

    if reason_key == "custom":
        await callback.message.answer("Sababini yozing:")
        await state.set_state(AdminApprovalStates.entering_custom_reason)
        return

    reason_text = REJECT_LABELS.get(reason_key, reason_key)
    await _do_reject(callback.message, state, bot, enrollment_id, reason_text)


@router.message(AdminApprovalStates.entering_custom_reason, F.text)
async def handle_custom_reason(message: Message, state: FSMContext, bot: Bot):
    enrollment_id = (await state.get_data()).get("enrollment_id")
    if not enrollment_id:
        await state.clear()
        await message.answer("❌ So'rov topilmadi. Bildirishnomadagi «Bekor qilish» tugmasini qayta bosing.")
        return
    await _do_reject(message, state, bot, int(enrollment_id), message.text.strip()[:300])


async def _do_reject(reply_to: Message, state: FSMContext, bot: Bot, enrollment_id: int, reason: str):
    # The buyer comes from the request, not from this (the admin's) FSM state.
    try:
        pending = await api_client.get_enrollment(enrollment_id)
        await api_client.cancel_enrollment(enrollment_id, reason)
    except Exception as exc:
        await state.clear()
        await reply_to.answer(_admin_error(exc))
        return

    await state.clear()
    await reply_to.answer("✅ So'rov bekor qilindi.")

    next_step = (
        "Qayta urinish uchun /homiy buyrug'ini yuboring."
        if pending.get("product") == "channel"
        else "Sahifalab ilovasidan yangi kod oling."
    )
    user_tg_id = pending.get("user_id")
    if user_tg_id:
        try:
            await bot.send_message(
                user_tg_id,
                "❌ <b>To'lov tasdiqlanmadi.</b>\n\n"
                f"Sabab: {html.escape(reason)}\n\n"
                "Iltimos, qaytadan urinib ko'ring yoki "
                f"{settings.SUPPORT_USERNAME} kanaliga yozing.\n\n"
                f"{next_step}",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Failed to notify user %s: %s", user_tg_id, exc)
