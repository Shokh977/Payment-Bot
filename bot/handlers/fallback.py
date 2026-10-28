"""Anything no other handler took (a random message, a photo sent before a
code): show the greeting and the buttons instead of staying silent."""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from bot.handlers.start import send_welcome

router = Router()


@router.message(StateFilter(None), F.chat.type == "private")
async def unknown_message(message: Message):
    await send_welcome(message)
