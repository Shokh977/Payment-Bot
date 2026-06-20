from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

REJECT_REASONS = [
    ("payment_not_found",  "📸 To'lov topilmadi"),
    ("wrong_amount",       "💰 Noto'g'ri summa"),
    ("fake_screenshot",    "🖼️ Soxta screenshot"),
    ("wrong_user",         "🤷 Noto'g'ri foydalanuvchi"),
    ("custom",             "📝 Boshqa sabab (yozish)"),
]


def payment_instructions_kb(enrollment_id: int, card_number: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Karta raqamini nusxalash", callback_data=f"copy_card:{enrollment_id}")
    b.button(text="❌ Bekor qilish",              callback_data=f"user_cancel:{enrollment_id}")
    b.adjust(1)
    return b.as_markup()


def admin_notification_kb(enrollment_id: int, admin_url: str, expected_amount: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash",          callback_data=f"admin_approve:{enrollment_id}:{expected_amount}")
    b.button(text="❌ Bekor qilish",        callback_data=f"admin_reject:{enrollment_id}")
    b.button(text="🌐 Admin panel",         url=admin_url)
    b.adjust(2, 1)
    return b.as_markup()


def admin_confirm_kb(enrollment_id: int, amount: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, kursni ochish", callback_data=f"grant_ok:{enrollment_id}:{amount}")
    b.button(text="❌ Yo'q, bekor",       callback_data=f"grant_cancel:{enrollment_id}")
    b.adjust(1)
    return b.as_markup()


def reject_reason_kb(enrollment_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in REJECT_REASONS:
        b.button(text=label, callback_data=f"rej:{enrollment_id}:{key}")
    b.adjust(1)
    return b.as_markup()


def user_cancel_confirm_kb(enrollment_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, bekor qilaman", callback_data=f"cancel_confirm:{enrollment_id}")
    b.button(text="🔙 Yo'q, orqaga",      callback_data="cancel_abort")
    b.adjust(2)
    return b.as_markup()


def status_item_kb(enrollment_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📤 Screenshotni yuborish", callback_data=f"resend_ss:{enrollment_id}")
    b.button(text="❌ Bekor qilish",           callback_data=f"user_cancel:{enrollment_id}")
    b.adjust(2)
    return b.as_markup()


def open_app_kb(course_slug: str = "") -> InlineKeyboardMarkup:
    from bot.config import settings
    b = InlineKeyboardBuilder()
    b.button(text="📱 Ilovani ochish", url=settings.APP_DEEP_LINK)
    b.adjust(1)
    return b.as_markup()
