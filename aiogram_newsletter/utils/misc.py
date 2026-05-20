import asyncio
import pickle  # noqa: S403
import re
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import User

from aiogram_newsletter.album import AlbumMessageData, message_data_to_message
from aiogram_newsletter.utils.texts import TextMessage

newsletter_bot: list[Bot] = []


def set_newsletter_bot(bot: Bot) -> None:
    newsletter_bot[:] = [bot]


async def send_message(bot: Bot, chat_id: int, message_data: AlbumMessageData) -> bool:
    message_obj = message_data_to_message(message_data, bot)

    try:
        copy_result = message_obj.send_copy(
            chat_id=chat_id,
            reply_markup=message_obj.reply_markup,
        )
        if hasattr(copy_result, "as_"):
            await copy_result.as_(bot)
        else:
            await copy_result

    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        await send_message(bot, chat_id, message_data)

    except (TelegramBadRequest, Exception):  # noqa: BLE001
        return False

    return True


async def run_newsletter(
    bot: Bot,
    users_ids: list[int],
    message_data: AlbumMessageData,
) -> tuple[int, int]:
    successful, unsuccessful = 0, 0

    for user_id in users_ids:
        is_success = await send_message(bot, user_id, message_data)

        if is_success:
            successful += 1
        else:
            unsuccessful += 1

    return successful, unsuccessful


async def run_newsletter_task(
    users_ids: list[int],
    user_data: dict,
    message_data: AlbumMessageData,
) -> None:
    bot = newsletter_bot[0] if newsletter_bot else None
    assert bot is not None, "Bot is configured by AiogramNewsletterMiddleware"

    user: User = User(**user_data)
    text_message = TextMessage(user.language_code or "en")

    text = text_message.get("newsletter_started")
    await bot.send_message(user.id, text=text)

    text = text_message.get("newsletter_ended")
    successful, unsuccessful = await run_newsletter(bot, users_ids, message_data)
    text = text.format(
        total=len(users_ids),
        successful=successful,
        unsuccessful=unsuccessful,
    )
    await bot.send_message(user.id, text=text)


def validate_url(url: str) -> str | None:
    url_pattern = re.compile(r"https?://\S+|www\.\S+")
    matches = re.findall(url_pattern, url)

    return matches[0] if matches else None


def validate_datetime(datetime_string: str) -> datetime | None:
    try:
        obj = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M").replace(
            tzinfo=UTC,
        )
    except ValueError:
        return None

    return obj


class DataStorage:
    def __init__(self, state: FSMContext) -> None:
        self.state = state

    @classmethod
    def data_to_hex(cls, data: Any) -> str:
        return pickle.dumps(data).hex()

    @classmethod
    def hext_to_data(cls, hext: str) -> Any:
        return pickle.loads(bytes.fromhex(hext))  # noqa: S301

    async def set_data(self, data: Any, key: str) -> None:
        await self.state.update_data({key: self.data_to_hex(data)})

    async def get_data(self, key: str) -> Any:
        state_data = await self.state.get_data()
        hext = state_data.get(key)
        if not isinstance(hext, str):
            raise KeyError(key)
        return self.hext_to_data(hext)
