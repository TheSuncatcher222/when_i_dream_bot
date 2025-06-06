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
from apscheduler.jobstores.base import JobLookupError

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
    RedisKeys,
    async_session_maker,
)
from app.src.models.user import User
from app.src.models.user_achievement import UserAchievement
from app.src.models.user_statistic import UserStatistic
from app.src.scheduler.scheduler import (
    SchedulerJobNames,
    scheduler,
)
from app.src.utils.image import (
    get_role_image_cards,
    get_shuffled_words_cards,
)
from app.src.utils.message import (
    MessagesEvents,
    delete_messages_list,
    set_user_messages_to_delete,
    delete_user_messages,
)
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    make_row_keyboard,
    KEYBOARD_HOME,
    KEYBOARD_LOBBY_SUPERVISOR,
    KEYBOARD_LOBBY_SUPERVISOR_IN_GAME,
    KEYBOARD_YES_NO,
    KEYBOARD_LOBBY_SUPERVISOR_IN_GAME_RETELL,
    KEYBOARD_LOBBY_SUPERVISOR_IN_GAME_RETELL_FAIL,
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
#     'card_index: 0,
#
#     'players': {
#         '12345678': {
#             'name': 'Иван Иванов (@iVan)',
#             'chat_id': 87654321,
#             'id: 1,
#
#             'role': 'buka',
#             'statistic': {
#                   'top_penalties': 0,
#                   'top_score_buka': 0,
#                   'top_score_fairy': 0,
#                   'top_score_sandman': 0,
#                   'top_score_dreamer': 0,
#             },
#             'achievements': {},
#         },
#         ...
#     },
#
#     'players_dreaming_order': [12345678, 56781234, ...],
#     'dreamer_index': 0,
#     'supervisor_index': 1,
#
#     'last_check_answer_datetime': '2021-11-01 00:00:00.000000',
#     'round_correct_count': 0,
#     'round_incorrect_count': 0,
#     'round_user_retell_dream_correct': True,
#     'round_correct_words': ['word1', 'word2', 'word3', ...],
# }

# INFO. Словарь с картинками для игры (хранится в Redis):
# # TODO. Можно ограничить количество карт. В игре участвует N игроков,
#         в раунде используется не более N слов, тогда нужно N*M слов.
# 'game_cards_ids': {
#     0: ('word_name', 1234),
#     1: ('word_name, 1235),
#     ...
# },


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


# -----------------------------------------------------------------------------
# INFO. Функции для подготовки игры (лобби).
# -----------------------------------------------------------------------------


NUMS_EMOJI: dict[str, str] = {
    1: '1️⃣',
    2: '2️⃣',
    3: '3️⃣',
    4: '4️⃣',
    5: '5️⃣',
    6: '6️⃣',
    7: '7️⃣',
    8: '8️⃣',
    9: '9️⃣',
    10: '🔟',
}


