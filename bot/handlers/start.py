from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from bot.config import settings
from bot.keyboards.inline import BTN_HELP, main_reply_kb

router = Router()


async def send_welcome(message: Message) -> None:
    """The greeting, with the buttons under the input field."""
    channel_line = (
        "🔒 <b>SAHIFALAB homiylari</b> yopiq kanaliga qo'shilish uchun "
        "pastdagi «🔒 Homiylar kanali» tugmasini bosing.\n\n"
        if settings.SPONSOR_CHANNEL_ID else ""
    )
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Men <b>Sahifalab to'lov botiman</b>.\n"
        "Kurslar va Sahifalab Pro uchun to'lovlarni shu yerda qabul qilaman.\n\n"
        f"{channel_line}"
        "📋 <b>Kurs yoki Pro uchun:</b>\n"
        f"1. <a href=\"{settings.APP_DEEP_LINK}\">Sahifalab ilovasida</a> kurs yoki Pro tanlang\n"
        "2. \"Sotib olish\" tugmasini bosing\n"
        "3. To'lov kodingizni shu yerga yuboring\n"
        "   (masalan: <code>PAY-A3F2-B5C1</code>)\n\n"
        f"✉️ Yordam kerakmi? {settings.SUPPORT_USERNAME} kanaliga yozing.",
        reply_markup=main_reply_kb(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    await send_welcome(message)


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message):
    await message.answer(
        "🤖 <b>Sahifalab To'lov Boti — Yordam</b>\n\n"
        "📌 <b>Asosiy buyruqlar:</b>\n"
        "/start — Botni qayta ishga tushirish\n"
        "/status — Mening so'rovlarim\n"
        "/cancel — So'rovni bekor qilish\n"
        "/homiy — SAHIFALAB homiylari yopiq kanali\n"
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
