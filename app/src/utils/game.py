from random import shuffle

from app.src.database.database import RedisKeys
from app.src.utils.redis_app import redis_get
from app.src.validators.game import GameRoles


def form_lobby_host_message(game_number: int) -> str:
    game: dict[str, any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=game_number))
    players: str = '\n'.join(player['name'] for player in game['players'].values())
    return (
        'Игра успешно создана!\n'
        f'Номер: {game_number}\n'
        f'Пароль: {game['password']}'
        '\n\n'
        'Список игроков:\n'
        f'{players}'
    )


def get_players_roles(players_count: int) -> list[str]:
    """
    Формирует список ролей игроков в зависимости от количества.
    """
    if players_count == 4:
        fairy, buka, sandman = 1, 1, 1
    elif players_count == 5:
        fairy, buka, sandman = 1, 1, 2
    elif players_count == 6:
        fairy, buka, sandman = 1, 2, 2
    elif players_count == 7:
        fairy, buka, sandman = 2, 3, 1
    elif players_count == 8:
        fairy, buka, sandman = 2, 3, 2
    elif players_count == 9:
        fairy, buka, sandman = 3, 4, 1
    elif players_count == 10:
        fairy, buka, sandman = 3, 4, 2
    return [GameRoles.FAIRY] * fairy + [GameRoles.BUKA] * buka + [GameRoles.SANDMAN] * sandman


def set_players_roles(game: dict[str, any]) -> None:
    """Обновляет роли игроков в словаре игры "game"."""
    roles: list[str] = get_players_roles(players_count=len(game['players']))
    shuffle(roles)

    i: int = 0
    for id_telegram, data in game['players'].items():
        if id_telegram == game['players_sleeping_order'][game['sleeper_index']]:
            data['role'] = GameRoles.SLEEPER
        else:
            data['role'] = roles[i]
        i += 1