def form_lobby_host_message(game: dict[str, Any]) -> str:
    """Формирует сообщение для хоста лобби."""
    return '\n'.join(
        f'{NUMS_EMOJI[i + 1]} {player["name"]}'
        for i, player in enumerate(game['players'].values())
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

    async def __set_players_last_game_datetime(
        id_telegram: str | int,
        datetime_now: datetime,
    ) -> None:
        """Обновляет время последней игры у игрока."""
        async with async_session_maker() as session:
            await user_statistic_crud.update_by_user_id_telegram(
                user_id_telegram=id_telegram,
                obj_data={'last_game_datetime': datetime_now},
                session=session,
                perform_check_unique=False,
            )

    async def __send_game_start_message(chat_id: int) -> None:
        """Задача по отправке сообщения игроку в начале игры."""
        await delete_user_messages(chat_id=chat_id, event_key=MessagesEvents.IN_LOBBY)

        messages_ids: list[int] = []
        for t in (
            'Твое путешествие начинается через..',
            '3..',
            '2..',
            '1..',
            'Сейчас! ✨',
        ):
            message: Message = await bot.send_message(
                chat_id=chat_id,
                text=t,
                reply_markup=ReplyKeyboardRemove(),
            )
            messages_ids.append(message.message_id)
            await asyncio_sleep(2)
        await delete_messages_list(chat_id=chat_id, messages_ids=messages_ids)

    datetime_now: datetime = datetime.now(tz=Timezones.MOSCOW)
    tasks: list[Task] = [
        asyncio_create_task(__send_game_start_message(chat_id=data['chat_id']))
        for data in game['players'].values()
    ] + [
        asyncio_create_task(
            __set_players_last_game_datetime(
                id_telegram=data['chat_id'],
                datetime_now=datetime_now,
            ),
        )
        for data in game['players'].values()
    ]
    await asyncio_gather(*tasks)


async def setup_game_data(game: dict[str, Any]) -> None:
    """Подготавливает данные для игры."""
    for k in ('host_chat_id', 'host_lobby_message_id'):
        del game[k]
    game_cards_ids: list[str, str] = await get_shuffled_words_cards()
    redis_set(
        key=RedisKeys.GAME_WORDS.format(number=game['number']),
        value=game_cards_ids,
    )
    game.update(
        {
            'status': GameStatus.PREPARE_NEXT_ROUND,

            'card_index': 0,

            'players_dreaming_order': __get_players_dreaming_order(players=list(game['players'].keys())),
            'dreamer_index': 0,
            'supervisor_index': 1,

            'last_check_answer_datetime': '2001-01-01 00:00:00.000000',
            'round_correct_count': 0,
            'round_incorrect_count': 0,
            'round_user_retell_dream_correct': False,
            'round_correct_words': [],
        },
    )
    for data in game['players'].values():
        data.update(
            {
                'statistic': {
                    'top_penalties': 0,
                    'top_score_buka': 0,
                    'top_score_dreamer': 0,
                    'top_score_fairy': 0,
                    'top_score_sandman': 0,
                },
                'achievements': {},
            },
        )
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
        return await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    # INFO. Подтверждение действий.
    if state_value == GameForm.in_game_destroy_game:
        return await process_in_game_destroy_game_confirm(game=game, message=message, state=state)
    elif state_value == GameForm.in_game_drop_game:
        return await __process_in_game_drop_game_confirm(game=game, message=message, state=state)
    elif state_value == GameForm.in_game_set_penalty:
        return await __process_in_game_set_penalty_confirm(game=game, message=message, state=state)
    elif game['status'] == GameStatus.WAIT_DREAMER_RETAILS:
        return await __process_in_game_end_round_ask_for_retail_confirm(game=game, message=message)

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
        await __process_in_game_start_round(game=game, message=message)

    # INFO. Выход из / удаление из игры.
    elif message.text == RoutersCommands.GAME_DESTROY:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        await __process_in_game_destroy_game(message=message, state=state)
    elif message.text == RoutersCommands.GAME_DROP:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        await __process_in_game_drop_game(message=message, state=state)
    elif message.text == RoutersCommands.HOME:
        await __process_in_game_home(game=game, message=message, state=state)


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
    if game['status'] in (GameStatus.FINISHED, GameStatus.IN_LOBBY):
        if message.text == RoutersCommands.HOME:
            return True

    # INFO. Может придти от любого игрока.
    elif message.text == RoutersCommands.GAME_DROP:
        return True


    # INFO. Может придти только от "supervisor" игрока, не содержит KEYBOARD команд.
    elif (
        game['status'] == GameStatus.WAIT_DREAMER_RETAILS
        and
        str(message.from_user.id) == game['players_dreaming_order'][game['supervisor_index']]
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
        if str(message.from_user.id) == game['players_dreaming_order'][game['supervisor_index']]:
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
    answer: Message = await message.answer(
        text='Ты действительно хочешь всех разбудить?',
        reply_markup=KEYBOARD_YES_NO,
    )
    await set_user_messages_to_delete(
        event_key=MessagesEvents.GAME_DESTROY,
        messages=[message, answer],
    )


async def process_in_game_destroy_game_confirm(
    message: Message,
    state: FSMContext,
    game: dict[str, Any] | None = None,
    from_lobby: bool = False,
    from_drop_game: bool = False,
) -> None:
    """Обрабатывает результат ответа на команду "Главное меню"."""

    # TODO. Надо записать answer для удаления. Сейчас удаляется через range() в callback.
    async def __send_destroy_game_message(
        data: dict[str, Any],
        supervisor_chat_id: int,
        from_drop_game: bool,
    ) -> None:
        """Задача по уведомлению игроков о принудительном завершении игры."""
        if from_drop_game:
            text: str = __choose_drop_game_text(is_run_out_of_players=True)
        elif data['chat_id'] == str(supervisor_chat_id):
            text: str = 'Сон был прерван..'
        else:
            text: str = 'Хранитель сна прервал твое путешествие..'
        answer: Message = await bot.send_message(
            chat_id=data['chat_id'],
            text=text,
            reply_markup=KEYBOARD_HOME,
        )
        await set_user_messages_to_delete(
            event_key=MessagesEvents.GAME_DESTROY,
            messages=[answer],
        )

    # INFO. Такое приходит из лобби.
    if not game:
        game: dict[str, Any] = await process_game_in_redis(message=message, get=True)

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=(message.message_id,),
    )

    # INFO. Из лобби или когда в игре не осталось людей - подтверждение не требуется.
    if not from_lobby and not from_drop_game:
        if message.text not in (RoutersCommands.YES, RoutersCommands.NO):
            return await process_game_in_redis(redis_key=game['redis_key'], release=True)
        elif message.text == RoutersCommands.NO:
            await state.set_state(state=GameForm.in_game)
            # INFO. Затрется reply-клавиатура, надо удалить роль и выслать заново.
            for k in (MessagesEvents.GAME_DESTROY, MessagesEvents.ROLE):
                await delete_user_messages(chat_id=message.chat.id, event_key=k)
            return await __send_game_role_message(
                data={
                    'role': game['players'][str(message.from_user.id)]['role'],
                    'chat_id': str(message.chat.id),
                },
                roles_images=await get_role_image_cards(),
                supervisor_id_telegram=game['players_dreaming_order'][game['supervisor_index']],
            )

    if from_drop_game:
        game['players'].pop(str(message.from_user.id), None)
    game['status'] = GameStatus.FINISHED
    await delete_user_messages(chat_id=message.chat.id, event_key=MessagesEvents.GAME_DESTROY)
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
    process_avaliable_game_numbers(remove_number=game['number'])

    if not from_lobby:
        try:
            scheduler.remove_job(job_id=SchedulerJobNames.GAME_END_ROUND.format(number=game['number']))
        except JobLookupError:
            pass

    # INFO. Даже если человек в лобби, нужно поставить состояние GameForm.in_game,
    #       чтобы он смог обработать команду "RoutersCommands.HOME".
    await state.set_state(state=GameForm.in_game)

    tasks: tuple[Task] = (
        asyncio_create_task(
            __send_destroy_game_message(
                data=data,
                supervisor_chat_id=message.chat.id,
                from_drop_game=from_drop_game,
            ),
        )
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)


async def __process_in_game_drop_game(
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Выйти из игры"."""
    await state.set_state(state=GameForm.in_game_drop_game)
    answer: Message = await message.answer(
        text=(
            'Ты действительно хочешь проснуться?'
            '\n\n'
            '❗️Учти, что в этом случае тебе в статистику будет засчитан '
            'выход из игры! Если вы все хотите проснуться - нужно, чтобы '
            f'Хранитель сна нажал "{RoutersCommands.GAME_DESTROY}" - '
            'в этом случае статистика не будет испорчена ни у кого.'
        ),
        reply_markup=KEYBOARD_YES_NO,
    )
    await set_user_messages_to_delete(
        event_key=MessagesEvents.GAME_DROP,
        messages=[message, answer],
    )


# TODO: Доделать
async def __process_in_game_drop_game_confirm(
    game: dict[str, Any],
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает результат ответа на команду "Покинуть игру"."""
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    if message.text not in (RoutersCommands.YES, RoutersCommands.NO):
        return

    if message.text == RoutersCommands.NO:
        await state.set_state(state=GameForm.in_game)
        # INFO. Затрется reply-клавиатура, надо удалить роль и выслать заново.
        for k in (MessagesEvents.GAME_DROP, MessagesEvents.ROLE):
            await delete_user_messages(chat_id=message.chat.id, event_key=k)
        return await __send_game_role_message(
            data={
                'role': game['players'][str(message.from_user.id)]['role'],
                'chat_id': str(message.chat.id),
            },
            roles_images=await get_role_image_cards(),
            supervisor_id_telegram=game['players_dreaming_order'][game['supervisor_index']],
        )

    async with async_session_maker() as session:
        # TODO. Оптимизировать в один запрос.
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
        current_statistic: UserStatistic = await user_statistic_crud.retrieve_by_user_id(
            user_id=user.id,
            session=session,
        )
        current_statistic.total_quits = current_statistic.total_quits + 1
        await session.commit()

    # INFO. -1 так как из game игрок еще не был удален.
    # TODO. Удалить игрока из game в этом месте, а не в функциях ниже.
    if len(game['players']) - 1 < GameParams.PLAYERS_MIN:
        await process_in_game_destroy_game_confirm(message=message, state=state, game=game, from_drop_game=True)
    else:
        await __game_drop_move_indexes(game=game, message=message)

    await state.clear()
    answer: Message = await message.answer(
        text=__choose_drop_game_text(is_leave=True),
        reply_markup=ReplyKeyboardRemove(),
    )
    await delete_user_messages(chat_id=message.chat.id, all_event_keys=True)
    await asyncio_sleep(5)
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(answer.message_id,))
    await command_start(message=message)


async def __process_in_game_set_penalty(
    game: dict[str, Any],
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Пенальти"."""
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    rows: list[tuple[str]] = (
        [(RoutersCommands.CANCEL,)]
        +
        [(player['name'],) for player in game['players'].values()]
    )
    answer: Message = await message.answer(
        text='Кто нарушил правила мира снов?',
        reply_markup=make_row_keyboard(rows=rows),
    )
    await set_user_messages_to_delete(
        event_key=MessagesEvents.SET_PENALTY,
        messages=[answer],
    )
    await state.set_state(state=GameForm.in_game_set_penalty)

    redis_set(key=RedisKeys.GAME_SET_PENALTY.format(number=game['number']), value=1)
    await process_game_in_redis(redis_key=game['redis_key'], release=True)


# TODO. Зарефакторить функцию.
async def __process_in_game_set_penalty_confirm(
    game: dict[str, Any],
    message: Message,
    state: FSMContext,
):
    """Обрабатывает результат ответа на команду "Выдать штраф"."""

    async def __exit(game: dict[str, Any]) -> None:
        redis_delete(key=RedisKeys.GAME_SET_PENALTY.format(number=game['number']))
        await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

        await state.set_state(state=GameForm.in_game)

        await delete_user_messages(chat_id=message.chat.id, event_key=MessagesEvents.SET_PENALTY)
        # INFO. Затрется reply-клавиатура, надо удалить слово и выслать заново.
        return await __send_new_word_to_player(
            id_telegram=str(message.from_user.id),
            data=game['players'][str(message.from_user.id)],
            game=game,
            game_cards_ids=redis_get(key=RedisKeys.GAME_WORDS.format(number=game['number'])),
            send_supervisor_keyboard=True,
        )

    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    if message.text == RoutersCommands.CANCEL:
        return await __exit(game=game)

    penalty_id_telegram: str | None = None
    for id_telegram, data in game['players'].items():
        if data['name'] == message.text:
            penalty_id_telegram: str = id_telegram
            break

    if penalty_id_telegram:
        game['players'][penalty_id_telegram]['statistic']['top_penalties'] += 1
        await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
        return await __exit(game=game)
    else:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)


# TODO. Добавить для слов глобальную статистику:
#       количество правильных/неправильных угадываний.
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
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    # INFO. Проверка от дабл-кликов.
    datetime_now: datetime = datetime.now()
    last_check_answer_datetime: datetime = datetime.fromisoformat(game['last_check_answer_datetime'])
    if datetime_now < last_check_answer_datetime + timedelta(seconds=5):
        return
    game['last_check_answer_datetime'] = datetime_now.strftime('%Y-%m-%d %H:%M:%S.%f')

    if is_correct:
        game['round_correct_count'] += 1
        card_ids: list[str, str] = redis_get(key=RedisKeys.GAME_WORDS.format(number=game['number']))
        game['round_correct_words'].append(card_ids[game['card_index']][0])
    else:
        game['round_incorrect_count'] += 1
    await __send_new_word(game=game)


async def __process_in_game_start_round(
    game: dict[str, Any],
    message: Message,
) -> None:
    """Обрабатывает команду "Начать раунд"."""
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    game['status'] = GameStatus.ROUND_IS_STARTED
    answer: Message = await bot.send_message(
        chat_id=game['players_dreaming_order'][game['supervisor_index']],
        text='Раунд начался!',
        reply_markup=KEYBOARD_LOBBY_SUPERVISOR_IN_GAME,
    )
    await set_user_messages_to_delete(
        event_key=MessagesEvents.ROUND_STARTED,
        messages=[answer],
    )

    await __send_new_word(game=game)

    scheduler.add_job(
        id=SchedulerJobNames.GAME_END_ROUND.format(number=game['number']),
        func=__process_in_game_end_round_ask_for_retail,
        trigger='date',
        next_run_time=datetime.now(tz=Timezones.MOSCOW) + timedelta(minutes=2),
        kwargs={'redis_key': game['redis_key']},
    )


async def __process_in_game_home(
    game: dict[str, Any],
    message: Message,
    state: FSMContext,
) -> None:
    """Обрабатывает команду "Домой"."""
    game['players'].pop(str(message.from_user.id), None)
    if len(game['players']) == 0:
        await process_game_in_redis(redis_key=game['redis_key'], delete=True)
        process_avaliable_game_numbers(remove_number=game['number'])
    else:
        if game['status'] == GameStatus.IN_LOBBY:
            if len(game['players']) < GameParams.PLAYERS_MIN:
                process_avaliable_game_numbers(add_number=game['number'])
            await bot.edit_message_text(
                chat_id=game['host_chat_id'],
                message_id=game['host_lobby_message_id'],
                text=form_lobby_host_message(game=game),
            )
        await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))
    await delete_user_messages(chat_id=message.chat.id, all_event_keys=True)
    await state.clear()
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
        answer: Message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=KEYBOARD_HOME,
        )
        await set_user_messages_to_delete(
            event_key=MessagesEvents.GAME_RESULTS,
            messages=[answer],
        )

    async def __process_in_game_end_game_update_user_db(
        data: dict[str, Any],
    ) -> None:
        """Обновляет статистику и достижения игрока."""
        async with async_session_maker() as session:
            current_statistic: UserStatistic = await user_statistic_crud.retrieve_by_user_id(
                user_id=data['id'],
                session=session,
            )
            for k, v in data['statistic'].items():
                if hasattr(current_statistic, k) and isinstance(v, (int, float)):
                    setattr(current_statistic, k, getattr(current_statistic, k) + v)

            current_achievement: UserAchievement = await user_achievement_crud.retrieve_by_user_id(
                user_id=data['id'],
                session=session,
            )
            for k, v in data['achievements'].items():
                if hasattr(current_achievement, k) and isinstance(v, (int, float)):
                    setattr(current_achievement, k, getattr(current_achievement, k) + v)

            await session.commit()

    def __set_game_achievements(game: dict[str, Any]) -> None:
        """Выдает достижения за игру."""
        keys: tuple[str] = (
            'top_penalties',
            'top_score',
            'top_score_buka',
            'top_score_dreamer',
            'top_score_fairy',
            'top_score_sandman',
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
                data['statistic']['top_score_dreamer'] +
                data['statistic']['top_score_fairy'] +
                data['statistic']['top_score_sandman'] -
                data['statistic']['top_penalties']
            )

        max_score: int = max((data['statistic'].get('top_score', 0) for data in game['players'].values()))
        if max_score == 0:
            return
        for data in game['players'].values():
            if data['statistic'].get('top_score', 0) == max_score:
                data['statistic']['total_wins'] = 1

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
                f'- очки за сновидца: {data["statistic"]["top_score_dreamer"]}\n'
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

    tasks: tuple[Task] = (
        asyncio_create_task(__process_in_game_end_game_update_user_db(data=data))
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)

    text: str = __get_results_text(game=game)
    tasks: tuple[Task] = (
        asyncio_create_task(
            __process_in_game_end_game_send_message(
                text=text,
                chat_id=data['chat_id'],
            ),
        )
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)


