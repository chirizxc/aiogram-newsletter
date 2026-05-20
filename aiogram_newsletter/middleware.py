from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, User
from jobify import Jobify

from .manager import ANManager
from .utils.keyboards import InlineKeyboard
from .utils.misc import run_newsletter_task, set_newsletter_bot
from .utils.texts import TextMessage


class AiogramNewsletterMiddleware(BaseMiddleware):
    def __init__(
        self,
        jobify: Jobify,
        text_message: TextMessage | None = None,
        inline_keyboard: InlineKeyboard | None = None,
    ) -> None:
        self.jobify = jobify
        self.newsletter_task = jobify.task(run_newsletter_task)
        self.text_message = text_message
        self.inline_keyboard = inline_keyboard

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")

        if chat and chat.type == ChatType.PRIVATE:
            user: User = data["event_from_user"]
            state: FSMContext = data["state"]

            state_data = await state.get_data()
            language_code = state_data.get("language_code")

            language_code = language_code or user.language_code or "en"
            text_message = self.text_message or TextMessage(language_code)
            inline_keyboard = self.inline_keyboard or InlineKeyboard(language_code)

            an_manager = ANManager(
                jobify=self.jobify,
                newsletter_task=self.newsletter_task,
                text_message=text_message,
                inline_keyboard=inline_keyboard,
                data=data,
            )

            data["an_manager"] = an_manager
            assert event.bot is not None
            set_newsletter_bot(event.bot)

        return await handler(event, data)
