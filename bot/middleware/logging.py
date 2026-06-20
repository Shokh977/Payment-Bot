"""Structured audit logging middleware."""
import logging
import time
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger("audit")


class AuditLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        start = time.monotonic()

        if isinstance(event, Message):
            user = event.from_user
            logger.info(
                "message",
                extra={
                    "user_id":   user.id if user else None,
                    "username":  user.username if user else None,
                    "text":      (event.text or "")[:120],
                    "has_photo": bool(event.photo),
                },
            )
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            logger.info(
                "callback",
                extra={
                    "user_id":  user.id if user else None,
                    "username": user.username if user else None,
                    "data":     event.data,
                },
            )

        result = await handler(event, data)

        elapsed = time.monotonic() - start
        if elapsed > 5:
            logger.warning("slow_handler", extra={"elapsed": elapsed})

        return result