async def __process_in_game_end_round_ask_for_retail(redis_key: str) -> None:
    """Завершает раунд и просит сновидца пересказать сон."""

    async def __process_in_game_end_round_ask_for_retail_send_message(
        chat_id: str,
        text: str,
        game: dict[str, Any],
    ) -> None:
        """Задача по уведомлению игроков о просьбе сновидца пересказать сон."""
        if chat_id == game['players_dreaming_order'][game['dreamer_index']]:
            return

        await delete_user_messages(
            chat_id=chat_id,
            event_key=MessagesEvents.WORD,
        )

        answer: Message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=KEYBOARD_HOME,
        )
        messages_to_delete: list[Message] = [answer]
        if chat_id == game['players_dreaming_order'][game['supervisor_index']]:
            if game['round_correct_words']:
                reply_markup: ReplyKeyboardMarkup = KEYBOARD_LOBBY_SUPERVISOR_IN_GAME_RETELL
            else:
                reply_markup: ReplyKeyboardMarkup = KEYBOARD_LOBBY_SUPERVISOR_IN_GAME_RETELL_FAIL
            answer: Message = await bot.send_message(
                chat_id=chat_id,
                text='Верно ли сновидец пересказал свой сон?',
                reply_markup=reply_markup,
            )
            messages_to_delete.append(answer)
        await set_user_messages_to_delete(event_key=MessagesEvents.RETELL, messages=messages_to_delete)

    game: dict[str, Any] = await process_game_in_redis(redis_key=redis_key, get=True)
    await process_game_in_redis(redis_key=game['redis_key'], release=True)
    # INFO. Пока назначается пенальти - сообщения окончания раунда перебивают клавиатуру.
    while 1:
        if redis_check_exists(key=RedisKeys.GAME_SET_PENALTY.format(number=game['number'])):
            await asyncio_sleep(1)
            continue
        game: dict[str, Any] = await process_game_in_redis(redis_key=redis_key, get=True)
        break

    await delete_user_messages(
        chat_id=game['players_dreaming_order'][game['supervisor_index']],
        event_key=MessagesEvents.ROUND_STARTED,
    )

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
        words: str = '\n'.join(f'- {word}' for word in game['round_correct_words'])
        text += 'А вот и сами слова (т-с-с, не говори сновидцу!):\n' + words

    game['status'] = GameStatus.WAIT_DREAMER_RETAILS
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    tasks: tuple[Task] = (
        asyncio_create_task(
            __process_in_game_end_round_ask_for_retail_send_message(
                text=text,
                chat_id=data['chat_id'],
                game=game,
            ),
        )
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)


