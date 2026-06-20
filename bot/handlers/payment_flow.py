"""
Core payment flow: reference code → payment instructions → screenshot → admin notify.
"""
import re
import logging
from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import httpx

from bot.config import settings
from bot.states.payment import PaymentStates
from bot.services import api_client, storage
from bot.keyboards import inline

logger = logging.getLogger(__name__)

router = Router()

CODE_PATTERN = re.compile(r"^PAY-[A-Z0-9]{4}-[A-Z0-9]{4}$", re.IGNORECASE)

PAYMENT_METHOD_LABELS = {
    "click_card": "Click karta o'tkazma",
    "payme_card": "Payme karta o'tkazma",
    "uzcard":     "Uzcard",
    "humo":       "Humo",
    "other":      "Boshqa",
}


def _fmt_money(tiyin: int) -> str:
    som = tiyin // 100
    return f"{som:,} so'm".replace(",", " ")


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
    except Exception:
        await wait_msg.delete()
        await message.answer("⚠️ Ulanishda xato. Iltimos, birozdan keyin urinib ko'ring.")
        return

    await wait_msg.delete()

    amount_str = _fmt_money(enrollment["expected_amount"])
    card_num   = settings.PAYMENT_CARD_NUMBER or "—"
    card_holder = settings.PAYMENT_CARD_HOLDER

    text = (
        f"✅ <b>Kod tasdiqlandi!</b>\n\n"
        f"📚 Kurs: <b>{enrollment['course_title']}</b>\n"
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

    await state.update_data(
        enrollment_id=enrollment["id"],
        expected_amount=enrollment["expected_amount"],
        course_title=enrollment["course_title"],
        user_name=enrollment["user_name"],
        user_id=enrollment["user_id"],
    )
    await state.set_state(PaymentStates.waiting_for_screenshot)

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=inline.payment_instructions_kb(enrollment["id"], card_num),
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
        if settings.BUNNY_STORAGE_ZONE and settings.BUNNY_API_KEY and settings.BUNNY_CDN_URL:
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

    await message.answer(
        "✅ <b>Screenshot saqlandi!</b>\n\n"
        "To'lovingiz tekshirilmoqda. Tasdiqlanishi bilan "
        "Sahifalab ilovasiga bildirishnoma keladi va kurs ochiladi.\n\n"
        "⏳ Odatda 5–30 daqiqa kutiladi.\n\n"
        f"Tezroq bo'lishi uchun: {settings.SUPPORT_USERNAME} ga screenshot "
        "yuborib, kodingizni yozing.",
        parse_mode="HTML",
    )

    # Notify admins
    course_title = data.get("course_title", "—")
    user_name    = data.get("user_name", "—")
    exp_amount   = data.get("expected_amount", 0)
    ref_code     = data.get("reference_code", f"#{enrollment_id}")

    admin_text = (
        f"🔔 <b>YANGI TO'LOV TASDIQLASH KERAK</b>\n\n"
        f"📋 Kod: <code>{ref_code}</code>\n"
        f"👤 Foydalanuvchi: {user_name}\n"
        f"📚 Kurs: {course_title}\n"
        f"💰 Kutilgan summa: {_fmt_money(exp_amount)}\n"
        f"🕐 Yuborildi: hozirgina\n\n"
        f"📸 Screenshot pastda ↓"
    )

    admin_url = f"https://sahifalab.uz/admin"
    admin_kb  = inline.admin_notification_kb(enrollment_id, admin_url)

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


# ── Admin approval callbacks ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_approve:"))
async def cb_admin_approve(callback: CallbackQuery, state: FSMContext):
    enrollment_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.answer(
        "To'lov usulini tanlang:",
        reply_markup=inline.payment_method_kb(enrollment_id),
    )
    await state.update_data(enrollment_id=enrollment_id)
    from bot.states.payment import AdminApprovalStates
    await state.set_state(AdminApprovalStates.selecting_payment_method)


@router.callback_query(F.data.startswith("pm:"))
async def cb_payment_method(callback: CallbackQuery, state: FSMContext):
    _, enrollment_id_str, method = callback.data.split(":", 2)
    enrollment_id = int(enrollment_id_str)
    await callback.answer()

    data = await state.get_data()
    expected = data.get("expected_amount", 0)

    await callback.message.answer(
        f"Haqiqiy to'langan summa kutilgan summa bilan bir xilmi?\n"
        f"Kutilgan: <b>{_fmt_money(expected)}</b>",
        parse_mode="HTML",
        reply_markup=inline.amount_confirm_kb(enrollment_id, expected, method),
    )
    from bot.states.payment import AdminApprovalStates
    await state.set_state(AdminApprovalStates.confirming_amount)


@router.callback_query(F.data.startswith("amt_ok:"))
async def cb_amount_ok(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")  # amt_ok:id:method:amount
    enrollment_id = int(parts[1])
    method        = parts[2]
    amount        = int(parts[3])
    await callback.answer()

    data = await state.get_data()
    course = data.get("course_title", f"#{enrollment_id}")
    user   = data.get("user_name", "—")

    await callback.message.answer(
        f"<b>Tasdiqlash:</b>\n"
        f"• Kurs: {course}\n"
        f"• Foydalanuvchi: {user}\n"
        f"• To'lov: {PAYMENT_METHOD_LABELS.get(method, method)}\n"
        f"• Summa: <b>{_fmt_money(amount)}</b>\n\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=inline.final_confirm_kb(enrollment_id, method, amount),
    )
    from bot.states.payment import AdminApprovalStates
    await state.set_state(AdminApprovalStates.final_confirmation)


@router.callback_query(F.data.startswith("amt_custom:"))
async def cb_amount_custom(callback: CallbackQuery, state: FSMContext):
    _, enrollment_id_str, method = callback.data.split(":", 2)
    await callback.answer()
    await callback.message.answer("Haqiqiy to'langan summani kiriting (so'mda):")
    from bot.states.payment import AdminApprovalStates
    await state.update_data(enrollment_id=int(enrollment_id_str), pending_method=method)
    await state.set_state(AdminApprovalStates.entering_custom_amount)


@router.message(F.from_user, lambda m: True)
async def handle_custom_amount(message: Message, state: FSMContext):
    from bot.states.payment import AdminApprovalStates
    current = await state.get_state()
    if current != AdminApprovalStates.entering_custom_amount:
        return

    try:
        amount_som = int(message.text.strip().replace(" ", "").replace(",", ""))
        amount_tiyin = amount_som * 100
    except ValueError:
        await message.answer("Faqat son kiriting (masalan: 100000)")
        return

    data = await state.get_data()
    enrollment_id = data["enrollment_id"]
    method        = data["pending_method"]
    course        = data.get("course_title", f"#{enrollment_id}")
    user          = data.get("user_name", "—")

    await message.answer(
        f"<b>Tasdiqlash:</b>\n"
        f"• Kurs: {course}\n"
        f"• Foydalanuvchi: {user}\n"
        f"• To'lov: {PAYMENT_METHOD_LABELS.get(method, method)}\n"
        f"• Summa: <b>{_fmt_money(amount_tiyin)}</b>\n\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=inline.final_confirm_kb(enrollment_id, method, amount_tiyin),
    )
    await state.set_state(AdminApprovalStates.final_confirmation)


@router.callback_query(F.data.startswith("grant_ok:"))
async def cb_grant_ok(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":")  # grant_ok:id:method:amount
    enrollment_id = int(parts[1])
    method        = parts[2]
    amount        = int(parts[3])
    await callback.answer("Ishlanmoqda...")

    try:
        await api_client.grant_enrollment(enrollment_id, amount, method)
    except Exception as exc:
        await callback.message.answer(f"❌ Xato: {exc}")
        return

    await callback.message.answer("✅ Kurs ochildi va foydalanuvchiga bildirishnoma yuborildi.")
    await state.clear()

    # Notify the user
    data = await state.get_data()
    user_tg_id = data.get("user_id")
    course     = data.get("course_title", "")
    if user_tg_id:
        try:
            await bot.send_message(
                user_tg_id,
                f"🎉 <b>TABRIKLAYMIZ!</b>\n\n"
                f"To'lov tasdiqlandi va kurs sizga ochildi.\n\n"
                f"📚 <b>{course}</b>\n\n"
                f"Sahifalab ilovasini oching va o'rganishni boshlang!",
                parse_mode="HTML",
                reply_markup=inline.open_app_kb(),
            )
        except Exception as exc:
            logger.warning("Failed to notify user %s: %s", user_tg_id, exc)


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
    from bot.states.payment import AdminApprovalStates
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
        from bot.states.payment import AdminApprovalStates
        await state.set_state(AdminApprovalStates.entering_custom_reason)
        return

    reason_text = REJECT_LABELS.get(reason_key, reason_key)
    await _do_reject(callback, state, bot, enrollment_id, reason_text)


async def _do_reject(callback_or_msg, state, bot, enrollment_id: int, reason: str):
    try:
        await api_client.cancel_enrollment(enrollment_id, reason)
    except Exception as exc:
        await callback_or_msg.answer(f"❌ Xato: {exc}")
        return

    await callback_or_msg.answer("✅ So'rov bekor qilindi.")
    await state.clear()

    data = await state.get_data()
    user_tg_id = data.get("user_id")
    if user_tg_id:
        try:
            await bot.send_message(
                user_tg_id,
                "❌ <b>To'lov tasdiqlanmadi.</b>\n\n"
                f"Sabab: {reason}\n\n"
                "Iltimos, qaytadan urinib ko'ring yoki "
                f"{settings.SUPPORT_USERNAME} kanaliga yozing.\n\n"
                "Sahifalab ilovasidan yangi kod oling.",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Failed to notify user %s: %s", user_tg_id, exc)
