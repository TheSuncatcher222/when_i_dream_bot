"""
Модуль с валидаторами моделей базы данных приложения "user".
"""


class UserParams:
    """
    Параметры пользователей.
    """

    # INFO. Идентификатор меньше, чем 52 бита (4.5e+15) + символ '-'
    ID_TELEGRAM_LEN_MAX: int = 16 + 1
    NAME_FIRST_LEN_MAX: int = 64
    NAME_LAST_LEN_MAX: int = 64
    USERNAME_LEN_MAX: int = 32
