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

    # Общее.
    CANCEL: str = 'Отмена'
    HELP: str = 'Помощь'
    HELP_RULES: str = 'Правила игры'
    NO: str = 'Нет'
    YES: str = 'Да'
    HOME: str = 'Главное меню'

    # Управление лобби.
    GAME_CREATE: str = 'Создать сновидение'
    GAME_JOIN: str = 'Присоединиться ко сну'
    GAME_START: str = 'Начать путешествие'

    # Управление игрой.
    GAME_DROP: str = 'Выйти из путешествия'
    GAME_DESTROY: str = 'Завершить путешествие'
    PENALTY: str = 'Выдать штраф'
    START_ROUND: str = 'Начать раунд'
    WORD_CORRECT: str = '✅'
    WORD_INCORRECT: str = '❌'


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
    if check_if_user_is_admin(user_id_telegram=user_id_telegram):
       return KEYBOARD_MAIN_MENU_ADMIN
    return KEYBOARD_MAIN_MENU


KEYBOARD_MAIN_MENU: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.GAME_CREATE, RoutersCommands.GAME_JOIN),
        (RoutersCommands.HELP,),
    ),
)
KEYBOARD_MAIN_MENU_ADMIN: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.PING,),
        (RoutersCommands.SYNC_IMAGES,),
        (RoutersCommands.GAME_CREATE, RoutersCommands.GAME_JOIN),
        (RoutersCommands.HELP,),
    ),
)
KEYBOARD_HELP: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.HELP_RULES,),
        (RoutersCommands.HOME,),
    ),
)
KEYBOARD_HOME: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.HOME,),),
)
KEYBOARD_LOBBY: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.GAME_DROP,),),
)
KEYBOARD_LOBBY_HOST: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.GAME_START,),(RoutersCommands.GAME_DROP,)),
)
KEYBOARD_LOBBY_SUPERVISOR: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.START_ROUND,),
        (RoutersCommands.GAME_DROP,),
        (RoutersCommands.GAME_DESTROY,),
    ),
)
KEYBOARD_LOBBY_SUPERVISOR_IN_GAME: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.WORD_CORRECT, RoutersCommands.WORD_INCORRECT),
        (RoutersCommands.PENALTY,),
        (RoutersCommands.GAME_DROP,),
        (RoutersCommands.GAME_DESTROY,),
    ),
)
KEYBOARD_LOBBY_SUPERVISOR_IN_GAME_RETELL: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.WORD_CORRECT, RoutersCommands.WORD_INCORRECT),
        (RoutersCommands.GAME_DROP,),
        (RoutersCommands.GAME_DESTROY,),
    ),
)
KEYBOARD_YES_NO: ReplyKeyboardMarkup = make_row_keyboard(
    rows=((RoutersCommands.YES, RoutersCommands.NO),),
)
KEYBOARD_YES_NO_HOME: ReplyKeyboardMarkup = make_row_keyboard(
    rows=(
        (RoutersCommands.YES, RoutersCommands.NO),
        (RoutersCommands.HOME,),
    ),
)
