from asyncio import (
    Task,
    create_task as asyncio_create_task,
    gather as asyncio_gather,
    sleep as asyncio_sleep,
)
from datetime import (
    datetime,
    timedelta,
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
from app.src.config.config import Timezones
from app.src.crud.user import user_crud
from app.src.crud.user_statistic import user_statistic_crud
from app.src.database.database import (
    RedisKeys,
    async_session_maker,
)
from app.src.models.user import User
from app.src.models.user_statistic import UserStatistic
from app.src.scheduler.scheduler import (
    SchedulerJobNames,
    scheduler,
)
from app.src.utils.image import (
    get_role_image_cards,
    get_shuffled_words_cards,
)
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    make_row_keyboard,
    KEYBOARD_HOME,
    KEYBOARD_LOBBY_SUPERVISOR,
    KEYBOARD_LOBBY_SUPERVISOR_IN_GAME,
    KEYBOARD_YES_NO,
)
from app.src.utils.redis_app import (
    redis_delete,
    redis_get,
    redis_set,
    redis_sset_process,
)
from app.src.validators.game import GameRoles


# INFO. Словарь с игрой в конечно форме (хранится в Redis):
# game = {
#     'redis_key': src_game_lobby_1234',
#     'number': '1234',
#     'password': '1234',
#     'round_is_started': False,
#     'ended': False,

#     'host_user_id_telegram': 12345678,
#     'host_chat_id': 87654321,
#     'host_lobby_message_id': 123,

#     'cards_ids': [abcd123..., dcba231..., ...],
#     'card_index: 0,

#     'players': {
#         12345678: {
#             'name': 'Иван Иванов (@iVan)',
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
    in_lobby_select_game = State()
    in_lobby_enter_password = State()
    in_game = State()
    in_game_destroy_game = State()
    in_game_drop_game = State()
    in_game_set_penalty = State()

    _join_game_number: str


# -----------------------------------------------------------------------------
# INFO. Функции для подготовки игры (лобби).
# -----------------------------------------------------------------------------


def form_lobby_host_message(
    message: Message | None = None,
    redis_key: str | None = None,
) -> str:
    """Формирует сообщение для хоста лобби."""
    game: dict[str, Any] = process_game_in_redis(message=message, redis_key=redis_key, get=True)
    players: str = '\n'.join(f'- {player["name"]}' for player in game['players'].values())
    return (
        'Приветствую, капитан! Ты готов отправиться со своей командой в новое '
        'путешествие по миру снов? Отлично! Игра успешно создана!\n'
        f'Номер: {game['number']}\n'
        f'Пароль: {game['password']}'
        '\n\n'
        'Список сновидцев:\n'
        f'{players}'
    )


