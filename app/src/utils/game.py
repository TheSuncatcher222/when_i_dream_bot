from app.src.database.database import RedisKeys
from app.src.utils.redis_app import redis_get


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