async def __process_in_game_end_round_ask_for_retail_confirm(
    game: dict[str, Any],
    message: Message,
) -> None:
    """Обрабатывает результат ответа на правильность пересказа сна сновидца."""

    async def __delete_retell_messages(chat_id: str) -> None:
        """Задача по удалению сообщений о пересказе сна сновидца."""
        await delete_user_messages(chat_id=chat_id, event_key=MessagesEvents.RETELL)

    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))
    tasks: tuple[Task] = (
        asyncio_create_task(__delete_retell_messages(chat_id=data['chat_id']))
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)

    if game['round_correct_words'] and message.text == RoutersCommands.WORD_CORRECT:
        game['round_user_retell_dream_correct'] = True
    else:
        game['round_user_retell_dream_correct'] = False
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
    await __process_in_game_end_round(redis_key=game['redis_key'])


# -----------------------------------------------------------------------------
# INFO. Общий функционал.
# -----------------------------------------------------------------------------


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

    # TODO. Посылать номер, чтобы не парсить. Подумать, как упростить интерфейс.
    # INFO. redis_key=src_lobby_{number}
    number: str = redis_key.split('_')[-1]
    if get or release:
        # INFO. Есть шанс, что несколько игроков одновременно получат данные
        #       игры в Redis и начнется состояние гонки.
        if release:
            redis_delete(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number))
        else:
            while 1:
                if redis_check_exists(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number)):
                    await asyncio_sleep(0.05)
                    continue
                break
            redis_set(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number), value=1, ex_sec=TimeIntervals.SECOND_ONE)
            return redis_get(key=redis_key)

    elif delete:
        redis_delete(key=redis_key)
        redis_delete(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number))
    elif set_game:
        redis_set(key=redis_key, value=set_game)
        redis_delete(key=RedisKeys.GAME_LOBBY_BLOCKED.format(number=number))


