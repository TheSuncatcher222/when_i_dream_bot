from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.src.utils.auth import check_if_user_is_admin


class RoutersCommands:
    """
    Класс хранения списка команд.
    """

    # Admin
    PING: str = '⚠️ Пинг'

    # Common
    HELP: str = 'Помощь'
    HOME: str = 'Главное меню'
    GAME_CREATE: str = 'Создать игру'
    GAME_JOIN: str = 'Присоединиться к игре'
    RULES: str = 'Правила'


def make_row_keyboard(rows: tuple[tuple[str]]) -> ReplyKeyboardMarkup:
    """
    Создаёт реплай-клавиатуру с кнопками в один/несколько ряд(ов)
    :param items: список текстов для кнопок
    :return: объект реплай-клавиатуры
    """
    keyboard: list[list[KeyboardButton]] = []
    for row in rows:
        keyboard.append(KeyboardButton(text=item) for item in row)
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


async def get_keyboard_main_menu(user_id_telegram: int | str) -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру главного меню.
    """
    # TODO. Добавить Redis
    keyboard: list[list[str]] = (
        (RoutersCommands.GAME_CREATE, RoutersCommands.GAME_JOIN),
        (RoutersCommands.RULES, RoutersCommands.HELP),
    )
    if check_if_user_is_admin(user_id_telegram=user_id_telegram):
        keyboard: list[list[str]] = (
            (RoutersCommands.PING,),
            *keyboard,
        )
    return make_row_keyboard(rows=keyboard)


KEYBOARD_HOME: ReplyKeyboardMarkup = make_row_keyboard(rows=((RoutersCommands.HOME,),))
