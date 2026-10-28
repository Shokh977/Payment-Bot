"""
Private channel "SAHIFALAB homiylari": one-time paid access.

  t.me/<bot>?start=homiy or /homiy → menu → card details → screenshot
  → admin approves (payment_flow.cb_grant_ok) → personal join-request link
  → on_join_request lets in only Telegram accounts with granted access.

Admins: /homiy_narx shows the price, /homiy_narx 60000 changes it.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatJoinRequest, Message

from bot.config import settings
from bot.handlers.payment_flow import _fmt_money, await_screenshot, instructions_text
from bot.keyboards import inline
from bot.services import api_client, channel

logger = logging.getLogger(__name__)

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_TELEGRAM_IDS


async def _show_menu(message: Message) -> None:
    if not settings.SPONSOR_CHANNEL_ID:
        await message.answer("Yopiq kanal hozircha mavjud emas.")
        return
    try:
        price = (await api_client.get_sponsor_config())["price"]
    except Exception as exc:
        logger.error("get_sponsor_config failed: %s", exc)
        await message.answer("⚠️ Ulanishda xato. Iltimos, birozdan keyin urinib ko'ring.")
        return
    await message.answer(
        "🔒 <b>SAHIFALAB homiylari</b> — yopiq kanal\n\n"
        "Faqat homiylar uchun maxsus kontent.\n\n"
        f"💰 Narxi: <b>{_fmt_money(price)}</b> — bir martalik to'lov, muddatsiz kirish.\n\n"
        "Qo'shilish uchun pastdagi tugmani bosing.",
        reply_markup=inline.sponsor_menu_kb(),
    )


@router.message(CommandStart(deep_link=True, magic=F.args == "homiy"))
async def start_homiy(message: Message, state: FSMContext):
    await state.clear()
    await _show_menu(message)


@router.message(Command("homiy"))
@router.message(F.text == inline.BTN_CHANNEL)
async def cmd_homiy(message: Message, state: FSMContext):
    await state.clear()
    await _show_menu(message)


@router.callback_query(F.data == "sponsor_menu")
async def cb_sponsor_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _show_menu(callback.message)


@router.callback_query(F.data == "sponsor_join")
async def cb_sponsor_join(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    user = callback.from_user
    try:
        request = await api_client.open_sponsor_request(user.id, user.first_name, user.username)
    except Exception as exc:
        logger.error("open_sponsor_request failed for %s: %s", user.id, exc)
        await callback.message.answer("⚠️ Ulanishda xato. Iltimos, birozdan keyin urinib ko'ring.")
        return

    if request["status"] == "granted":
        # Paid before (maybe left the channel since): a fresh link.
        try:
            await channel.send_invite(bot, user.id)
        except Exception as exc:
            logger.error("send_invite failed for %s: %s", user.id, exc)
            await callback.message.answer(
                f"⚠️ Havolani yaratib bo'lmadi. Iltimos, {settings.SUPPORT_USERNAME} ga yozing."
            )
        return

    if request["status"] == "paid":
        await callback.message.answer(
            "⏳ Screenshotingiz qabul qilingan va tekshirilmoqda.\n\n"
            "Tasdiqlanishi bilan shu yerga kanal havolasi keladi."
        )
        return

    await await_screenshot(state, request)
    await callback.message.answer(
        instructions_text(request, heading="🔒 <b>SAHIFALAB homiylari ga qo'shilish</b>"),
        reply_markup=inline.payment_instructions_kb(request["id"], settings.PAYMENT_CARD_NUMBER or "—"),
    )


@router.callback_query(F.data.startswith("sponsor_resend:"))
async def cb_sponsor_resend(callback: CallbackQuery, bot: Bot):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    user_id = int(callback.data.split(":")[1])
    try:
        await channel.send_invite(bot, user_id)
    except Exception as exc:
        await callback.answer()
        await callback.message.answer(f"❌ Yana yuborilmadi: {exc}")
        return
    await callback.answer("Yuborildi ✅")
    await callback.message.answer("✅ Kanal havolasi yuborildi.")


@router.chat_join_request(F.chat.id == settings.SPONSOR_CHANNEL_ID)
async def on_join_request(request: ChatJoinRequest, bot: Bot):
    """Approve only accounts that paid; the personal link is single-use."""
    user_id = request.from_user.id
    try:
        granted = await api_client.has_sponsor_access(user_id)
    except Exception as exc:
        # Leave the request pending: an admin can approve it by hand, and a
        # retry via /homiy sends a new link.
        logger.error("has_sponsor_access failed for %s: %s", user_id, exc)
        return

    link = request.invite_link
    if not granted:
        await request.decline()
        try:
            await bot.send_message(
                user_id,
                "🔒 <b>SAHIFALAB homiylari</b> — yopiq kanal.\n\n"
                "Kirish faqat to'lov qilganlar uchun. Qo'shilish uchun: /homiy",
            )
        except Exception:
            pass  # they may never have opened the bot
        return

    await request.approve()
    if link and (link.name or "").startswith(channel.LINK_PREFIX):
        await channel.revoke(bot, link.invite_link)
    try:
        await bot.send_message(user_id, "🎉 <b>Xush kelibsiz!</b> Siz endi SAHIFALAB homiylari kanalidasiz.")
    except Exception:
        pass


@router.message(Command("homiy_narx"))
async def cmd_homiy_price(message: Message, command: CommandObject):
    if not _is_admin(message.from_user.id):
        return

    arg = (command.args or "").replace(" ", "").replace("_", "")
    try:
        if not arg:
            config = await api_client.get_sponsor_config()
            await message.answer(
                f"🔒 Homiylar kanali narxi: <b>{_fmt_money(config['price'])}</b>\n\n"
                "O'zgartirish: <code>/homiy_narx 60000</code>"
            )
            return
        if not arg.isdigit():
            await message.answer("Narxni so'mda, faqat raqam bilan yozing: <code>/homiy_narx 60000</code>")
            return
        config = await api_client.set_sponsor_price(int(arg))
    except Exception as exc:
        await message.answer(f"❌ Xato: {exc}")
        return
    await message.answer(
        f"✅ Yangi narx: <b>{_fmt_money(config['price'])}</b>\n\n"
        "Hali to'lamaganlar uchun ham shu narx qo'llanadi."
    )
