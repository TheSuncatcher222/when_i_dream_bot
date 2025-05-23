"""
Модуль с валидаторами моделей базы данных приложения "image".
"""

class ImageParams:
    """
    Параметры изображений.
    """

    CATEGORY_LEN_MAX: int = 16
    # Пример: AaAAAaAAAaaAAAAAAAaaaA_AAAAaaA1a-Aa_1AAa1aAaAAAAa-AAaA11aAA1Aaa11aaaAAAAAAaAAaAAAAaA
    ID_TELEGRAM_LEN_MAX: int = 128
    # Пример: /app/src/res/characters/х1_песочный_человечек.jpg
    LOCAL_PATH_LEN_MAX: int = 128
    NAME_LEN_MAX: int = 24


class ImageCategory:
    """
    Категории изображений.
    """

    CHARACTERS: str = 'characters'
    RULES: str = 'rules'
    WORDS: str = 'words'
