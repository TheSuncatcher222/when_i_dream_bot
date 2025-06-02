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
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.src.bot.bot import bot
from app.src.bot.routers.start import command_start
from app.src.config.config import (
    TimeIntervals,
    Timezones,
)
from app.src.crud.user import user_crud
from app.src.crud.user_achievement import user_achievement_crud
from app.src.crud.user_statistic import user_statistic_crud
from app.src.database.database import (
    AsyncSession,
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
    KEYBOARD_YES_NO_HOME,
)
from app.src.utils.redis_app import (
    redis_check_exists,
    redis_delete,
    redis_get,
    redis_set,
    redis_sset_process,
)
from app.src.validators.game import (
    GameParams,
    GameRoles,
    GameStatus,
)
from app.src.validators.user import UserAchievementDescription

# INFO. Словарь с игрой в конечно форме (хранится в Redis):
# game = {
#     'number': '1234',
#     'password': '1234',
#     'redis_key': src_game_lobby_1234',
#     'status': lobby,
#
#     'host_chat_id': 87654321,
#     'host_lobby_message_id': 123,
#
#     # TODO. Можно ограничить количество карт. В игре участвует N игроков,
#             в раунде используется не более N слов, тогда нужно N*M слов.
#     'cards_ids': [abcd123..., dcba231..., ...],
#     'card_index: 0,
#
#     'players': {
#         '12345678': {
#             'name': 'Иван Иванов (@iVan)',
#             'chat_id': 87654321,

#             'messages_to_delete': [],
#             'card_message_last_id'
#
#             'role': 'buka',
#             'statistic': {
#                   'top_penalties': 0,
#                   'top_score_buka': 0,
#                   'top_score_fairy': 0,
#                   'top_score_sandman': 0,
#                   'top_score_sleeper': 0,
#             },
#             'achievements': {},
#         },
#         ...
#     },
#
#     'players_sleeping_order': [12345678, 56781234, ...],
#     'sleeper_index': 0,
#     'supervisor_index': 1,

#     'round_correct_count': 0,
#     'round_incorrect_count': 0,
#     'round_user_retell_dream_correct': True,
#     'round_correct_words': ['word1', 'word2', 'word3', ...],
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


# INFO. Протестировано ✅
def form_lobby_host_message(game: dict[str, Any]) -> str:
    """Формирует сообщение для хоста лобби."""
    players: str = '\n'.join(f'- {player["name"]}' for player in game['players'].values())
    return (
        'Список сновидцев:\n'
        f'{players}'
    )


# INFO. Протестировано ✅
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
            message: Message = await bot.send_message(
                chat_id=chat_id,
                text=t,
                reply_markup=ReplyKeyboardRemove(),
            )
            messages_ids.append(message.message_id)
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
    for k in ('host_chat_id', 'host_lobby_message_id'):
        del game[k]
    game.update(
        {
            'status': GameStatus.PREPARE_NEXT_ROUND,

            'cards_ids': await get_shuffled_words_cards(),
            'card_index': 0,

            'players_sleeping_order': __get_players_sleeping_order(players=game['players']),
            'sleeper_index': 0,
            'supervisor_index': -1,

            'round_correct_count': 0,
            'round_incorrect_count': 0,
            'round_user_retell_dream_correct': False,
            'round_correct_words': [],
        },
    )
    for data in game['players'].items():
        data.update(
            {
                'messages_to_delete': [],
                'card_message_last_id': None,
                'set_penalty_last_id': None,
                'statistic': {
                    'top_penalties': 0,
                    'top_score_buka': 0,
                    'top_score_fairy': 0,
                    'top_score_sandman': 0,
                    'top_score_sleeper': 0,
                },
                'achievements': {},
            },
        )
    __set_players_roles(game=game)
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


# -----------------------------------------------------------------------------
# INFO. Функции для обработки команд игроков в ходе игры.
# -----------------------------------------------------------------------------