def process_avaliable_game_numbers(
    get: bool = False,
    add_number: str | None = None,
    remove_number: str | None = None,
) -> list[str] | None:
    """
    Используя Redis Set, возвращает или модифицирует
    список номеров доступных игр.
    """
    return redis_sset_process(
        key=RedisKeys.GAME_LOBBIES_AVALIABLE,
        get=get,
        add_value=add_number,
        remove_value=remove_number,
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


async def setup_game_data(game: dict[str, Any]) -> None:
    """Подготавливает данные для игры."""
    game.update(
        {
            'round_is_started': False,
            'ended': False,

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
    __set_players_roles(game=game)
    process_game_in_redis(redis_key=game['redis_key'], set_game=game)


# -----------------------------------------------------------------------------
# INFO. Функции для обработки команд игроков в ходе игры.
# -----------------------------------------------------------------------------


async def process_in_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команды игроков в ходе игры."""
    game: dict[str, Any] = process_game_in_redis(message=message, get=True)
    state_value: str = await state.get_state()
    if not await __process_in_game_validate_message_text(
        game=game,
        message=message,
        state_value=state_value,
    ):
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )

    # INFO. Подтверждение действий.
    if state_value == GameForm.in_game_destroy_game:
        return await process_in_game_destroy_game_confirm(message=message, state=state)
    elif state_value == GameForm.in_game_drop_game:
        return await __process_in_game_drop_game_confirm(message=message, state=state)
    elif state_value == GameForm.in_game_set_penalty:
        return await __process_in_game_set_penalty_confirm(message=message, state=state)

    # INFO. Фиксация ответа спящего игрока.
    elif message.text == RoutersCommands.WORD_CORRECT:
        await __process_in_game_answer(game=game, is_correct=True, message=message)
    elif message.text == RoutersCommands.WORD_INCORRECT:
        await __process_in_game_answer(game=game, is_correct=False, message=message)

    # INFO. Выдача штрафа игроку.
    elif message.text == RoutersCommands.PENALTY:
        await __process_in_game_set_penalty(game=game, message=message, state=state)

    # INFO. Начало следующего раунда.
    elif message.text == RoutersCommands.START_ROUND:
        await __process_in_game_start_round(game=game)

    # INFO. Выход из / удаление из игры.
    elif message.text == RoutersCommands.GAME_DESTROY:
        await __process_in_game_destroy_game(message=message, state=state)
    elif message.text == RoutersCommands.GAME_DROP:
        await __process_in_game_drop_game(message=message, state=state)
    elif message.text == RoutersCommands.HOME:
        await __process_in_game_home(message=message, state=state)


async def __process_in_game_validate_message_text(
    game: dict[str, Any],
    message: Message,
    state_value: str,
) -> bool:
    """Производит валидацию команд игроков в ходе игры."""
    # INFO. Игрок отвечает боту из особого состояния GameForm,
    #       текст сообщения не содержит команд управления игрой
    #       и должен быть обработан в соответствующем хендлере.
    if state_value in (
        GameForm.in_game_drop_game,
        GameForm.in_game_destroy_game,
        GameForm.in_game_set_penalty,
    ):
        return True

    # INFO. Может придти от любого игрока (в том числе из состояния GameForm.in_lobby!),
    #       но только если игра в состоянии game['ended'] == True.
    if game['ended']:
        if message.text == RoutersCommands.HOME:
            return True

    # INFO. Может придти от любого игрока.
    elif message.text == RoutersCommands.GAME_DROP:
        return True

    # INFO. Может придти только от "supervisor" игрока.
    elif message.text in (
        RoutersCommands.WORD_CORRECT,
        RoutersCommands.WORD_INCORRECT,
        RoutersCommands.PENALTY,
        # INFO. Может придти только если game['round_is_started'] == False.
        RoutersCommands.START_ROUND,
        RoutersCommands.GAME_DESTROY,
        RoutersCommands.HOME,
    ):
        if str(message.from_user.id) == game['players_sleeping_order'][game['supervisor_index']]:
            if message.text == RoutersCommands.START_ROUND:
                if not game['round_is_started']:
                    return True
            else:
                return True

    return False


async def __process_in_game_destroy_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Завершить игру"."""
    await state.set_state(state=GameForm.in_game_destroy_game)
    await message.answer(
        text='Ты действительно хочешь всех разбудить?',
        reply_markup=KEYBOARD_YES_NO,
    )


async def process_in_game_destroy_game_confirm(
    message: Message,
    state: FSMContext,
    from_lobby: bool = False,
) -> None:
    """Обрабатывает результат ответа на команду "Завершить игру"."""

    async def __send_destroy_game_message(chat_id: int) -> None:
        """Задача по уведомлению игроков о принудительном завершении игры."""
        await bot.send_message(
            chat_id=chat_id,
            text='Хранитель сна прервал твое путешествие..',
            reply_markup=KEYBOARD_HOME,
        )

    game: dict[str, Any] = process_game_in_redis(message=message, get=True)

    # INFO. Из лобби подтверждение не требуется.
    if not from_lobby:
        if message.text not in (RoutersCommands.YES, RoutersCommands.NO):
            return await delete_messages_list(
                chat_id=message.chat.id,
                messages_ids=[message.message_id],
            )
        elif message.text == RoutersCommands.NO:
            await state.set_state(state=GameForm.in_game)
            await delete_messages_list(
                chat_id=message.chat.id,
                messages_ids=list(
                    range(
                        game['players'][str(message.from_user.id)]['last_end_game_message_id'],
                        message.message_id,
                    ),
                ),
            )

    game['ended'] = True
    process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    if not from_lobby:
        scheduler.remove_job(job_id=SchedulerJobNames.GAME_END_ROUND.format(number=game['number']))
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=list(
                range(
                    game['players'][str(message.from_user.id)]['last_end_game_message_id'],
                    message.message_id + 1,
                ),
            ),
        )

    # INFO. Даже если человек в лобби, нужно поставить состояние GameForm.in_game,
    #       чтобы он смог обработать команду "RoutersCommands.HOME".
    await state.set_state(state=GameForm.in_game)

    tasks: list[Task] = [
        asyncio_create_task(__send_destroy_game_message(chat_id=data['chat_id']))
        for data in game['players'].values()
    ]
    await asyncio_gather(*tasks)


async def __process_in_game_drop_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Выйти из игры"."""
    game: dict[str, Any] = process_game_in_redis(message=message, get=True)
    game['players'][str(message.from_user.id)]['last_drop_game_message_id'] = message.message_id

    await state.set_state(state=GameForm.in_game_destroy_game)
    await message.answer(
        text='Ты действительно хочешь проснуться?',
        reply_markup=KEYBOARD_YES_NO,
    )


# TODO: Доделать
async def __process_in_game_drop_game_confirm(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает результат ответа на команду "Покинуть игру"."""
    if message.text not in (RoutersCommands.YES, RoutersCommands.NO):
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )

    game: dict[str, Any] = process_game_in_redis(message=message, get=True)

    if message.text == RoutersCommands.NO:
        await state.set_state(state=GameForm.in_game)
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=list(
                range(
                    game['players'][str(message.from_user.id)]['last_drop_game_message_id'],
                    message.message_id + 1,
                ),
            ),
        )

    await __game_drop_move_indexes(game=game, message=message)

    messages_ids: list[int] = []
    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
        if user.message_main_last_id:
            # INFO. Приветственное сообщение + MediaGroup с правилами.
            messages_ids.extend([user.message_main_last_id, user.message_main_last_id + 1])
            await user_crud.update_by_id(
                obj_id=user.id,
                obj_data={'message_main_last_id': None},
                session=session,
                perform_commit=False,
            )
        user_statistic: UserStatistic = await user_statistic_crud.retrieve_by_user_id(
            user_id=user.id,
            session=session,
        )
        await user_statistic_crud.update_by_user_id(
            user_id=user.id,
            obj_data={'total_quits': user_statistic.total_quits + 1},
            session=session,
        )

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



    # async with async_session_maker() as session:
    #     user: User = await user_crud.retrieve_by_id_telegram(obj_id_telegram=message.from_user.id, session=session)  # await
    # process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    # tasks: list[Task] = [
    #     asyncio_create_task(__send_end_game_message(chat_id=data['chat_id']))
    #     for data in game['players'].values()
    # ]
    # await asyncio_gather(*tasks)


async def __process_in_game_set_penalty(
    game: dict[str, Any],
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Пенальти"."""
    game['players'][str(message.from_user.id)]['last_penalty_message_id'] = message.message_id
    process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    rows: list[tuple[str]] = (
        [(RoutersCommands.CANCEL,)]
        +
        [(player['name'],) for player in game['players'].values()]
    )
    await message.reply(
        text='Кто нарушил правила мира снов?',
        reply_markup=make_row_keyboard(rows=rows),
    )
    await state.set_state(state=GameForm.in_game_set_penalty)


# TODO. Зарефакторить функцию.
async def __process_in_game_set_penalty_confirm(
    message: Message,
    state: FSMContext,
):
    """Обрабатывает результат ответа на команду "Выдать штраф"."""
    game: dict[str, Any] = process_game_in_redis(message=message, get=True)
    if message.text == RoutersCommands.CANCEL:
        await state.set_state(state=GameForm.in_game)
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=list(
                range(
                    game['players'][str(message.from_user.id)]['last_penalty_message_id'],
                    message.message_id + 1,
                ),
            ),
        )
        # TODO. Может быть удалять фотографию посылать заново?
        await bot.send_message(
            chat_id=message.chat.id,
            text=' ',
            reply_markup=KEYBOARD_LOBBY_SUPERVISOR_IN_GAME,
        )

    penalty_id_telegram: str | None = None
    for id_telegram, data in game['players'].items():
        if data['name'] == message.text:
            penalty_id_telegram: str = id_telegram
            break

    if penalty_id_telegram:
        game['players'][penalty_id_telegram]['penalties'] += 1
        process_game_in_redis(redis_key=game['redis_key'], set_game=game)
        await state.set_state(state=GameForm.in_game)
        messages_ids: list[int] = [range(game['players'][str(message.from_user.id)]['last_penalty_message_id'], message.message_id + 1)]
    else:
        messages_ids: list[int] = [message.message_id]

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=messages_ids,
    )
    if penalty_id_telegram:
        # TODO. Может быть удалять фотографию посылать заново?
        await bot.send_message(
            chat_id=message.chat.id,
            text=' ',
            reply_markup=KEYBOARD_LOBBY_SUPERVISOR_IN_GAME,
        )


async def __process_in_game_answer(
    game: dict[str, Any],
    is_correct: bool,
    message: Message,
) -> None:
    """
    Фиксирует результат ответа спящего игрока и слово для
    проведения тура по пересказу сна в данных игровой сессии
    и отправляет новую карточку слова игрокам.
    """
    # TODO. Добавить для слов глобальную статистику:
    #       количество правильных/неправильных угадываний.
    if is_correct:
        game['round_correct_count'] += 1
        game['round_correct_words'].append(game['cards_ids'][game['card_index']])
    else:
        game['round_incorrect_count'] += 1
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )
    await __send_new_word(game=game)


