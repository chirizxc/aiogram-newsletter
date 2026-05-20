import asyncio
from collections.abc import Awaitable, Callable

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message
from jobify import Job

from .album import AlbumMiddleware, message_to_message_data, set_message_data_reply_markup
from .manager import ANManager
from .utils.misc import run_newsletter_task, validate_datetime
from .utils.states import ANState


class AiogramNewsletterHandlers:
    @staticmethod
    def _register_callbacks(
        router: Router,
        handlers: tuple[
            tuple[
                Callable[[CallbackQuery, ANManager], Awaitable[None]],
                State,
            ],
            ...,
        ],
    ) -> None:
        for handler, state in handlers:
            router.callback_query.register(handler, state)

    @staticmethod
    def _register_messages(
        router: Router,
        handlers: tuple[
            tuple[
                Callable[[Message, ANManager], Awaitable[None]],
                State,
            ],
            ...,
        ],
    ) -> None:
        for handler, state in handlers:
            router.message.register(handler, state)

    @classmethod
    async def _newsletters_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data in {"back", "exit"}:
            await an_manager.return_callback()
            await an_manager.delete_previous_message()
        elif data == "add":
            await an_manager.open_send_message_window()
        elif data.startswith("page"):
            page = int(data.split(":")[1])
            await an_manager.state.update_data(page=page)
            await an_manager.open_newsletters_window()
        elif data.startswith("id"):
            job_id = data.split(":")[1]
            await an_manager.state.update_data(job_id=job_id)
            await an_manager.open_newsletter_window()

        await call.answer()

    @classmethod
    async def _newsletter_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_newsletters_window()
        elif data == "delete":
            await an_manager.open_newsletter_delete_window()

        await call.answer()

    @classmethod
    async def _newsletter_delete_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_newsletter_window()
        elif data == "confirm":
            state_data = await an_manager.state.get_data()
            job_id = state_data.get("job_id")
            if not isinstance(job_id, str):
                msg = "job_id"
                raise KeyError(msg)
            job: Job[None] | None = an_manager.jobify.find_job(job_id)
            if job:
                await job.cancel()
            an_manager.jobify.job_metadata.pop(job_id, None)
            await an_manager.open_newsletters_window()

        await call.answer()

    @classmethod
    async def _send_message_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_newsletters_window()

        await call.answer()

    @classmethod
    async def _send_message_message_handler(
        cls,
        message: Message,
        an_manager: ANManager,
    ) -> None:
        message_data = message_to_message_data(message)
        await an_manager.data_storage.set_data(message_data, "message_data")
        await an_manager.open_send_buttons_window()

        await an_manager.delete_message(message)

    @classmethod
    async def _send_buttons_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_send_message_window()
        if data == "skip":
            message_data = await an_manager.data_storage.get_data("message_data")
            message_data = set_message_data_reply_markup(message_data, None)

            await an_manager.data_storage.set_data(message_data, "message_data")
            await an_manager.open_message_preview_window()

        await call.answer()

    @classmethod
    async def _send_buttons_message_handler(
        cls,
        message: Message,
        an_manager: ANManager,
    ) -> None:
        try:
            message_data = await an_manager.data_storage.get_data("message_data")
            buttons = an_manager.inline_keyboard.build_buttons(
                message.text or "",
            )
            message_data = set_message_data_reply_markup(message_data, buttons)

            await an_manager.data_storage.set_data(message_data, "message_data")
            await an_manager.open_message_preview_window()

        except Exception:  # noqa: BLE001
            text = an_manager.text_message.get("send_buttons_error")
            await an_manager.open_send_buttons_window(text)

        await an_manager.delete_message(message)

    @classmethod
    async def _message_preview_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_send_buttons_window()
        elif data == "next":
            await an_manager.open_choose_options_window()

        await call.answer()

    @classmethod
    async def _choose_options_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_message_preview_window()
        elif data == "later":
            await an_manager.open_send_datetime_window()
        elif data == "now":
            await an_manager.open_confirmation_now_window()

        await call.answer()

    @classmethod
    async def _confirmation_now_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_choose_options_window()
        elif data == "confirm":
            state_data = await an_manager.state.get_data()
            users_ids = state_data.get("users_ids", [])
            user_data = an_manager.user.model_dump()
            message_data = await an_manager.data_storage.get_data("message_data")

            task = asyncio.create_task(
                run_newsletter_task(
                    users_ids,
                    user_data,
                    message_data,
                ),
            )
            task.add_done_callback(lambda _: None)
            await an_manager.delete_previous_message()
            await an_manager.state.clear()

        await call.answer()

    @classmethod
    async def _send_datetime_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_choose_options_window()

        await call.answer()

    @classmethod
    async def _send_datetime_message_handler(
        cls,
        message: Message,
        an_manager: ANManager,
    ) -> None:
        if message.text is not None:
            obj = validate_datetime(message.text)

            if obj is None:
                text = an_manager.text_message.get("send_datetime_error")
                await an_manager.open_send_datetime_window(text)
            else:
                await an_manager.data_storage.set_data(obj, "datetime_obj")
                await an_manager.open_confirmation_later_window()

        await an_manager.delete_message(message)

    @classmethod
    async def _confirmation_later_callback_handler(
        cls,
        call: CallbackQuery,
        an_manager: ANManager,
    ) -> None:
        data = call.data or ""
        if data == "back":
            await an_manager.open_send_datetime_window()
        elif data == "confirm":
            state_data = await an_manager.state.get_data()
            users_ids = state_data.get("users_ids", [])
            user_data = an_manager.user.model_dump()
            message_data = await an_manager.data_storage.get_data("message_data")
            obj = await an_manager.data_storage.get_data("datetime_obj")

            job = await an_manager.newsletter_task.schedule(
                users_ids,
                user_data,
                message_data,
            ).at(obj)
            an_manager.jobify.job_metadata[job.id] = {"message_data": message_data}

            await an_manager.open_newsletters_window()

        await call.answer()

    @classmethod
    async def _default_message_handler(
        cls,
        message: Message,
        an_manager: ANManager,
    ) -> None:
        await an_manager.delete_message(message)

    def register(self, dp: Dispatcher) -> None:
        router = Router()
        router.message.outer_middleware(AlbumMiddleware())  # ty: ignore[invalid-argument-type]

        router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
        router.message.filter(F.chat.type == ChatType.PRIVATE)

        self._register_callbacks(
            router,
            (
                (self._newsletters_callback_handler, ANState.newsletters),
                (self._newsletter_callback_handler, ANState.newsletter),
                (self._newsletter_delete_callback_handler, ANState.newsletter_delete),
                (self._send_message_callback_handler, ANState.send_message),
                (self._send_buttons_callback_handler, ANState.send_buttons),
                (self._message_preview_callback_handler, ANState.message_preview),
                (self._choose_options_callback_handler, ANState.choose_options),
                (self._confirmation_now_callback_handler, ANState.confirmation_now),
                (self._send_datetime_callback_handler, ANState.send_datetime),
                (self._confirmation_later_callback_handler, ANState.confirmation_later),
            ),
        )

        self._register_messages(
            router,
            (
                (self._default_message_handler, ANState.newsletter),
                (self._default_message_handler, ANState.newsletter_delete),
                (self._send_message_message_handler, ANState.send_message),
                (self._send_buttons_message_handler, ANState.send_buttons),
                (self._send_datetime_message_handler, ANState.send_datetime),
                (self._default_message_handler, ANState.confirmation_later),
            ),
        )

        dp.include_router(router)
