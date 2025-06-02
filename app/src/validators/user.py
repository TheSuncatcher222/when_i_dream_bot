"""
Модуль с валидаторами моделей базы данных приложения "user".
"""


class UserAchievementDescription:
    """
    Описание достижений пользователя.
    """

    DREAM_MASTER: str = '😻 Cон на яву: отгадал(а) все слова за сновидца и верно пересказал(а) сон'
    NIGHTMARE: str = '👺 Cущий кошмар: не отгадал(а) ни одного слова за сновидца'
    TOP_PENALTIES: str = '🌚 Кайфоломщик: получил(а) больше всего штрафных очков'
    TOP_SCORE: str = '🏆 Высший разум: получил(а) больше всего очков'
    TOP_SCORE_BUKA: str = '🗿 Бу-бу-бука: получил(а) больше всего очков за буку'
    TOP_SCORE_FAIRY: str = '🧚‍♀️ Крестная фея: получил(а) больше всего очков за фею'
    TOP_SCORE_SANDMAN: str = '🎭 Лицемерище: получил(а) больше всего очков за песочного человечка'
    TOP_SCORE_DREAMER: str = '🕵️‍♀️ Яркие сны: получил(а) больше всего очков за сновидца'

    @staticmethod
    def return_attr_names() -> tuple[str]:
        """Возвращает имена атрибутов."""
        # WARNING: в этом порядке будут указаны достижения в итоговом сообщении игрокам!
        return (
            'DREAM_MASTER',
            'NIGHTMARE',
            'TOP_PENALTIES',
            'TOP_SCORE',
            'TOP_SCORE_BUKA',
            'TOP_SCORE_FAIRY',
            'TOP_SCORE_SANDMAN',
            'TOP_SCORE_DREAMER',
        )


class UserParams:
    """
    Параметры пользователей.
    """

    # INFO. Идентификатор меньше, чем 52 бита (4.5e+15) + символ '-'
    ID_TELEGRAM_LEN_MAX: int = 16 + 1
    NAME_FIRST_LEN_MAX: int = 64
    NAME_LAST_LEN_MAX: int = 64
    USERNAME_LEN_MAX: int = 32
