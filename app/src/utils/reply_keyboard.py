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
    SYNC_IMAGES: str = '⚠️ Синхронизировать картинки'

    # Common
    HELP: str = 'Помощь'
    HOME: str = 'Главное меню'
    GAME_CREATE: str = 'Создать игру'
    GAME_JOIN: str = 'Присоединиться к игре'
    GAME_START: str = 'Начать игру'
    GAME_DROP: str = 'Выйти из игры'


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


def get_keyboard_main_menu(user_id_telegram: int | str) -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру главного меню.
    """
    # TODO. Добавить Redis
    keyboard: list[list[str]] = (
        (RoutersCommands.GAME_CREATE, RoutersCommands.GAME_JOIN),
        (RoutersCommands.HELP,),
    )
    if check_if_user_is_admin(user_id_telegram=user_id_telegram):
        keyboard: list[list[str]] = (
            (RoutersCommands.PING,),
            (RoutersCommands.SYNC_IMAGES,),
            *keyboard,
        )
    return make_row_keyboard(rows=keyboard)


KEYBOARD_HOME: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.HOME,),),
)
KEYBOARD_LOBBY: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.GAME_DROP,),),
)
KEYBOARD_LOBBY_HOST: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.GAME_START,),(RoutersCommands.GAME_DROP,)),
)