async def __process_in_game_start_round(game: dict[str, Any]) -> None:
    """Обрабатывает команду "Начать раунд"."""
    game['round_is_started'] = True
    scheduler.add_job(
        id=SchedulerJobNames.GAME_END_ROUND.format(number=game['number']),
        func=__process_in_game_end_round,
        trigger='date',
        next_run_time=datetime.now(tz=Timezones.MOSCOW) + timedelta(minutes=2),
        kwargs={'game_number': game['number']},
    )
    await __send_new_word(game=game)


async def __process_in_game_home(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Домой"."""
    game: dict[str, Any] = process_game_in_redis(message=message, get=True)
    game['players'].pop(str(message.from_user.id))
    if len(game['players']) == 0:
        process_game_in_redis(redis_key=game['redis_key'], delete=True)
    else:
        process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    await state.clear()
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )
    await command_start(message=message)


# TODO: Доделать
async def __process_in_game_end_round(
    game_number: str,
    skip_results: bool = False,
) -> None:
    # TODO:
    #  1) Предварительно еще нужно учесть пересказ сна.
    #  2) Подсчитать очки в раунде.
    #  3.1) Закончить игру при необходимости
    #  3.2.1) Сместить указатели
    #  3.2.2) Отправить рассылку ролей
    ...


# TODO: Доделать
async def __process_in_game_end_round_confirm(
    game_number: str,
    skip_results: bool = False,
) -> None:
    # TODO:
    #  1) Предварительно еще нужно учесть пересказ сна.
    #  2) Подсчитать очки в раунде.
    #  3.1) Закончить игру при необходимости
    #  3.2.1) Сместить указатели
    #  3.2.2) Отправить рассылку ролей
    ...


