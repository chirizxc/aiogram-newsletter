from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from operator import itemgetter
from typing import Any, cast

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardMarkup,
    Message,
    User,
)
from jobify import Jobify

from .utils.exceptions import (
    MESSAGE_DELETE_ERRORS,
    MESSAGE_EDIT_ERRORS,
)
from .utils.keyboards import InlineKeyboard
from .utils.misc import DataStorage
from .utils.states import ANState
from .utils.texts import TextMessage

job_metadata: dict[str, dict[str, Any]] = {}


class ANManager:

    def __init__(
            self,
            jobify: Jobify,
            newsletter_task: Any,
            text_message: TextMessage,
            inline_keyboard: InlineKeyboard,
            data: dict[str, Any],
    ) -> None:
        self.bot: Bot = data["bot"]
        self.user: User = data["event_from_user"]
        self.state: FSMContext = data["state"]

        self.jobify = jobify
        self.newsletter_task = newsletter_task
        self.text_message = text_message
        self.inline_keyboard = inline_keyboard
        self.data_storage = DataStorage(self.state)

        self._data: dict[str, Any] = data

    @property
    def middleware_data(self) -> dict[str, Any]:
        return self._data

    async def return_callback(self) -> None:
        return_callback = await self.data_storage.get_data("return_callback")
        await return_callback(**self.middleware_data)

    async def update_interfaces_language(self, language_code: str) -> None:
        if (
                language_code in self.text_message.text_messages and
                language_code in self.inline_keyboard.text_buttons
        ):
            await self.state.update_data(language_code=language_code)
            self.text_message.language_code = language_code
            self.inline_keyboard.language_code = language_code
            return

        msg = (
            f"Language code '{language_code}'"
            " not in text message or button text"
        )
        raise ValueError(msg)

    async def newsletter_menu(
            self,
            users_ids: list[int],
            return_callback: Callable[..., Awaitable],
    ) -> Message:
        await self.data_storage.set_data(return_callback, "return_callback")
        await self.state.update_data(users_ids=users_ids, page=1)
        return await self.open_newsletters_window()

    async def open_newsletters_window(self) -> Message:
        state_data = await self.state.get_data()
        page, page_size = state_data.get("page", 1), 5
        items = sorted(
            [
                (job.exec_at.strftime("%Y-%m-%d %H:%M"), f"id:{job.id}")
                for job in self.jobify.get_active_jobs()
            ],
            key=itemgetter(0),
        )
        page_items = items[(page - 1) * page_size: page * page_size]
        total_pages = (len(items) + page_size - 1) // page_size
        text = self.text_message.get("newsletters")
        reply_markyp = self.inline_keyboard.newsletters(page_items, page, total_pages)
        users_ids = cast("list[int]", state_data.get("users_ids", []))
        text = text.format(total=len(users_ids))
        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.newsletters)
        return message

    async def open_newsletter_window(self) -> Message:
        state_data = await self.state.get_data()
        job_id = cast("str", state_data.get("job_id"))
        metadata = job_metadata.get(job_id, {})
        message_data = cast("dict[str, Any]", metadata.get("message_data"))
        message_obj = Message(**message_data).as_(self.bot)
        await message_obj.send_copy(
            chat_id=self.user.id,
            reply_markup=message_obj.reply_markup,
        )

        text = self.text_message.get("newsletter")
        reply_markyp = self.inline_keyboard.back_delete()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.newsletter)
        return message

    async def open_newsletter_delete_window(self) -> Message:
        text = self.text_message.get("newsletter_delete")
        reply_markyp = self.inline_keyboard.back_confirm()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.newsletter_delete)
        return message

    async def open_send_message_window(self) -> Message:
        text = self.text_message.get("send_message")
        reply_markyp = self.inline_keyboard.send_message()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.send_message)
        return message

    async def open_send_buttons_window(self, text: str | None = None) -> Message:
        if not text:
            text = self.text_message.get("send_buttons")
        reply_markyp = self.inline_keyboard.send_buttons()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.send_buttons)
        return message

    async def open_message_preview_window(self) -> Message:
        message_data = await self.data_storage.get_data("message_data")
        message_obj = Message(**message_data)
        await message_obj.send_copy(
            self.user.id,
            reply_markup=message_obj.reply_markup,
        ).as_(self.bot)

        text = self.text_message.get("message_preview")
        reply_markyp = self.inline_keyboard.back_next()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.message_preview)
        return message

    async def open_choose_options_window(self) -> Message:
        text = self.text_message.get("choose_options")
        reply_markyp = self.inline_keyboard.choose_options()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.choose_options)
        return message

    async def open_confirmation_now_window(self) -> Message:
        text = self.text_message.get("confirmation_now")
        reply_markyp = self.inline_keyboard.back_confirm()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.confirmation_now)
        return message

    async def open_send_datetime_window(self, text: str | None = None) -> Message:
        if not text:
            text = self.text_message.get("send_datetime")
        reply_markyp = self.inline_keyboard.back()
        datetime_now = datetime.now(UTC)
        text = text.format(datetime_string=datetime_now.strftime("%Y-%m-%d %H:%M"))

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.send_datetime)
        return message

    async def open_confirmation_later_window(self) -> Message:
        text = self.text_message.get("confirmation_later")
        reply_markyp = self.inline_keyboard.back_confirm()

        message = await self.send_message(text, reply_markup=reply_markyp)
        await self.state.set_state(ANState.confirmation_later)
        return message

    async def send_message(
            self,
            text: str,
            reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        message = await self.bot.send_message(
            text=text,
            chat_id=self.user.id,
            reply_markup=reply_markup,
        )
        await self.delete_previous_message()
        await self.state.update_data(an_message_id=message.message_id)
        return message

    @classmethod
    async def delete_message(cls, message: Message) -> None:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

    async def delete_previous_message(self) -> Message | None:
        state_data = await self.state.get_data()
        an_message_id = state_data.get("an_message_id")
        if not an_message_id: return None  # noqa:E701

        try:
            await self.bot.delete_message(
                message_id=an_message_id,
                chat_id=self.user.id,
            )
        except TelegramBadRequest as exc:
            if any(e in exc.message for e in MESSAGE_DELETE_ERRORS):
                try:
                    text = self.text_message.get("outdated_text")
                    edited_message = await self.bot.edit_message_text(
                        message_id=an_message_id,
                        chat_id=self.user.id,
                        text=text,
                    )
                    return edited_message if isinstance(edited_message, Message) else None
                except TelegramBadRequest as exc:
                    if not any(e in exc.message for e in MESSAGE_EDIT_ERRORS):
                        raise
