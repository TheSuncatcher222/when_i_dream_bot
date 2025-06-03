from asyncio import (
    Task,
    gather as asyncio_gather,
    sleep as asyncio_sleep,
)
from datetime import datetime
from random import choices
from typing import Any

from aiogram import (
    Router,
    F,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.src.config.config import Timezones
from app.src.crud.user import user_crud
from app.src.crud.user_statistic import user_statistic_crud
from app.src.database.database import (
    AsyncSession,
    RedisKeys,
    async_session_maker,
)
from app.src.models.user import User
from app.src.utils.game import (
    GameForm,
    form_lobby_host_message,
    process_avaliable_game_numbers,
    process_in_game,
    process_in_game_destroy_game_confirm,
    process_game_in_redis,
    send_game_roles_messages,
    send_game_start_messages,
    setup_game_data,
)
from app.src.utils.message import delete_messages_list
from app.src.utils.redis_app import (
    redis_check_exists,
    redis_set,
)
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    KEYBOARD_LOBBY_HOST,
)
from app.src.validators.game import (
    GameParams,
    GameStatus,
)


router: Router = Router()


@router.message(F.text == RoutersCommands.GAME_CREATE)
async def command_game_create(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Инициализирует создание игрового лобби.
    """
    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[user.message_main_last_id, message.message_id],
    )

    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
    await __create_lobby(user=user, message=message)

    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    await state.set_state(state=GameForm.in_lobby)
    # INFO. Разделено на 2 части, так как нельзя редактировать сообщение,
    #       к которому привязана reply-клавиатура.
    await message.answer(
        text=(
            'Приветствую, капитан! Ты готов отправиться со своей командой в новое '
            'путешествие по миру снов? Отлично! Игра успешно создана!\n'
            f'Номер: {game['number']}\n'
            f'Пароль: {game['password']}'
        ),
        reply_markup=KEYBOARD_LOBBY_HOST,
    )
    answer: Message = await message.answer(text=form_lobby_host_message(game=game))

    game['host_lobby_message_id'] = answer.message_id
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


@router.message(GameForm.in_lobby)
async def start_game(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == RoutersCommands.GAME_DROP:
        return await process_in_game_destroy_game_confirm(
            message=message,
            state=state,
            from_lobby=True,
        )

    if message.text != RoutersCommands.GAME_START:
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )
    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    if not await __validate_players_count(game=game, message=message):
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        return

    await state.set_state(state=GameForm.in_game)
    process_avaliable_game_numbers(remove_number=game['number'])

    await setup_game_data(game=game)
    await send_game_start_messages(game=game)
    await send_game_roles_messages(game=game)
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    async with async_session_maker() as session:
        datetime_now: datetime = datetime.now(tz=Timezones.MOSCOW)
        tasks: list[Task] = [
            __set_players_last_game_datetime(
                id_telegram=k,
                datetime_now=datetime_now,
                session=session,
            )
            for k in game['players']
        ]
        await asyncio_gather(*tasks, return_exceptions=True)
        await session.commit()


@router.message(
    StateFilter(
        GameForm.in_game,
        GameForm.in_game_destroy_game,
        GameForm.in_game_drop_game,
        GameForm.in_game_set_penalty,
    ),
)
async def in_game(
    message: Message,
    state: FSMContext,
) -> None:
    return await process_in_game(
        message=message,
        state=state,
    )


async def __create_lobby(
    user: User,
    message: Message,
) -> str:
    """Создает лобби и сохраняет в Redis."""
    while 1:
        number: str = ''.join(choices('0123456789', k=4))
        key: str = RedisKeys.GAME_LOBBY.format(number=number)
        if redis_check_exists(key=key):
            continue
        break

    redis_set(key=RedisKeys.USER_GAME_LOBBY_NUMBER.format(id_telegram=str(user.id_telegram)), value=number)
    await process_game_in_redis(
        redis_key=key,
        set_game={
            'number': number,
            'password': ''.join(choices('0123456789', k=4)),
            'redis_key': key,
            'status': GameStatus.IN_LOBBY,
            'host_chat_id': message.chat.id,
            'players': {
                str(user.id_telegram): {
                    'name': user.get_full_name(),
                    'id': user.id,
                    'chat_id': str(message.chat.id),
                },
            },
        },
    )
    process_avaliable_game_numbers(add_number=number)


async def __validate_players_count(
    game: dict[str, Any],
    message: Message,
) -> bool:
    if GameParams.PLAYERS_MIN <= len(game['players']) <= GameParams.PLAYERS_MAX:
        return True

    answer: Message = await message.answer(
        text=(
            f'Для начала путешествия необходимо от {GameParams.PLAYERS_MIN} '
            f'до {GameParams.PLAYERS_MAX} сновидцев.'
        ),
    )
    await asyncio_sleep(2)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id, answer.message_id],
    )
    return False


async def __set_players_last_game_datetime(
    id_telegram: str | int,
    datetime_now: datetime,
    session: AsyncSession,
) -> None:
    """Обновляет время последней игры у игрока."""
    await user_statistic_crud.update_by_user_id_telegram(
        obj_id_telegram=id_telegram,
        obj_data={'last_game_datetime': datetime_now},
        session=session,
        perform_check_unique=False,
        perform_commit=False,
    )