# -----------------------------------------------------------------------------
# INFO. Общий функционал.
# -----------------------------------------------------------------------------


def process_game_in_redis(
    redis_key: str | None = None,
    message: Message | None = None,
    user_id_telegram: str | int | None = None,
    get: bool = False,
    delete: bool = False,
    set_game: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not redis_key:
        if not user_id_telegram:
            user_id_telegram: int = message.from_user.id
        number: str = redis_get(key=RedisKeys.USER_GAME_LOBBY_NUMBER.format(id_telegram=str(user_id_telegram)))
        redis_key: str = RedisKeys.GAME_LOBBY.format(number=number)
    if get:
        return redis_get(key=redis_key)
    elif delete:
        redis_delete(key=redis_key)
    elif set_game:
        redis_set(key=redis_key, value=set_game)


async def send_game_roles_messages(game: dict[str, Any]) -> None:
    """Отправляет сообщения игрокам с их ролями."""

    async def __send_game_roles_message(
        id_telegram: str,
        player_data: dict[str, Any],
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


def __choose_drop_game_text(
    is_leave: bool = False,
    is_run_out_of_players: bool = False,
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
    elif is_run_out_of_players:
        choses: list[str] = [
            'Сновидцы стали просыпаться один за другим.. Сон дрогнул.. И рассыпался..',
            'Сон оборвался, как недописанная сказка. Кто-то проснулся — и всё исчезло.',
            'Кто-то покинул чащу снов, и тропы мгновенно заросли. Игра окончена..',
            'История рассыпалась, как карточный домик. Без всех игроков игра — не игра..',
            'Ты ушёл. Остальные пробудились в растерянности. Сны исчезли.. Без прощания..',
        ]
    return choice(choses)


async def __game_drop_move_indexes(
    game: dict[str, Any],
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
            process_game_in_redis(redis_key=game['redis_key'], set_game=game)
            __process_in_game_end_round(skip_results=True)

    process_game_in_redis(redis_key=game['redis_key'], set_game=game)


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
            'В этом раунде ты также — Хранитель сна. Ты следишь за тем, как '
            'сновидец проходит свой путь, и видишь всё: правду, ложь и колебания. '
            'Отмечай верно или ошибочно были названы слова, раздавай пенальти, когда '
            'кто-то нарушает законы царства снов. И не забывай — ты тоже играешь.'
        )


async def __notify_supervisor(chat_id: int) -> None:
    """Уведомляет Хранителя сна о его роли."""
    await bot.send_message(
        chat_id=chat_id,
        text=__get_role_description(role=GameRoles.SUPERVISOR),
        reply_markup=KEYBOARD_LOBBY_SUPERVISOR,
    )


async def __send_new_word(game: dict[str, Any]) -> None:
    """Отправляет новую карточку слова игрокам."""

    async def __send_new_word_to_player(
        id_telegram: str,
        data: dict[str, Any],
        game: dict[str, Any],
    ) -> None:
        """Задача по отправке новой карточки слова игроку."""
        await delete_messages_list(
            chat_id=data['chat_id'],
            messages_ids=[data['card_message_last_id']],
        )
        if id_telegram != game['players_sleeping_order'][game['sleeper_index']]:
            message: Message = await bot.send_photo(
                chat_id=data['chat_id'],
                photo=game['cards_ids'][game['card_index']],
            )
            data['card_message_last_id'] = message.message_id

    tasks: list[Task] = [
        asyncio_create_task(
            __send_new_word_to_player(
                id_telegram=id_telegram,
                game=game,
                data=data,
            ),
        )
        for id_telegram, data in game['players'].items()
    ]
    await asyncio_gather(*tasks)

    game['card_index'] += 1
    process_game_in_redis(redis_key=game['redis_key'], set_game=game)


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
