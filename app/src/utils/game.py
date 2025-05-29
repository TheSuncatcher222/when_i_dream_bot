from asyncio import (
    Task,
    create_task as asyncio_create_task,
    gather as asyncio_gather,
    sleep as asyncio_sleep,
)
from typing import Any
from random import (
    choice,
    shuffle,
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import (
    StatesGroup,
    State,
)
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
)

from app.src.bot.bot import bot
from app.src.bot.routers.start import command_start
from app.src.crud.user import user_crud
from app.src.database.database import (
    RedisKeys,
    async_session_maker,
)
from app.src.models.user import User
from app.src.scheduler import scheduler
from app.src.utils.image import (
    get_role_image_cards,
    get_shuffled_words_cards,
)
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    make_row_keyboard,
    KEYBOARD_LOBBY_SUPERVISOR,
)
from app.src.utils.redis_app import (
    redis_get,
    redis_set,
)
from app.src.validators.game import GameRoles


# INFO. Словарь с игрой в конечно форме (хранится в Redis):
# game = {
#     'password': 1234,
#     'round_is_started': False,

#     'host_user_id_telegram': 12345678,
#     'host_chat_id': 87654321,

#     'cards_ids': [abcd123..., dcba231..., ...],
#     'card_index: 0,

#     'players': {
#         12345678: {
#             'name': Иван Иванов (@iVan),
#             'chat_id': 87654321,
#             'messages_to_delete': [],
#             'card_message_last_id'

#             'role': 'buka',
#             'score': 0,
#             'score_buka': 0,
#             'score_fairy': 0,
#             'score_sandman': 0,
#             'penalties': 0,
#         },
#         ...
#     },
#     'players_sleeping_order': [12345678, 56781234, ...],
#     'sleeper_index': 0,
#     'supervisor_index': 1,

#     'round_correct_count': 0,
#     'round_incorrect_count': 0,
#     'round_words': ['word1', 'word2', 'word3', ...],
# }


class GameForm(StatesGroup):
    """
    Состояния формы роутера.
    """

    in_lobby = State()
    in_game = State()
    in_game_set_penalty = State()

    # TODO. Будет много сообщений, лучше вести список тех, что надо удалить.
    _init_message_id: int
    _game_number: int


def form_lobby_host_message(game_number: int) -> str:
    game: dict[str, Any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=game_number))
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


