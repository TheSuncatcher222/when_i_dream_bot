from asyncio import sleep as asyncio_sleep
from random import (
    choices,
)
from typing import Any

from aiogram import (
    Router,
    F,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import (
    StatesGroup,
    State,
)
from aiogram.types import Message

from app.src.bot.bot import bot
from app.src.config.config import TimeIntervals
from app.src.crud.user import user_crud
from app.src.database.database import (
    async_session_maker,
    RedisKeys,
)
from app.src.models.user import User
from app.src.utils.game import (
    form_lobby_host_message,
    process_in_game,
    send_game_roles_messages,
    send_game_start_messages,
    setup_game_data,
)
from app.src.utils.message import delete_messages_list
from app.src.utils.redis_app import (
    redis_check_exists,
    redis_delete,
    redis_get,
    redis_set,
)
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    KEYBOARD_HOME,
    KEYBOARD_LOBBY_HOST,
)
from app.src.validators.game import GameParams

router: Router = Router()


class Form(StatesGroup):
    """
    Состояния формы роутера.
    """

    in_lobby = State()
    in_game = State()

    # TODO. Будет много сообщений, лучше вести список тех, что надо удалить.
    _init_message_id: int
    _game_number: int


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
    number: str = await __create_lobby(user=user, message=message)

    await state.update_data(
        _init_message_id=message.message_id,
        _game_number=number,
    )
    await state.set_state(state=Form.in_lobby)

    await message.answer(
        text=form_lobby_host_message(game_number=number),
        reply_markup=KEYBOARD_LOBBY_HOST,
    )


@router.message(Form.in_lobby)
async def start_game(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == RoutersCommands.GAME_DROP:
        return await __destroy_lobby(state=state)

    if message.text != RoutersCommands.GAME_START:
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id],
        )

    # TODO. Учесть, вдруг игра будет удален из Redis.
    state_data: dict[str, Any] = await state.get_data()
    game: dict[str, Any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=state_data['_game_number']))
    if not await __validate_players_count(game=game):
        return

    await state.set_state(state=Form.in_game)
    await __start_game(game=game)


@router.message(Form.in_game)
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
    redis_set(
        key=key,
        value={
            'host_user_id_telegram': user.id_telegram,
            'host_chat_id': message.chat.id,
            'password': ''.join(choices('0123456789', k=4)),
            'players': {
                user.id_telegram: {
                    'name': user.get_full_name(),
                    'chat_id': message.chat.id,
                },
            },
        },
        ex_sec=TimeIntervals.SECONDS_IN_1_DAY,
    )
    return number


async def __destroy_lobby(
    state: FSMContext,
) -> None:
    """Удаляет лобби."""
    state_data: dict[str, Any] = await state.get_data()
    game: dict[str, Any] = redis_get(key=RedisKeys.GAME_LOBBY.format(number=state_data['_game_number']))
    for player in game['players'].values():
        await bot.send_message(
            chat_id=player['chat_id'],
            text='Игра была отменена.',
            reply_markup=KEYBOARD_HOME,
        )
    redis_delete(key=RedisKeys.GAME_LOBBY.format(number=state_data['_game_number']))
    await state.clear()


async def __start_game(game: dict) -> None:
    """Начинает игру."""
    await setup_game_data(game=game)
    await send_game_start_messages(game=game)
    await send_game_roles_messages(game=game)


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