async def __send_game_role_message(
    data: dict[str, Any],
    roles_images: dict[str, str],
    supervisor_id_telegram: str,
):
    """Задача по отправке сообщения с ролью игроку."""
    # TODO. Дать возможность выхода из игры спящему.
    if data['role'] == GameRoles.DREAMER:
        reply_markup: ReplyKeyboardRemove = ReplyKeyboardRemove()
    else:
        reply_markup: ReplyKeyboardMarkup = KEYBOARD_HOME
    answer: Message = await bot.send_photo(
        chat_id=data['chat_id'],
        # TODO. Возможно стоит скрыть за спойлер.
        photo=roles_images[data['role']],
        caption=__get_role_description(role=data['role']),
        reply_markup=reply_markup,
    )
    messages: list[Message] = [answer]

    if data['chat_id'] == supervisor_id_telegram:
        messages.append(await __notify_supervisor(chat_id=data['chat_id']))

    await set_user_messages_to_delete(event_key=MessagesEvents.ROLE, messages=messages)



async def send_game_roles_messages(game: dict[str, Any]) -> None:
    """Отправляет сообщения игрокам с их ролями."""

    def __set_players_roles(game: dict[str, Any]) -> None:
        """Обновляет роли игроков в словаре игры "game"."""
        roles: list[str] = __get_players_roles(players_count=len(game['players']))
        shuffle(roles)

        i: int = 0
        for id_telegram, data in game['players'].items():
            if id_telegram == game['players_dreaming_order'][game['dreamer_index']]:
                data['role'] = GameRoles.DREAMER
            else:
                data['role'] = roles[i]
                i += 1

    __set_players_roles(game=game)
    roles_images: dict[str, str] = await get_role_image_cards()
    tasks: tuple[Task] = (
        asyncio_create_task(
            __send_game_role_message(
                data=data,
                roles_images=roles_images,
                supervisor_id_telegram=game['players_dreaming_order'][game['supervisor_index']],
            ),
        )
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)

    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


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
    id_telegram: str = str(message.from_user.id)
    player_index: int = game['players_dreaming_order'].index(id_telegram)
    game['players_dreaming_order'].pop(player_index)
    game['players'].pop(id_telegram)

    # INFO. После окончания каждого раунда указатели будут сдвинуты на +1
    #       в функции __process_in_game_end_round.
    if player_index > game['dreamer_index']:
        if player_index < game['supervisor_index']:
            game['supervisor_index'] -= 1
        elif player_index == game['supervisor_index']:
            if game['supervisor_index'] > len(game['players_dreaming_order']) - 1:
                game['supervisor_index'] = 0
            await __notify_supervisor(chat_id=game['players_dreaming_order'][game['supervisor_index']])

    elif player_index <= game['dreamer_index']:
        game['dreamer_index'] -= 1
        if game['supervisor_index'] == player_index == 0:
            await __notify_supervisor(chat_id=game['players_dreaming_order'][game['supervisor_index']])
        else:
            game['supervisor_index'] -= 1
        # INFO. Проверка, что ушел сновидец, нужно сверить со старым индексом.
        if player_index == game['dreamer_index'] + 1:
            await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
            await __process_in_game_end_round(redis_key=game['redis_key'], skip_results=True)

    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


