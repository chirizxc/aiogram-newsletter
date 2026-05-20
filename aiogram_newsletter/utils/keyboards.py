from dataclasses import dataclass
from typing import ClassVar

from aiogram.enums import ButtonStyle
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder as Builder,
    InlineKeyboardButton as Button,
    InlineKeyboardMarkup as Markup,
)

from .misc import validate_url


@dataclass
class InlineKeyboard:
    text_buttons: ClassVar[dict[str, dict[str, str]]] = {
        "en": {
            "add": "Add",
            "delete": "Delete",
            "back": "Back",
            "exit": "Exit",
            "skip": "Skip",
            "next": "Next",
            "later": "Later",
            "now": "Now",
            "confirm": "Confirm",
        },
        "ru": {
            "add": "Добавить",
            "delete": "Удалить",
            "back": "Назад",
            "exit": "Выйти",
            "skip": "Пропустить",
            "next": "Далее",
            "later": "Позже",
            "now": "Сейчас",
            "confirm": "Подтвердить",
        },
    }

    def __init__(self, language_code: str) -> None:
        self.language_code = language_code if language_code in self.text_buttons else "en"

    def _get_button(
        self,
        code: str,
        url: str | None = None,
        style: ButtonStyle | None = None,
    ) -> Button:
        text = self.text_buttons[self.language_code][code]
        if not url:
            return Button(text=text, callback_data=code, style=style)
        return Button(text=text, url=url, style=style)

    def back(self) -> Markup:
        return Markup(
            inline_keyboard=[[self._get_button("back")]],
        )

    def back_add(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [
                    self._get_button("exit", style=ButtonStyle.DANGER),
                    self._get_button("add", style=ButtonStyle.SUCCESS),
                ],
            ],
        )

    def back_next(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [
                    self._get_button("back", style=ButtonStyle.PRIMARY),
                    self._get_button("next", style=ButtonStyle.SUCCESS),
                ],
            ],
        )

    def back_delete(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [self._get_button("back"), self._get_button("delete")],
            ],
        )

    def back_confirm(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [
                    self._get_button("back", style=ButtonStyle.PRIMARY),
                    self._get_button("confirm", style=ButtonStyle.SUCCESS),
                ],
            ],
        )

    def newsletters(
        self,
        items: list[tuple[str, str]],
        page: int,
        total_pages: int,
    ) -> Markup:
        paginator = InlineKeyboardPaginator(
            items=items,
            current_page=page,
            total_pages=total_pages,
            after_reply_markup=self.back_add(),
        )
        return paginator.as_markup()

    def send_message(self) -> Markup:
        return Markup(
            inline_keyboard=[[self._get_button("back", style=ButtonStyle.PRIMARY)]],
        )

    def send_buttons(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [
                    self._get_button("back", style=ButtonStyle.PRIMARY),
                    self._get_button("skip", style=ButtonStyle.SUCCESS),
                ],
            ],
        )

    def message_preview(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [
                    self._get_button("back", style=ButtonStyle.PRIMARY),
                    self._get_button("next", style=ButtonStyle.SUCCESS),
                ],
            ],
        )

    def choose_options(self) -> Markup:
        return Markup(
            inline_keyboard=[
                [
                    self._get_button("later"),
                    self._get_button("now", style=ButtonStyle.SUCCESS),
                ],
                [self._get_button("back", style=ButtonStyle.PRIMARY)],
            ],
        )

    @staticmethod
    def build_buttons(buttons: str) -> Markup | None:
        if not buttons:
            return None

        rows: list[list[Button]] = []
        for row in buttons.splitlines():
            button_row: list[Button] = []
            for button in row.split(","):
                text, separator, url = button.partition("|")
                if not separator:
                    msg = "Button must contain a separator"
                    raise ValueError(msg)
                validated_url = validate_url(url.strip())
                if validated_url is None:
                    msg = "Button must contain a valid URL"
                    raise ValueError(msg)
                button_row.append(Button(text=text.strip(), url=validated_url))
            if button_row:
                rows.append(button_row)

        if not rows:
            return None

        return Markup(
            inline_keyboard=rows,
        )


class InlineKeyboardPaginator:
    first_page_label = "« {}"
    previous_page_label = "‹ {}"
    current_page_label = "· {} ·"
    next_page_label = "{} ›"
    last_page_label = "{} »"

    def __init__(
        self,
        items: list[tuple[str, str]],
        current_page: int = 1,
        total_pages: int = 1,
        row_width: int = 1,
        data_pattern: str = "page:{}",
        before_reply_markup: Markup | None = None,
        after_reply_markup: Markup | None = None,
    ) -> None:
        self.items = items
        self.current_page = current_page
        self.total_pages = total_pages
        self.row_width = row_width
        self.data_pattern = data_pattern

        self.builder = Builder()
        self.before_reply_markup = before_reply_markup
        self.after_reply_markup = after_reply_markup

    def _items_builder(self) -> Builder:
        builder = Builder()

        for key, val in self.items:
            builder.button(text=key, callback_data=val)
        builder.adjust(self.row_width)

        return builder

    def _navigation_builder(self) -> Builder:
        builder = Builder()
        keyboard_dict: dict[int, int | str] = {}

        if self.total_pages > 1:
            if self.total_pages <= 5:
                pages = range(1, self.total_pages + 1)
                keyboard_dict.update(zip(pages, pages, strict=True))
            else:
                page_range: range | list[int]
                if self.current_page <= 3:
                    page_range = range(1, 4)
                    keyboard_dict[4] = self.next_page_label.format(4)
                    keyboard_dict[self.total_pages] = self.last_page_label.format(
                        self.total_pages,
                    )
                elif self.current_page > self.total_pages - 3:
                    keyboard_dict[1] = self.first_page_label.format(1)
                    keyboard_dict[self.total_pages - 3] = self.previous_page_label.format(
                        self.total_pages - 3,
                    )
                    page_range = range(self.total_pages - 2, self.total_pages + 1)
                else:
                    keyboard_dict[1] = self.first_page_label.format(1)
                    keyboard_dict[self.current_page - 1] = (
                        self.previous_page_label.format(self.current_page - 1)
                    )
                    keyboard_dict[self.current_page + 1] = self.next_page_label.format(
                        self.current_page + 1,
                    )
                    keyboard_dict[self.total_pages] = self.last_page_label.format(
                        self.total_pages,
                    )
                    page_range = [self.current_page]
                keyboard_dict.update(zip(page_range, page_range, strict=True))
            keyboard_dict[self.current_page] = self.current_page_label.format(
                self.current_page,
            )

            for key, val in sorted(keyboard_dict.items()):
                builder.button(
                    text=str(val),
                    callback_data=str(self.data_pattern.format(key)),
                )
            builder.adjust(5)

        return builder

    def as_markup(self) -> Markup:
        if self.before_reply_markup:
            self.builder.attach(Builder(markup=self.before_reply_markup.inline_keyboard))

        self.builder.attach(self._items_builder())
        self.builder.attach(self._navigation_builder())

        if self.after_reply_markup:
            self.builder.attach(Builder(markup=self.after_reply_markup.inline_keyboard))

        return self.builder.as_markup()
