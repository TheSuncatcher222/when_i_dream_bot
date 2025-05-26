"""
Модуль с валидаторами моделей базы данных приложения "image".
"""

from enum import IntEnum


class ImageParams:
    """
    Параметры изображений.
    """

    CATEGORY_LEN_MAX: int = 16
    # Пример: AaAAAaAAAaaAAAAAAAaaaA_AAAAaaA1a-Aa_1AAa1aAaAAAAa-AAaA11aAA1Aaa11aaaAAAAAAaAAaAAAAaA
    ID_TELEGRAM_LEN_MAX: int = 128
    # Пример: /app/src/res/characters/х1_песочный_человечек.jpg
    LOCAL_PATH_LEN_MAX: int = 128
    NAME_LEN_MAX: int = 48


class ImageCategory(IntEnum):
    """
    Категории изображений.
    """

    CHARACTERS: int = 1
    RULES: int = 2
    WORDS: int = 3

    @classmethod
    def get_category_by_dir(cls, dir_name: str) -> int:
        return getattr(cls, dir_name.upper())