def __get_players_roles(players_count: int) -> list[str]:
    """
    Формирует список ролей игроков в зависимости от количества.
    """
    # INFO. Заглушка, на всякий случай, если по среди процесса
    #       игрок выйдет из игры.
    if players_count < 4:
        fairy, buka, sandman = 1, 1, 1

    if players_count == 4:
        fairy, buka, sandman = 1, 1, 2
    elif players_count == 5:
        fairy, buka, sandman = 2, 1, 2
    elif players_count == 6:
        fairy, buka, sandman = 3, 2, 1
    elif players_count == 7:
        fairy, buka, sandman = 3, 2, 2
    elif players_count == 8:
        fairy, buka, sandman = 4, 3, 1
    elif players_count == 9:
        fairy, buka, sandman = 4, 3, 2
    elif players_count == 10:
        fairy, buka, sandman = 5, 4, 1
    return [GameRoles.FAIRY] * fairy + [GameRoles.BUKA] * buka + [GameRoles.SANDMAN] * sandman


def __get_players_dreaming_order(players: list[str]) -> list[str]:
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
    if role == GameRoles.DREAMER:
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


async def __notify_supervisor(chat_id: int) -> Message:
    """Уведомляет Хранителя сна о его роли."""
    return await bot.send_message(
        chat_id=chat_id,
        text=__get_role_description(role=GameRoles.SUPERVISOR),
        reply_markup=KEYBOARD_LOBBY_SUPERVISOR,
    )


