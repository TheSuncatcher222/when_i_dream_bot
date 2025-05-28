from random import shuffle

from app.src.database.database import RedisKeys
from app.src.utils.image import get_shuffled_words_cards
from app.src.utils.redis_app import redis_get
from app.src.validators.game import GameRoles


def form_lobby_host_message(game_number: int) -> str:
    game: dict[str, any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=game_number))
    players: str = '\n'.join(player['name'] for player in game['players'].values())
    return (
        'Приветствую, капитан! Ты готов отправиться со своей командой в новое '
        'путешествие по миру снов? Отлично! Игра успешно создана!\n'
        f'Номер: {game_number}\n'
        f'Пароль: {game['password']}'
        '\n\n'
        'Список сновидцев:\n'
        f'{players}'
    )


def get_role_description(role: str) -> str:
    if role == GameRoles.BUKA:
        return (
            'В этом раунде ты — бука-мифоман. Обманывай сновидца, сбивай '
            'его с пути, преврати его сны в кошмары! Твоя цель: чтобы сновидец '
            'не отгадал ни единого слова!'
        )
    if role == GameRoles.FAIRY:
        return (
            'В этом раунде ты — добрая фея (ну или добрый фей). Всячески помогай '
            'сновидцу пройти по его нелегкому пути. Твоя цель: чтобы сновидец '
            'отгадал все-все-все слова!'
        )
    if role == GameRoles.SANDMAN:
        return (
            'В этом раунде ты — песочный человечек. Поддерживай хрупкий мир '
            'снов в гармонии. Помогай сновидцу отбиваться от кошмаров, если он не '
            'справляется, сбивай его с пути, если путь его слишком легок. '
            'Твоя цель: чтобы сновидец отгадал ровно половину слов!'
        )
    if role == GameRoles.SLEEPER:
        return (
            'В этом раунде ты — сновидец. Твой разум парит в глубинах грёз, где '
            'добро и зло плетут узоры твоих снов. Прислушивайся к голосам — но помни, '
            'не все они желают тебе добра. Попробуй понять, кто тебе помогает, '
            'а кто уводит в чащу кошмаров.. Твоя цель: отгадать как можно больше слов! '
            'Теперь закрывай глаза, баю-бай. Игра началась!'
        )


async def setup_game_data(game: dict[str, any]) -> None:
    """Подготавливает данные для игры."""
    game.update(
        {
            'cards_ids': await get_shuffled_words_cards(),
            'cards_start_from': 0,

            'players_sleeping_order': __get_players_sleeping_order(players=game['players']),
            'sleeper': 0,
            'supervisor': -1,
        },
    )
    __set_players_roles(game=game)

    for data in game['players'].items():
        data.update(
            {
                'score': 0,
                'score_buka': 0,
                'score_fairy': 0,
                'score_sandman': 0,
                'penalties': 0,
            },
        )


def __get_players_roles(players_count: int) -> list[str]:
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


def __get_players_sleeping_order(players: list[str]) -> list[str]:
    shuffle(players)
    return players


def __set_players_roles(game: dict[str, any]) -> None:
    """Обновляет роли игроков в словаре игры "game"."""
    roles: list[str] = __get_players_roles(players_count=len(game['players']))
    shuffle(roles)

    i: int = 0
    for id_telegram, data in game['players'].items():
        if id_telegram == game['players_sleeping_order'][game['sleeper_index']]:
            data['role'] = GameRoles.SLEEPER
        else:
            data['role'] = roles[i]
        i += 1
