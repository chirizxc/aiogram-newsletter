from collections.abc import Iterator, Sequence
from itertools import starmap, zip_longest
from typing import Any, Self, TypeAlias

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.methods import CopyMessages, DeleteMessages, ForwardMessages
from aiogram.types import (
    ChatIdUnion,
    DateTimeUnion,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaLivePhoto,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    MessageEntity,
    ReplyParameters,
)
from aiogram.types.reply_markup_union import ReplyMarkupUnion

AlbumMessageData: TypeAlias = dict[str, Any] | list[dict[str, Any]]
ReplyMarkupData: TypeAlias = ReplyMarkupUnion | dict[str, Any] | None
MediaData: TypeAlias = (
    InputMediaAudio
    | InputMediaDocument
    | InputMediaLivePhoto
    | InputMediaPhoto
    | InputMediaVideo
)


def _to_input_media(
    message: Message,
    caption: str | None = None,
    parse_mode: str | Default | None = Default("parse_mode"),
    caption_entities: list[MessageEntity] | None = None,
) -> MediaData:
    kwargs: dict[str, Any] = {
        "caption": caption or message.caption,
        "parse_mode": parse_mode,
        "caption_entities": caption_entities or message.caption_entities,
    }
    if message.photo:
        return InputMediaPhoto(media=message.photo[-1].file_id, **kwargs)
    if message.video:
        return InputMediaVideo(media=message.video.file_id, **kwargs)
    if message.audio:
        return InputMediaAudio(media=message.audio.file_id, **kwargs)
    if message.document:
        return InputMediaDocument(media=message.document.file_id, **kwargs)
    msg = f"Unsupported media type: {message.content_type}"
    raise ValueError(msg)


def _message_data_to_messages(data: AlbumMessageData) -> list[Message]:
    if isinstance(data, list):
        return [Message(**message_data) for message_data in data]
    return [Message(**data)]


def message_data_to_message(data: AlbumMessageData, bot: Bot | None = None) -> Message:
    messages = _message_data_to_messages(data)
    if len(messages) == 1:
        return messages[0].as_(bot)
    return AlbumMessage.new(messages, bot=bot)


def message_to_message_data(message: Message) -> AlbumMessageData:
    if isinstance(message, AlbumMessage):
        return [item.model_dump() for item in message.messages]
    return message.model_dump()


def set_message_data_reply_markup(
    data: AlbumMessageData,
    reply_markup: ReplyMarkupData,
) -> AlbumMessageData:
    if isinstance(data, list):
        if len(data) == 0:
            return data
        data[0]["reply_markup"] = reply_markup
        return data
    data["reply_markup"] = reply_markup
    return Message(**data).model_dump()


class AlbumMessage(Message, frozen=False):
    _messages: list[Message]

    @classmethod
    def new(
        cls,
        messages: Sequence[Message],
        *,
        bot: Bot | None = None,
    ) -> Self:
        items = list(messages)
        first = items[0]
        self = cls.model_validate(first, from_attributes=True).as_(bot)
        self._messages = items
        return self

    @property
    def messages(self) -> list[Message]:
        return self._messages

    @property
    def message_ids(self) -> list[int]:
        return [m.message_id for m in self._messages]

    @property
    def content_type(self) -> str:
        return "media_group"

    def as_input_media(
        self,
        caption: str | list[str] | None = None,
        parse_mode: str | Default | None = Default("parse_mode"),
        caption_entities: (list[MessageEntity] | list[list[MessageEntity]] | None) = None,
    ) -> list[MediaData]:
        captions: list[str | None]
        if isinstance(caption, str):
            captions = [caption]
        elif caption:
            captions = list(caption)
        else:
            captions = [None]

        entities: list[list[MessageEntity] | None] = []
        if caption_entities:
            first_caption_entity = caption_entities[0]
            if isinstance(first_caption_entity, MessageEntity):
                for item in caption_entities:
                    assert isinstance(item, MessageEntity)
                    entities.append([item])
            else:
                for item in caption_entities:
                    assert isinstance(item, list)
                    entities.append(item)
        else:
            entities = [None]
        return list(
            starmap(
                _to_input_media,
                zip_longest(
                    self._messages,
                    captions,
                    [parse_mode],
                    entities,
                    fillvalue=None,
                ),
            ),
        )

    def copy_to(  # ty: ignore[invalid-method-override]
        self,
        chat_id: ChatIdUnion,
        *,
        message_thread_id: int | None = None,
        direct_messages_topic_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        remove_caption: bool | None = None,
        **kwargs: Any,
    ) -> CopyMessages:
        assert self.chat is not None, (
            "This method can be used only if chat is present in the message."
        )
        return CopyMessages(
            chat_id=chat_id,
            from_chat_id=self.chat.id,
            message_ids=self.message_ids,
            message_thread_id=message_thread_id,
            direct_messages_topic_id=direct_messages_topic_id,
            disable_notification=disable_notification,
            protect_content=protect_content,
            remove_caption=remove_caption,
            **kwargs,
        ).as_(self.bot)

    def delete(  # ty: ignore[invalid-method-override]
        self,
        **kwargs: Any,
    ) -> DeleteMessages:
        assert self.chat is not None, (
            "This method can be used only if chat is present in the message."
        )
        return DeleteMessages(
            chat_id=self.chat.id,
            message_ids=self.message_ids,
            **kwargs,
        ).as_(self.bot)

    def forward(  # ty: ignore[invalid-method-override]
        self,
        chat_id: ChatIdUnion,
        *,
        message_thread_id: int | None = None,
        direct_messages_topic_id: int | None = None,
        video_start_timestamp: DateTimeUnion | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        message_effect_id: str | None = None,
        **kwargs: Any,
    ) -> ForwardMessages:
        assert self.chat is not None, (
            "This method can be used only if chat is present in the message."
        )
        return ForwardMessages(
            chat_id=chat_id,
            from_chat_id=self.chat.id,
            message_ids=self.message_ids,
            message_thread_id=message_thread_id,
            direct_messages_topic_id=direct_messages_topic_id,
            video_start_timestamp=video_start_timestamp,
            disable_notification=disable_notification,
            protect_content=protect_content,
            message_effect_id=message_effect_id,
            **kwargs,
        ).as_(self.bot)

    async def send_copy(  # ty: ignore[invalid-method-override]
        self,
        chat_id: ChatIdUnion,
        *,
        disable_notification: bool | None = None,
        reply_to_message_id: int | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: ReplyMarkupUnion | None = None,
        allow_sending_without_reply: bool | None = None,
        message_thread_id: int | None = None,
        protect_content: bool | Default | None = Default("protect_content"),
        direct_messages_topic_id: int | None = None,
        remove_caption: bool | None = None,
        **kwargs: Any,
    ) -> list[Message]:
        if self.bot is None:
            msg = "Bot is not configured"
            raise RuntimeError(msg)

        return await self.bot.send_media_group(
            chat_id=chat_id,
            media=self.as_input_media(
                caption="" if remove_caption else None,
                parse_mode=None,
            ),
            disable_notification=disable_notification,
            allow_sending_without_reply=allow_sending_without_reply,
            message_thread_id=message_thread_id,
            protect_content=protect_content,
            direct_messages_topic_id=direct_messages_topic_id,
            reply_parameters=reply_parameters,
            reply_to_message_id=reply_to_message_id,
            **kwargs,
        )

    def __iter__(  # ty: ignore[invalid-method-override]
        self,
    ) -> Iterator[Message]:
        return iter(self._messages)

    def __len__(self) -> int:
        return len(self._messages)