async def process_in_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команды игроков в ходе игры."""
    game: dict[str, Any] = await __process_in_game_validate_and_get_game(message=message, state=state)
    if not game:
        return

    elif message.text == RoutersCommands.PENALTY:
        await __process_in_game_penalty(game=game, message=message, state=state)
    elif message.text == RoutersCommands.ANSWER_CORRECT:
        await __process_in_game_answer(game=game, is_correct=True)
    elif message.text == RoutersCommands.ANSWER_INCORRECT:
        await __process_in_game_answer(game=game, is_correct=False)
    if message.text == RoutersCommands.START_ROUND:
        await __process_in_game_start_round(game=game)


async def set_penalty(
    message: Message,
    state: FSMContext,
):
    """Обрабатывает команду выдачи пенальти."""
    if message.text == RoutersCommands.CANCEL:
        await state.set_state(state=GameForm.in_game)
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )

    state_data: dict[str, Any] = await state.get_data()
    game: dict[str, Any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=state_data['_game_number']))
    penalty_id_telegram: str | None = None
    for id_telegram, data in game['players'].items():
        if data['name'] == message.text:
            penalty_id_telegram: str = id_telegram
            break

    if penalty_id_telegram:
        messages_ids: list[int] = [range(game['players'][str(message.from_user.id)]['last_penalty_message_id'], message.message_id + 1)]
        game['players'][penalty_id_telegram]['penalties'] += 1
        redis_set(key=RedisKeys.GAME_LOBBY.format(number=game['game_number']), value=game)
        await state.set_state(state=GameForm.in_game)
    else:
        messages_ids: list[int] = [message.message_id]

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=messages_ids,
    )


async def send_game_start_messages(game: dict[str, Any]) -> None:
    """Отправляет сообщение игрокам в начале игры."""

    async def __send_game_start_message(chat_id: int) -> None:
        """Задача по отправке сообщения игроку в начале игры."""
        messages_ids: list[int] = []
        for t in (
            'Твое путешествие начинается через..',
            '3..',
            '2..',
            '1..',
            'Сейчас!✨',
        ):
            await bot.send_message(
                chat_id=chat_id,
                text=t,
            )
            await asyncio_sleep(1)
        await delete_messages_list(
            chat_id=chat_id,
            messages_ids=messages_ids,
        )

    tasks: list[Task] = [
        asyncio_create_task(__send_game_start_message(chat_id=data['chat_id']))
        for data in game['players'].values()
    ]
    await asyncio_gather(*tasks)


async def send_game_roles_messages(game: dict[str, Any]) -> None:
    """Отправляет сообщения игрокам с их ролями."""

    async def __send_game_roles_message(
        id_telegram: str,
        player_data: dict[str, any],
        roles_images: dict[str, str],
        supervisor_id_telegram: str,
    ):
        """Задача по отправке сообщения с ролью игроку."""
        await bot.send_photo(
            chat_id=player_data['chat_id'],
            # TODO. Возможно стоит скрыть за спойлер.
            photo=roles_images[player_data['role']],
            # TODO. Возможно стоит скрыть за спойлер.
            caption=__get_role_description(role=player_data['role']),
        )
        if id_telegram == supervisor_id_telegram:
            await __notify_supervisor(chat_id=player_data['chat_id'])

    roles_images: dict[str, str] = await get_role_image_cards()
    tasks: list[Task] = [
        asyncio_create_task(
            __send_game_roles_message(
                id_telegram=id_telegram,
                player_data=player_data,
                roles_images=roles_images,
                supervisor_id_telegram=game['players_sleeping_order'][game['supervisor_index']],
            ),
        )
        for id_telegram, player_data in game['players'].items()
    ]
    return await asyncio_gather(*tasks)


async def setup_game_data(game: dict[str, Any]) -> None:
    """Подготавливает данные для игры."""
    game.update(
        {
            'round_is_started': False,

            'cards_ids': await get_shuffled_words_cards(),
            'card_index': 0,

            'players_sleeping_order': __get_players_sleeping_order(players=game['players']),
            'sleeper_index': 0,
            'supervisor_index': -1,

            'round_correct_count': 0,
            'round_incorrect_count': 0,
            'round_correct_words': [],
        },
    )
    __set_players_roles(game=game)

    for data in game['players'].items():
        data.update(
            {
                'messages_to_delete': [],
                'card_message_last_id': None,
                'set_penalty_last_id': None,

                'score': 0,
                'score_buka': 0,
                'score_fairy': 0,
                'score_sandman': 0,
                'penalties': 0,
            },
        )


def __choose_drop_game_text(
    is_leave: bool = False,
    is_game_dropped: bool = False,
) -> str:
    """Рандомно выбирает текст."""
    if is_leave:
        choses: list[str] = [
            'Ты покинул мир сновидений раньше времени. Образы растворились, а смыслы так и не раскрылись..',
            'Ты проснулся. Сны остались позади — незавершённые, неразгаданные, забытые..',
            'Ты вырвался из сновидений. Но за их пределами всё ещё слышны отголоски чужих голосов..',
            'Грезы рассыпались, как пыль в лунном свете. Ты покинул мир снов слишком рано..',
            'Ты проснулся.. Над тобой склонился Бабайка и тихо прошептал: «Слабак»..',
            'Ты вынырнул из грёз, как из ванной с пеной. А вечеринки-то ещё не закончена..',
            'Ты проснулся.. И теперь никогда не узнаешь, кто же был в костюме единорога.',
        ]
    elif is_game_dropped:
        choses: list[str] = [
            'Сновидцы стали просыпаться один за другим.. Сон дрогнул.. И рассыпался..',
            'Сон оборвался, как недописанная сказка. Кто-то проснулся — и всё исчезло.',
            'Кто-то покинул чащу снов, и тропы мгновенно заросли. Игра окончена..',
            'История рассыпалась, как карточный домик. Без всех игроков игра — не игра..',
            'Ты ушёл. Остальные пробудились в растерянности. Сны исчезли.. Без прощания..',
        ]
    return choice(choses)


async def __game_drop(
    message: Message,
    state: FSMContext,
) -> None:
    """Выводит игрока из текущей игры и удаляет все сообщения."""
    state_data: dict[str, Any] = await state.get_data()
    game_key: str = RedisKeys.GAME_LOBBY.format(number=state_data['_game_number'])
    game: dict[str, Any] = redis_get(key=game_key)

    await __game_drop_move_indexes(game=game, game_key=game_key, message=message)

    messages_ids: list[int] = []
    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
        if user.message_main_last_id:
            # INFO. Приветственное сообщение + MediaGroup с правилами.
            messages_ids.extend([user.message_main_last_id, user.message_main_last_id + 1])
            user_crud.update_by_id(
                obj_id=user.id,
                obj_data={'message_main_last_id': None},
                session=session,
            )
    messages_ids.extend(game['players_drop_game']['messages_to_delete'])

    await state.clear()
    message: Message = await message.answer(
        text=__choose_drop_game_text(is_leave=True),
        reply_markup=ReplyKeyboardRemove(),
    )
    await asyncio_sleep(5)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=messages_ids,
    )
    await command_start(message=message)


async def __game_drop_move_indexes(
    game: dict[str, Any],
    game_key: str,
    message: Message,
) -> None:
    player_index: int = game['players_sleeping_order'].index(str(message.from_user.id))
    game['players_sleeping_order'].pop(player_index)
    game['players'].pop(str(message.from_user.id))

    # INFO. После окончания каждого раунда указатели будут сдвинуты на +1
    #       в функции __process_in_game_end_round.
    if player_index > game['sleeper_index']:
        if player_index < game['supervisor_index']:
            game['supervisor_index'] -= 1
        else:
            if game['supervisor_index'] > len(game['players_sleeping_order']) - 1:
                game['supervisor_index'] = 0
            await __notify_supervisor(chat_id=game['players_sleeping_order'][game['supervisor_index']])

    elif player_index <= game['sleeper_index']:
        game['sleeper_index'] -= 1
        if game['supervisor_index'] == player_index == 0:
            await __notify_supervisor(chat_id=game['players_sleeping_order'][game['supervisor_index']])
        else:
            game['supervisor_index'] -= 1
        if player_index == game['sleeper_index']:
            redis_set(key=game_key, value=game)
            __process_in_game_end_round(skip_results=True)

    redis_set(key=game_key, value=game)


# TODO. Проверить, что если человек ушел с игры - роли будут обновляться.
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


def __get_role_description(role: str) -> str:
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
    if role == GameRoles.SUPERVISOR:
        return (
            'В этом раунде ты также — хранитель сна. Ты следишь за тем, как '
            'сновидец проходит свой путь, и видишь всё: правду, ложь и колебания. '
            'Отмечай верно или ошибочно были названы слова, раздавай пенальти, когда '
            'кто-то нарушает законы царства снов. И не забывай — ты тоже играешь.'
        )


async def __notify_supervisor(chat_id: int) -> None:
    """Уведомляет хранителя сна о его роли."""
    await bot.send_message(
        chat_id=chat_id,
        text=__get_role_description(role=GameRoles.SUPERVISOR),
        reply_markup=KEYBOARD_LOBBY_SUPERVISOR,
    )


async def __process_in_game_answer(game: dict[str, Any], is_correct: bool) -> None:
    """
    TODOS:
        2) Запомнить слово для пересказа сна спящим игроком.
        2) отправить новую карточку
    """
    if is_correct:
        game['round_correct_count'] += 1
        game['round_correct_words'].append(game['cards_ids'][game['card_index']])
    else:
        game['round_incorrect_count'] += 1
    await __send_new_words(game=game)


# TODO. CRITICAL. Дописать функционал
async def __process_in_game_end_round(
    game: dict[str, Any],
    skip_results: bool = False,
) -> None:
    ...


async def __process_in_game_penalty(
    game: dict[str, Any],
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Пенальти"."""
    game['players'][str(message.from_user.id)]['last_penalty_message_id'] = message.message_id
    redis_set(key=RedisKeys.GAME_LOBBY.format(number=game['game_number']), value=game)

    rows: list[tuple[str]] = [(name for name in game['players'].values())] + [RoutersCommands.CANCEL]
    await message.reply(text='Кто нарушил правила мира снов?', reply_markup=make_row_keyboard(rows=rows))
    await state.set_state(state=GameForm.in_game_set_penalty)