# TODO: Доделать
async def __process_in_game_end_round(
    redis_key: str,
    skip_results: bool = False,
) -> None:
    """Завершает раунд."""

    async def __process_in_game_end_round_delete_roles(chat_id: str | int) -> None:
        await delete_user_messages(chat_id=chat_id, event_key=MessagesEvents.ROLE)

    game: dict[str, Any] = await process_game_in_redis(redis_key=redis_key, get=True)

    # TODO. Заменить на tuple везде.
    tasks: tuple[Task] = (
        asyncio_create_task(
            __process_in_game_end_round_delete_roles(chat_id=data['chat_id']),
        )
        for data in game['players'].values()
    )
    await asyncio_gather(*tasks)

    if not skip_results:
        __set_round_achievements(game=game)
        __set_round_points(game=game)

    if game['dreamer_index'] == len(game['players_dreaming_order']) - 1:
        return await __process_in_game_end_game(game=game)

    game['dreamer_index'] += 1
    if game['supervisor_index'] == len(game['players_dreaming_order']) - 1:
        game['supervisor_index'] = 0
    else:
        game['supervisor_index'] += 1

    game['status'] = GameStatus.PREPARE_NEXT_ROUND
    game['round_correct_count'] = 0
    game['round_incorrect_count'] = 0
    game['round_correct_words'] = []

    await send_game_roles_messages(game=game)
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