async def process_in_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команды игроков в ходе игры."""
    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    state_value: str = await state.get_state()
    if not await __process_in_game_validate_message_text(
        game=game,
        message=message,
        state_value=state_value,
    ):
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
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
    elif game['status'] == GameStatus.WAIT_DREAMER_RETAILS:
        return await __process_in_game_end_round_ask_for_retail_confirm(message=message)

    # INFO. Фиксация ответа сновидца.
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
    #       но только если игра в состоянии game['status'] == GameStatus.FINISHED
    #       (завершена по любой причине).
    if game['status'] == GameStatus.FINISHED:
        if message.text == RoutersCommands.HOME:
            return True

    # INFO. Может придти от любого игрока.
    elif message.text == RoutersCommands.GAME_DROP:
        return True


    # INFO. Может придти только от "supervisor" игрока, не содержит KEYBOARD команд.
    elif (
        game['status'] == GameStatus.WAIT_DREAMER_RETAILS
        and
        str(message.from_user.id) == game['players_sleeping_order'][game['supervisor_index']]
    ):
        return True

    # INFO. Может придти только от "supervisor" игрока.
    elif message.text in (
        RoutersCommands.WORD_CORRECT,
        RoutersCommands.WORD_INCORRECT,
        RoutersCommands.PENALTY,
        # INFO. Может придти только если game['status'] == GameStatus.PREPARE_NEXT_ROUND.
        RoutersCommands.START_ROUND,
        RoutersCommands.GAME_DESTROY,
        RoutersCommands.HOME,
    ):
        if str(message.from_user.id) == game['players_sleeping_order'][game['supervisor_index']]:
            if message.text == RoutersCommands.START_ROUND:
                if game['status'] == GameStatus.PREPARE_NEXT_ROUND:
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

    async def __send_destroy_game_message(
        chat_id: int,
        supervisor_chat_id: int,
    ) -> None:
        """Задача по уведомлению игроков о принудительном завершении игры."""
        if chat_id == supervisor_chat_id:
            text: str = 'Сон был прерван..'
        else:
            text: str = 'Хранитель сна прервал твое путешествие..',
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=KEYBOARD_HOME,
        )

    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)

    # INFO. Из лобби подтверждение не требуется.
    if not from_lobby:
        if message.text not in (RoutersCommands.YES, RoutersCommands.NO):
            await process_game_in_redis(redis_key=game['redis_key'], release=True)
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

    game['status'] = GameStatus.FINISHED
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
    process_avaliable_game_numbers(remove_number=game['number'])

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
        asyncio_create_task(
            __send_destroy_game_message(
                chat_id=data['chat_id'],
                supervisor_chat_id=message.chat.id,
            ),
        )
        for data in game['players'].values()
    ]
    await asyncio_gather(*tasks)


async def __process_in_game_drop_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Выйти из игры"."""
    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    await process_game_in_redis(redis_key=game['redis_key'], release=True)
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

    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)

    if message.text == RoutersCommands.NO:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
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

        # await user_statistic_crud.update_by_user_id(
        #     user_id=user.id,
        #     obj_data={'total_quits': user_statistic.total_quits + 1},
        #     session=session,
        # )

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
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

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
    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    if message.text == RoutersCommands.CANCEL:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        await state.set_state(state=GameForm.in_game)
        await delete_messages_list(game['players'][str(message.from_user.id)]['last_penalty_message_id'], message.message_id)
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
        await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
        await state.set_state(state=GameForm.in_game)
        messages_ids: list[int] = (game['players'][str(message.from_user.id)]['last_penalty_message_id'], message.message_id)
    else:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
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
    Фиксирует результат ответа сновидца и слово для
    проведения тура по пересказу сна в данных игровой сессии.

    Ставит задачу отправки нового слова игрокам.
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
    game['status'] = GameStatus.ROUND_IS_STARTED
    scheduler.add_job(
        id=SchedulerJobNames.GAME_END_ROUND.format(number=game['number']),
        func=__process_in_game_end_round_ask_for_retail,
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
    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    game['players'].pop(str(message.from_user.id))
    if len(game['players']) == 0:
        await process_game_in_redis(redis_key=game['redis_key'], delete=True)
    else:
        # INFO. Игры в лобби не имеют статуса.
        if 'status' not in game and len(game['players']) < GameParams.PLAYERS_MAX:
            process_avaliable_game_numbers(add_number=game['number'])
            await bot.edit_message_text(
                chat_id=game['host_chat_id'],
                message_id=game['host_lobby_message_id'],
                text=form_lobby_host_message(game=game),
            )
        await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    await state.clear()
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )
    await command_start(message=message)



