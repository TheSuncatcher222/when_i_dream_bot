class GameParams:

    PLAYERS_MAX: int = 10
    PLAYERS_MIN: int = 4


class GameRoles:

    BUKA: str = 'бука'
    FAIRY: str = 'фея'
    SANDMAN: str = 'песочный человечек'
    SLEEPER: str = 'спящий'
    # INFO. Тот человек, который играет за буку/фейу/песочного человечка,
    #       и при этом отмечает правильно или неправильно спящий назвал слово.
    SUPERVISOR: str = 'хранитель'
