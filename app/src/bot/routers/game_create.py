from asyncio import sleep as asyncio_sleep
from random import choices
from typing import Any

from aiogram import (
    Router,
    F,
)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.src.crud.user import user_crud
from app.src.database.database import (
    async_session_maker,
    RedisKeys,
)
from app.src.models.user import User
from app.src.utils.game import (
    GameForm,
    form_lobby_host_message,
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
from app.src.validators.game import GameParams

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
    await __create_lobby(user=user, message=message)

    await state.set_state(state=GameForm.in_lobby)
    await message.answer(
        text=form_lobby_host_message(message=message),
        reply_markup=KEYBOARD_LOBBY_HOST,
    )


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

    game: dict[str, Any] = process_game_in_redis(message=message, get=True)
    if not await __validate_players_count(game=game, message=message):
        return

    await state.set_state(state=GameForm.in_game)
    await setup_game_data(game=game)
    await send_game_start_messages(game=game)
    await send_game_roles_messages(game=game)


@router.message(
    GameForm.in_game,
    GameForm.in_game_destroy_game,
    GameForm.in_game_drop_game,
    GameForm.in_game_set_penalty,
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
    process_game_in_redis(
        redis_key=key,
        set_game={
            'redis_key': key,
            'number': number,
            'password': ''.join(choices('0123456789', k=4)),
            'host_user_id_telegram': user.id_telegram,
            'host_chat_id': message.chat.id,
            'players': {
                user.id_telegram: {
                    'name': user.get_full_name(),
                    'chat_id': message.chat.id,
                },
            },
        },
    )


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
