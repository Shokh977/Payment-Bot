from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Sahifalab ilovasini ochish", url=settings.APP_DEEP_LINK)

    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Men <b>Sahifalab to'lov botiman</b>.\n"
        "Kurslarni sotib olish va kirishni faollashtirish uchun shu yerdaman.\n\n"
        "📋 <b>Qanday ishlatish:</b>\n"
        "1. Sahifalab ilovasida kurs tanlang\n"
        "2. \"Sotib olish\" tugmasini bosing\n"
        "3. To'lov kodingizni shu yerga yuboring\n"
        "   (masalan: <code>PAY-A3F2-B5C1</code>)\n\n"
        "Boshlash uchun to'lov kodingizni yuboring.\n\n"
        f"✉️ Yordam kerakmi? {settings.SUPPORT_USERNAME} kanaliga yozing.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🤖 <b>Sahifalab To'lov Boti — Yordam</b>\n\n"
        "📌 <b>Asosiy buyruqlar:</b>\n"
        "/start — Botni qayta ishga tushirish\n"
        "/status — Mening so'rovlarim\n"
        "/cancel — So'rovni bekor qilish\n"
        "/help — Bu yordam\n\n"
        "📚 <b>Qanday kurs sotib olish:</b>\n"
        "1. Sahifalab ilovasini oching\n"
        "2. Kurs tanlang va \"Sotib olish\" bosing\n"
        "3. <code>PAY-XXXX-YYYY</code> kodini shu yerga yuboring\n"
        "4. Bot karta raqamini beradi\n"
        "5. Click/Payme orqali to'lang\n"
        "6. Screenshot yuboring\n"
        "7. 5–30 daqiqada kurs ochiladi\n\n"
        f"💬 <b>Boshqa savollar:</b>\n{settings.SUPPORT_USERNAME} kanaliga yozing\n\n"
        "🔒 <b>Xavfsizlik:</b>\n"
        "Faqat shu botda to'lov ko'rsatmalarini oling. "
        "Boshqa joydan \"sahifalab to'lovi\" deb kelgan xabarlarga ishonmang.",
        parse_mode="HTML",
    )