async def __process_in_game_end_game(
    game: dict[str, Any],
) -> None:
    """Завершает игру."""

    async def __process_in_game_end_game_send_message(
        text: str,
        chat_id: int,
    ) -> None:
        """Задача по уведомлению игроков о завершении игры."""
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=KEYBOARD_HOME,
        )

    async def __process_in_game_end_game_update_user_db(
        id_telegram: str | int,
        data: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Обновляет статистику и достижения игрока."""
        for crud in (user_statistic_crud, user_achievement_crud):
            await crud.increment_by_telegram_id(
                user_id_telegram=id_telegram,
                obj_data=data['statistic'],
                session=session,
                perform_commit=False,
            )

    def __set_game_achievements(game: dict[str, Any]) -> None:
        """Выдает достижения за игру."""
        keys: tuple[str] = (
            'top_penalties',
            'top_score',
            'top_score_buka',
            'top_score_fairy',
            'top_score_sandman',
            'top_score_sleeper',
        )
        for key in keys:
            max_value: int = max((data['statistic'][key] for data in game['players'].values()))
            if max_value == 0:
                continue
            for data in game['players'].values():
                if data['statistic'].get(key, None) == max_value:
                    data['achievements'][key] = 1

    def __set_game_statistics(game: dict[str, Any]) -> None:
        """Выдает итоговые очки за игру."""
        for data in game['players'].values():
            data['statistic']['top_score'] = (
                data['statistic']['top_score_buka'] +
                data['statistic']['top_score_fairy'] +
                data['statistic']['top_score_sandman'] +
                data['statistic']['top_score_sleeper'] -
                data['statistic']['top_penalties']
            )

        max_score: int = max((data['statistic'].get('top_score', 0) for data in game['players'].values()))
        if max_score == 0:
            return
        for data in game['players'].values():
            if data['statistic'].get('top_score', 0) == max_score:
                data['statistic']['total_wins'] = 1

    # INFO. Протестировано ✅
    def __get_results_text(game: dict[str, Any]) -> str:
        """Возвращает текст с результатами игры."""
        sorted_players = sorted(
            game['players'].values(),
            key=lambda player: player['statistic'].get('top_score', 0),
            reverse=True,
        )
        medals: dict[int, str] = {
            1: '🥇 ',
            2: '🥈 ',
            3: '🥉 ',
        }

        text: list[str] = [
            (
                'Последнее слово найдено, последняя роль сыграна. Сон подошёл к концу, но магия осталась с вами. '
                'Феи радостно порхают на прощание, буки злобно бурчат, песочные человечки машут вам своими мешочками с песком. '
                'Сегодня вы вместе создали волшебство: смеялись, гадали, путались и помогали. '
                'Спасибо за это прекрасное путешествие — вы были потрясающими!'
                '\n\n'
                '-----------\n'
                'Итоги игры:\n'
                '-----------\n'
            ),
        ]

        i: int = 1
        for data in sorted_players:
            text.append(
                '\n'
                f'{medals.get(i, '🎖 ')}{data["name"]}:\n'
                f'- общий счет: {data["statistic"]["top_score"]}\n'
                f'- очки за фею: {data["statistic"]["top_score_fairy"]}\n'
                f'- очки за буку: {data["statistic"]["top_score_buka"]}\n'
                f'- очки за песочного человечка: {data["statistic"]["top_score_sandman"]}\n'
                f'- очки за сновидца: {data["statistic"]["top_score_sleeper"]}\n'
                f'- штрафные очки: {data["statistic"].get("top_penalties", 0)}\n',
            )
            i += 1

        text.append(
            '\n---------\n'
            'Достижения:'
            '\n---------',
        )

        for a in UserAchievementDescription.return_attr_names():
            players_names: list[str] = []
            for data in sorted_players:
                if a.lower() in data['achievements']:
                    players_names.append(data['name'])
            if players_names:
                players: str = '\n'.join(f'- {player}' for player in players_names)
                text.append('\n\n' + f'{getattr(UserAchievementDescription, a)}:\n{players}')
        return ''.join(text)

    __set_game_statistics(game=game)
    __set_game_achievements(game=game)
    game['status'] = GameStatus.FINISHED
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    async with async_session_maker() as session:
        tasks: list[Task] = [
            __process_in_game_end_game_update_user_db(
                id_telegram=id_telegram,
                data=data,
                session=session,
            )
            for id_telegram, data in game['players'].items()
        ]
        await asyncio_gather(*tasks)
        await session.commit()

    text: str = __get_results_text(game=game)
    tasks: list[Task] = [
        asyncio_create_task(
            __process_in_game_end_game_send_message(
                text=text,
                chat_id=data['chat_id'],
            ),
        )
        for data in game['players'].values()
    ]
    await asyncio_gather(*tasks)


async def __process_in_game_end_round_ask_for_retail(game_number: str) -> None:
    """Завершает раунд и просит сновидца пересказать сон."""

    async def __process_in_game_end_round_ask_for_retail_send_message(
        text: str,
        chat_id: int,
        supervisor_chat_id: int,
    ) -> None:
        """Задача по уведомлению игроков о просьбе сновидца пересказать сон."""
        if chat_id == supervisor_chat_id:
            reply_markup: list[ReplyKeyboardMarkup] = KEYBOARD_YES_NO_HOME
        else:
            reply_markup: list[ReplyKeyboardMarkup] = KEYBOARD_HOME
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )

    game: dict[str, Any] = await process_game_in_redis(game_number, get=True)
    text: str = (
        'Та-да! А вот и утро! Но перед тем как будить нашего сновидца, '
        'попросите его в мельчайших подробностях вспомнить свой сон. '
        'Пусть это будет абсолютный полет фантазии, полный внезапных '
        'сумасбродных и причудливых сюжетных поворотов! Важно, что сновидец '
        'в своем рассказе должен упомянуть все ВЕРНО угаданные слова!'
        '\n\n'
    )
    if game['round_correct_count'] == 0:
        text += (
            'Т-с-с! Не говорите, что сновидец не угадал ни одного слова! '
            'Пусть пофантазирует 😉'
        )
    else:
        words: str = '\n'.join(game['round_correct_words'])
        text += 'А вот и сами слова (т-с-с, не говори сновидцу!):\n' + words

    game['status'] = GameStatus.WAIT_DREAMER_RETAILS
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    supervisor_t_id: str = game['players_sleeping_order'][game['supervisor_index']]
    tasks: list[Task] = [
        __process_in_game_end_round_ask_for_retail_send_message(
            text=text,
            chat_id=data['chat_id'],
            supervisor_chat_id=game['players'][supervisor_t_id]['chat_id'],
        )
        for data in game['players'].values()
    ]
    await asyncio_gather(*tasks)


async def __process_in_game_end_round_ask_for_retail_confirm(
    message: Message,
) -> None:
    """Обрабатывает результат ответа на правильность пересказа сна сновидца."""
    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    if message.text == RoutersCommands.YES:
        game['round_user_retell_dream_correct'] = True
    else:
        game['round_user_retell_dream_correct'] = False
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
    await __process_in_game_end_round(game_number=game['number'])


# -----------------------------------------------------------------------------
# INFO. Общий функционал.
# -----------------------------------------------------------------------------


# INFO. Протестировано ✅
async def process_game_in_redis(
    redis_key: str | None = None,
    message: Message | None = None,
    user_id_telegram: str | int | None = None,
    get: bool = False,
    delete: bool = False,
    release: bool = False,
    set_game: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not redis_key:
        if not user_id_telegram:
            user_id_telegram: int = message.from_user.id
        number: str = redis_get(key=RedisKeys.USER_GAME_LOBBY_NUMBER.format(id_telegram=str(user_id_telegram)))
        redis_key: str = RedisKeys.GAME_LOBBY.format(number=number)

    # INFO. Есть шанс, что несколько игроков одновременно получат данные
    #       игры в Redis и начнется состояние гонки.
    # TODO. Посылать номер, чтобы не парсить.
    # INFO. redis_key=src_lobby_{number}
    number: str = redis_key.split('_')[-1]
    while 1:
        if redis_check_exists(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number)):
            await asyncio_sleep(0.05)
            continue
        break

    if get:
        redis_set(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number), value=1, ex_sec=TimeIntervals.SECOND_ONE)
        return redis_get(key=redis_key)
    elif delete:
        redis_delete(key=redis_key)
        redis_delete(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number))
    elif set_game:
        redis_set(key=redis_key, value=set_game)
        redis_delete(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number))
    elif release:
        redis_delete(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number))


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


# INFO. Протестировано ✅
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


# INFO. Протестировано ✅
async def __game_drop_move_indexes(
    game: dict[str, Any],
    message: Message,
) -> None:
    id_telegram: str = str(message.from_user.id)
    player_index: int = game['players_sleeping_order'].index(id_telegram)
    game['players_sleeping_order'].pop(player_index)
    game['players'].pop(id_telegram)

    # INFO. После окончания каждого раунда указатели будут сдвинуты на +1
    #       в функции __process_in_game_end_round.
    if player_index > game['sleeper_index']:
        if player_index < game['supervisor_index']:
            game['supervisor_index'] -= 1
        elif player_index == game['supervisor_index']:
            if game['supervisor_index'] > len(game['players_sleeping_order']) - 1:
                game['supervisor_index'] = 0
            await __notify_supervisor(chat_id=game['players_sleeping_order'][game['supervisor_index']])

    elif player_index <= game['sleeper_index']:
        game['sleeper_index'] -= 1
        if game['supervisor_index'] == player_index == 0:
            await __notify_supervisor(chat_id=game['players_sleeping_order'][game['supervisor_index']])
        else:
            game['supervisor_index'] -= 1
        # INFO. Проверка, что ушел сновидец, нужно сверить со старым индексом.
        if player_index == game['sleeper_index'] + 1:
            await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
            await __process_in_game_end_round(skip_results=True)

    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


# INFO. Протестировано ✅
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


# INFO. Протестировано ✅
def __get_players_sleeping_order(players: list[str]) -> list[str]:
    shuffle(players)
    return players


# INFO. Протестировано ✅
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
            'Также в этом раунде ты — Хранитель сна. Ты следишь за тем, как '
            'сновидец проходит свой путь, и видишь всё: правду, ложь, сомнения и колебания. '
            'Отмечай верно или ошибочно были названы сновидцем слова, раздавай штрафные очки, '
            'когда кто-то нарушает законы царства снов. И не забывай — ты тоже играешь.'
        )


async def __notify_supervisor(chat_id: int) -> None:
    """Уведомляет Хранителя сна о его роли."""
    await bot.send_message(
        chat_id=chat_id,
        text=__get_role_description(role=GameRoles.SUPERVISOR),
        reply_markup=KEYBOARD_LOBBY_SUPERVISOR,
    )



# TODO: Доделать
async def __process_in_game_end_round(
    game_number: str,
    skip_results: bool = False,
) -> None:
    """Завершает раунд."""
    game: dict[str, Any] = await process_game_in_redis(game_number, get=True)
    if not skip_results:
        __set_round_achievements(game=game)
        __set_round_points(game=game)

    if game['sleeper_index'] == len(game['players_sleeping_order']) - 1:
        await __process_in_game_end_game(game_number=game['number'])

    game['sleeper_index'] += 1
    if game['supervisor_index'] == len(game['players_sleeping_order']) - 1:
        game['supervisor_index'] = 0
    else:
        game['supervisor_index'] += 1

    game['status'] = GameStatus.PREPARE_NEXT_ROUND
    game['round_correct_count'] = 0
    game['round_incorrect_count'] = 0
    game['round_correct_words'] = []

    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
    await send_game_roles_messages(game=game)
    await __process_in_game_start_round(game=game)



async def __send_new_word(game: dict[str, Any]) -> None:
    """Отправляет новую карточку слова игрокам и смещает индекс карточки в игре."""

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
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


# INFO. Протестировано ✅
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


# INFO. Протестировано ✅
def __set_round_achievements(
    game: dict[str, Any],
):
    """Выдает достижения за раунд."""
    for data in game['players'].values():
        if data['role'] != GameRoles.SLEEPER:
            continue

        if game['round_correct_count'] == 0:
            data['achievements']['nightmare'] = 1
        elif (
            game['round_correct_count'] >= 4
            and
            game['round_incorrect_count'] == 0
            and
            game['round_user_retell_dream_correct']
        ):
            data['achievements']['dream_master'] = 1


# INFO. Протестировано ✅
def __set_round_points(
    game: dict[str, Any],
):
    """Подсчитывает очки за раунд."""
    if game['round_incorrect_count'] == game['round_correct_count']:
        sandman_points: int = game['round_correct_count'] + 2
    else:
        answers_balance: int = abs(game['round_correct_count'] - game['round_incorrect_count'])
        if answers_balance == 1:
            sandman_points: int = max(game['round_correct_count'], game['round_incorrect_count'])
        else:
            sandman_points: int = min(game['round_correct_count'], game['round_incorrect_count'])

    sleeper_points: int = game['round_correct_count']
    if game['round_user_retell_dream_correct']:
        sleeper_points += 2

    for data in game['players'].values():
        if data['role'] == GameRoles.BUKA:
            data['statistic']['top_score_buka'] += game['round_incorrect_count']
        elif data['role'] == GameRoles.FAIRY:
            data['statistic']['top_score_fairy'] += game['round_correct_count']
        elif data['role'] == GameRoles.SANDMAN:
            data['statistic']['top_score_sandman'] += sandman_points
        elif data['role'] == GameRoles.SLEEPER:
            data['statistic']['top_score_sleeper'] += sleeper_points