# TODO. CRITICAL. Дописать функционал
async def __process_in_game_start_round(game: dict[str, Any]) -> None:
    """Обрабатывает команду "Начать раунд"."""
    game['round_is_started'] = True
    # scheduler.add_job(
    #     func=__process_in_game_end_round,
    #     trigger='date',
    #     next_run_time=game['round_end_time'],
    #     args=[game],
    # )
    await __send_new_words(game=game)


async def __process_in_game_validate_and_get_game(
    message: Message,
    state: FSMContext,
) -> dict[str, Any] | None:
    """
    Производит валидацию команд игроков в ходе игры.

    Если валидация успешна, возвращает данные игры.
    """
    if message.text == RoutersCommands.GAME_DROP:
        await __game_drop(message=message, state=state)
        return

    if message.text not in (
        RoutersCommands.ANSWER_CORRECT,
        RoutersCommands.ANSWER_INCORRECT,
        RoutersCommands.PENALTY,
        RoutersCommands.START_ROUND,
    ):
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )
        return

    state_data: dict[str, Any] = await state.get_data()
    game: dict[str, Any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=state_data['_game_number']))
    if (
        game['players_sleeping_order'][game['supervisor_index']] != message.from_user.id
        or
        (message.text == RoutersCommands.START_ROUND and game['round_is_started'])
    ):
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )
        return

    return game


async def __send_new_words(game: dict[str, Any]) -> None:
    """Отправляет новую карточку слова игрокам."""

    async def __send_new_word(
        id_telegram: str,
        data: dict[str, Any],
        game: dict[str, Any],
    ) -> None:
        """Задача по отправке новой карточки слова игроку."""
        if id_telegram != game['players_sleeping_order'][game['sleeper_index']]:
            await delete_messages_list(
                chat_id=data['chat_id'],
                messages_ids=[data['card_message_last_id']],
            )
            message: Message = await bot.send_photo(
                chat_id=data['chat_id'],
                photo=game['cards_ids'][game['card_index']],
            )
            data['card_message_last_id'] = message.message_id

    tasks: list[Task] = [
        asyncio_create_task(
            __send_new_word(
                game=game,
                id_telegram=id_telegram,
                data=data,
            ),
        )
        for id_telegram, data in game['players'].items()
    ]
    await asyncio_gather(*tasks)

    game['card_index'] += 1
    redis_set(key=RedisKeys.GAME_LOBBY.format(number=game['game_number']), value=game)


def __set_players_roles(game: dict[str, Any]) -> None:
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