async def __send_new_word(game: dict[str, Any]) -> None:
    """Отправляет новую карточку слова игрокам и смещает индекс карточки в игре."""
    game['card_index'] += 1
    game_cards_ids: list[str, str] = redis_get(key=RedisKeys.GAME_WORDS.format(number=game['number']))
    tasks: tuple[Task] = (
        asyncio_create_task(
            __send_new_word_to_player(
                id_telegram=id_telegram,
                data=data,
                game=game,
                game_cards_ids=game_cards_ids,
            ),
        )
        for id_telegram, data in game['players'].items()
    )
    await asyncio_gather(*tasks)
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


async def __send_new_word_to_player(
    id_telegram: str,
    data: dict[str, Any],
    game: dict[str, Any],
    game_cards_ids: list[str, str],
    send_supervisor_keyboard: bool = False,
) -> None:
    """Задача по отправке новой карточки слова игроку."""
    if id_telegram == game['players_dreaming_order'][game['dreamer_index']]:
        return

    await delete_user_messages(
        chat_id=data['chat_id'],
        event_key=MessagesEvents.WORD,
    )
    if send_supervisor_keyboard:
        answer: Message = await bot.send_photo(
            chat_id=data['chat_id'],
            photo=game_cards_ids[game['card_index']][1],
            reply_markup=KEYBOARD_LOBBY_SUPERVISOR_IN_GAME,
        )
    else:
        answer: Message = await bot.send_photo(
            chat_id=data['chat_id'],
            photo=game_cards_ids[game['card_index']][1],
        )
    await set_user_messages_to_delete(
        event_key=MessagesEvents.WORD,
        messages=(answer,),
    )


def __set_round_achievements(
    game: dict[str, Any],
):
    """Выдает достижения за раунд."""
    for data in game['players'].values():
        if data['role'] != GameRoles.DREAMER:
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

    dreamer_points: int = game['round_correct_count']
    if game['round_user_retell_dream_correct']:
        dreamer_points += 2

    for data in game['players'].values():
        if data['role'] == GameRoles.BUKA:
            data['statistic']['top_score_buka'] += game['round_incorrect_count']
        elif data['role'] == GameRoles.FAIRY:
            data['statistic']['top_score_fairy'] += game['round_correct_count']
        elif data['role'] == GameRoles.SANDMAN:
            data['statistic']['top_score_sandman'] += sandman_points
        elif data['role'] == GameRoles.DREAMER:
            data['statistic']['top_score_dreamer'] += dreamer_points
