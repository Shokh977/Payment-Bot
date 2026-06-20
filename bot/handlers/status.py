from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.services import api_client
from bot.keyboards.inline import status_item_kb

router = Router()

STATUS_EMOJI = {
    "awaiting_payment": "🟡",
    "paid":             "📸",
    "granted":          "✅",
    "cancelled":        "❌",
    "expired":          "⏰",
}
STATUS_LABEL = {
    "awaiting_payment": "Screenshot kutilmoqda",
    "paid":             "Tasdiqlash kutilmoqda",
    "granted":          "Kurs ochildi",
    "cancelled":        "Bekor qilindi",
    "expired":          "Muddati tugagan",
}


def _fmt_money(tiyin: int) -> str:
    return f"{tiyin // 100:,} so'm".replace(",", " ")


@router.message(Command("status"))
async def cmd_status(message: Message):
    user_id = message.from_user.id
    wait = await message.answer("🔍 Yuklanmoqda...")

    try:
        items = await api_client.get_user_enrollments(user_id)
    except Exception:
        await wait.delete()
        await message.answer("⚠️ Ma'lumot olishda xato. Keyinroq urinib ko'ring.")
        return

    await wait.delete()

    if not items:
        await message.answer(
            "Sizda faol to'lov so'rovlari yo'q.\n\n"
            "Yangi kurs sotib olish uchun Sahifalab ilovasini oching."
        )
        return

    await message.answer(f"📋 <b>Sizning so'rovlaringiz ({len(items)} ta):</b>", parse_mode="HTML")

    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for i, item in enumerate(items[:5]):
        em    = STATUS_EMOJI.get(item["status"], "❓")
        label = STATUS_LABEL.get(item["status"], item["status"])
        code  = item.get("reference_code", "—")
        title = item.get("course", {}).get("title") if item.get("course") else f"Kurs #{item['course_id']}"
        price = _fmt_money(item.get("expected_amount", 0))

        text = (
            f"{num_emojis[i]} <code>{code}</code>\n"
            f"   📚 {title}\n"
            f"   💰 {price}\n"
            f"   {em} Holati: {label}"
        )

        kb = status_item_kb(item["id"]) if item["status"] == "awaiting_payment" else None
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
