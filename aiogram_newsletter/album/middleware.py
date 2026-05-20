import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, Router
from aiogram.types import Message, TelegramObject
from cachebox import TTLCache

from .album_message import AlbumMessage


class AlbumMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        latency: float = 0.2,
        maxsize: int = 10_000,
        ttl: float = 10.0,
        router: Router | None = None,
    ) -> None:
        self.latency = latency
        self.cache: TTLCache[str, list[Message]] = TTLCache(
            maxsize,
            ttl=ttl,
        )
        if router is not None:
            router.message.outer_middleware(self)  # ty: ignore[invalid-argument-type]

    async def __call__(  # ty: ignore[invalid-method-override]
        self,
        handler: Callable[
            [TelegramObject, dict[str, Any]],
            Awaitable[Any],
        ],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        media_group_id = event.media_group_id
        try:
            self.cache[media_group_id].append(event)
        except KeyError:
            self.cache[media_group_id] = [event]
        else:
            return None

        await asyncio.sleep(self.latency)

        messages = self.cache.pop(media_group_id)
        bot = data.get("bot")
        if not isinstance(bot, Bot):
            bot = event.bot
        album = AlbumMessage.new(messages, bot=bot)
        return await handler(album, data)
