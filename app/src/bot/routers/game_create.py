from asyncio import sleep as asyncio_sleep
from random import choices
from typing import Any

from aiogram import (
    Router,
    F,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.src.config.config import settings
from app.src.crud.user import user_crud
from app.src.database.database import (
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
    send_users_ordering_message,
    setup_game_data,
)
from app.src.utils.message import (
    MessagesEvents,
    delete_messages_list,
    set_user_messages_to_delete,
)
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
        messages_ids=(user.message_main_last_id, message.message_id),
    )

    game: dict[str, Any] = await __create_lobby(user=user, message=message)
    await state.set_state(state=GameForm.in_lobby)

    # INFO. Разделено на 2 части, так как нельзя редактировать сообщение,
    #       к которому привязана reply-клавиатура.
    answer_1: Message = await message.answer(
        text=(
            'Приветствую, капитан! Ты готов отправиться со своей командой в новое '
            'путешествие по миру снов? Отлично! Игра успешно создана!\n'
            f'Номер: {game['number']}\n'
            f'Пароль: {game['password']}'
            '\n\n'
            'Проверь список сновидцев ниже: когда вся команда будет в сборе, '
            f'жми "{RoutersCommands.GAME_START}". Желаю добрых снов!'
        ),
        reply_markup=KEYBOARD_LOBBY_HOST,
    )
    answer_2: Message = await message.answer(text=form_lobby_host_message(game=game))
    await set_user_messages_to_delete(
        event_key=MessagesEvents.IN_LOBBY,
        messages=[answer_1, answer_2],
    )

    game['host_lobby_message_id'] = answer_2.message_id
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


@router.message(GameForm.in_lobby)
async def start_game(
    message: Message,
    state: FSMContext,
) -> None:
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))
    if message.text == RoutersCommands.GAME_DROP:
        return await process_in_game_destroy_game_confirm(
            message=message,
            state=state,
            from_lobby=True,
        )
    if message.text != RoutersCommands.GAME_START:
        return

    game: dict[str, Any] = await process_game_in_redis(message=message, get=True)
    if not await __validate_players_count(game=game, message=message):
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        return

    await state.set_state(state=GameForm.in_game)
    process_avaliable_game_numbers(remove_number=game['number'])

    await setup_game_data(game=game)
    await send_game_start_messages(game=game)
    await send_game_roles_messages(game=game)
    await send_users_ordering_message(game=game)
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)


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
) -> dict[str, Any]:
    """Создает лобби."""
    while 1:
        # INFO. Двойка зарезервирована за создателем.
        if user.id_telegram == settings.ADMIN_NOTIFY_ID:
            number: str = '2️⃣2️⃣2️⃣'
            key: str = RedisKeys.GAME_LOBBY.format(number=number)
        else:
            number: str = ''.join(choices('013456789', k=4))
            key: str = RedisKeys.GAME_LOBBY.format(number=number)
            if redis_check_exists(key=key):
                continue
        break

    redis_set(key=RedisKeys.USER_GAME_LOBBY_NUMBER.format(id_telegram=str(user.id_telegram)), value=number)
    process_avaliable_game_numbers(add_number=number)
    return {
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
    }


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
        messages_ids=(message.message_id, answer.message_id),
    )
    return False
