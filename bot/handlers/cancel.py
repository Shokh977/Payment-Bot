from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.services import api_client
from bot.keyboards.inline import user_cancel_confirm_kb

router = Router()


def _fmt_money(tiyin: int) -> str:
    return f"{tiyin // 100:,} so'm".replace(",", " ")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    # Clear any in-progress FSM state first
    await state.clear()

    user_id = message.from_user.id
    try:
        items = await api_client.get_user_enrollments(user_id)
    except Exception:
        await message.answer("⚠️ Ma'lumot olishda xato. Keyinroq urinib ko'ring.")
        return

    active = [i for i in items if i["status"] in ("awaiting_payment", "paid")]
    if not active:
        await message.answer("Sizda bekor qilish uchun faol so'rov yo'q.")
        return

    if len(active) == 1:
        item = active[0]
        code  = item.get("reference_code", "—")
        title = item.get("course", {}).get("title", f"Kurs #{item['course_id']}")
        price = _fmt_money(item.get("expected_amount", 0))
        await message.answer(
            f"<b>So'rovni bekor qilish:</b>\n\n"
            f"📋 Kod: <code>{code}</code>\n"
            f"📚 {title}\n"
            f"💰 {price}\n\n"
            "Tasdiqlaysizmi?",
            parse_mode="HTML",
            reply_markup=user_cancel_confirm_kb(item["id"]),
        )
        return

    # Multiple active requests — show picker
    b = InlineKeyboardBuilder()
    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for i, item in enumerate(active[:5]):
        title = item.get("course", {}).get("title", f"Kurs #{item['course_id']}")
        price = _fmt_money(item.get("expected_amount", 0))
        b.button(text=f"{num_emojis[i]} {title} — {price}", callback_data=f"cancel_pick:{item['id']}")
    b.button(text="🔙 Bekor qilmaslik", callback_data="cancel_abort")
    b.adjust(1)

    await message.answer(
        "Bekor qilish uchun tanlang:",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data.startswith("cancel_pick:"))
async def cb_cancel_pick(callback: CallbackQuery):
    enrollment_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.answer(
        "Ushbu so'rovni bekor qilishni tasdiqlaysizmi?",
        reply_markup=user_cancel_confirm_kb(enrollment_id),
    )


@router.callback_query(F.data.startswith("cancel_confirm:"))
async def cb_cancel_confirm(callback: CallbackQuery):
    enrollment_id = int(callback.data.split(":")[1])
    await callback.answer("Bekor qilinmoqda...")
    try:
        await api_client.cancel_enrollment(enrollment_id, "Foydalanuvchi tomonidan bekor qilindi")
    except Exception as exc:
        await callback.message.answer(f"❌ Xato: {exc}")
        return
    await callback.message.answer(
        "✅ So'rov bekor qilindi.\n\n"
        "Yangi kurs sotib olish uchun Sahifalab ilovasini oching."
    )


@router.callback_query(F.data == "cancel_abort")
async def cb_cancel_abort(callback: CallbackQuery):
    await callback.answer("Yaxshi, o'zgarishsiz qoldi.")
    await callback.message.delete()


@router.callback_query(F.data.startswith("user_cancel:"))
async def cb_user_cancel_from_flow(callback: CallbackQuery):
    enrollment_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.answer(
        "Ushbu to'lov so'rovini bekor qilishni tasdiqlaysizmi?",
        reply_markup=user_cancel_confirm_kb(enrollment_id),
    )
