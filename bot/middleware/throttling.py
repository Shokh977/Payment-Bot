"""Simple in-memory rate limiter."""
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 1.0, burst: int = 5):
        """
        rate  — minimum seconds between allowed messages
        burst — allowed burst size before throttling kicks in
        """
        self.rate  = rate
        self.burst = burst
        self._tokens: dict[int, float]      = defaultdict(lambda: burst)
        self._last:   dict[int, float]      = defaultdict(float)
        self._warned: dict[int, float]      = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        elapsed = now - self._last[user_id]
        self._tokens[user_id] = min(self.burst, self._tokens[user_id] + elapsed * (1.0 / self.rate))
        self._last[user_id] = now

        if self._tokens[user_id] >= 1:
            self._tokens[user_id] -= 1
            return await handler(event, data)

        # Throttled — warn once per 30s
        last_warn = self._warned.get(user_id, 0)
        if now - last_warn > 30:
            self._warned[user_id] = now
            await event.answer("Juda ko'p so'rovlar. Iltimos, biroz kuting.")
        # Silently drop
        return None
