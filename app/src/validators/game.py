class GameParams:
    """Параметры игры."""

    PLAYERS_MAX: int = 10
    PLAYERS_MIN: int = 4


class GameRoles:
    """Роли в игре."""

    BUKA: str = 'бука'
    FAIRY: str = 'фея'
    SANDMAN: str = 'песочный человечек'
    SLEEPER: str = 'сновидец'
    # INFO. Тот человек, который играет за буку/фею/песочного человечка,
    #       и при этом отмечает правильно или неправильно сновидец назвал слово.
    SUPERVISOR: str = 'хранитель'


class GameStatus:
    """Статусы/состояния игры."""

    IN_LOBBY: str = 'in_lobby'
    ROUND_IS_STARTED: str = 'round_is_started'
    WAIT_DREAMER_RETAILS: str = 'wait_dreamer_retails'
    PREPARE_NEXT_ROUND: str = 'prepare_next_round'
    FINISHED: str = 'finished'
