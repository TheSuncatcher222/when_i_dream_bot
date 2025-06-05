from asyncio import sleep as asyncio_sleep
from typing import Any

from aiogram import (
    Router,
    F,
)
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.src.bot.bot import bot
from app.src.bot.routers.start import command_start
from app.src.crud.user import user_crud
from app.src.database.database import (
    async_session_maker,
    RedisKeys,
)
from app.src.models.user import User
from app.src.utils.game import (
    GameForm,
    form_lobby_host_message,
    process_avaliable_game_numbers,
    process_in_game,
    process_game_in_redis,
)
from app.src.utils.message import (
    MessagesEvents,
    delete_messages_list,
    set_user_messages_to_delete,
)
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    make_row_keyboard,
    KEYBOARD_HOME,
)
from app.src.utils.redis_app import redis_set
from app.src.validators.game import (
    GameParams,
    GameStatus,
)

router: Router = Router()


@router.message(F.text == RoutersCommands.GAME_JOIN)
async def command_game_join(
    message: Message,
    state: FSMContext,
) -> None:
    """Инициализирует присоединение к игровому лобби."""
    avaliable_games_numbers: list[str] = process_avaliable_game_numbers(get=True)
    if not avaliable_games_numbers:
        await state.clear()
        answer: Message = await message.answer(text='В данный момент никто не собирается спать.')
        await asyncio_sleep(2)
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=(message.message_id, answer.message_id),
        )

    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=(user.message_main_last_id, message.message_id),
    )

    rows: list[list[str]] = [[RoutersCommands.HOME]]
    i: int = 1
    sub_row: list[str] = []
    for idx, game in enumerate(avaliable_games_numbers):
        sub_row.append(game)
        if i == 5 or idx == len(avaliable_games_numbers) - 1:
            rows.append(sub_row)
            sub_row = []
            i = 1
        else:
            i += 1

    answer: Message = await message.answer(
        text = 'К какому сну ты хочешь присоединиться?\n' + '\n'.join(f'- {number}' for number in avaliable_games_numbers),
        reply_markup=make_row_keyboard(rows=rows),
    )
    await state.update_data({'_command_game_join_message_id': answer.message_id})
    await state.set_state(state=GameForm.in_lobby_select_game)


@router.message(GameForm.in_lobby_select_game)
async def asked_for_password(
    message: Message,
    state: FSMContext,
):
    """Запрашивает пароль игрового лобби."""
    state_data: dict[str, Any] = await state.get_data()

    if message.text == RoutersCommands.HOME:
        await state.clear()
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=(state_data['_command_game_join_message_id'], message.message_id),
        )
        return await command_start(message=message)

    game: dict[str, Any] | None = await process_game_in_redis(
        redis_key=RedisKeys.GAME_LOBBY.format(number=message.text),
        get=True,
    )
    if game:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)

    success: bool = False
    if not game:
        text: str = 'Такого сна не существует.'
    elif game['status'] != GameStatus.IN_LOBBY:
        text: str = 'Игроки уже крепко спят, присоединиться не получится.'
    else:
        success: bool = True
    if not success:
        answer: Message = await message.answer(text=text)
        await asyncio_sleep(1)
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=(message.message_id, answer.message_id),
        )

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=(state_data['_command_game_join_message_id'], message.message_id),
    )
    answer: Message = await message.answer(
        text='Узнай у Хранителя сна пароль и сообщи мне.',
        reply_markup=KEYBOARD_HOME,
    )
    await state.update_data(
        {
            '_asked_for_password_message_id': answer.message_id,
            '_join_game_number': message.text,
        },
    )
    await state.set_state(state=GameForm.in_lobby_enter_password)


@router.message(GameForm.in_lobby_enter_password)
async def add_to_game(
    message: Message,
    state: FSMContext,
):
    """Добавляет пользователя в игровое лобби."""
    state_data: dict[str, Any] = await state.get_data()

    if message.text == RoutersCommands.HOME:
        await state.clear()
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=(state_data['_asked_for_password_message_id'], message.message_id),
        )
        return await command_start(message=message)

    game: dict[str, Any] | None = await process_game_in_redis(RedisKeys.GAME_LOBBY.format(number=state_data['_join_game_number']), get=True)

    if message.text != game['password']:
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        answer: Message = await message.answer(text='Увы, пароль оказался неправильным..')
        await process_game_in_redis(redis_key=game['redis_key'], release=True)
        await asyncio_sleep(1)
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=(message.message_id, answer.message_id),
        )

    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
    game['players'][str(user.id_telegram)] = {
        'name': user.get_full_name(),
        'id': user.id,
        'chat_id': str(message.chat.id),
    }
    await bot.edit_message_text(
        chat_id=game['host_chat_id'],
        message_id=game['host_lobby_message_id'],
        text=form_lobby_host_message(game=game),
    )

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=(state_data['_asked_for_password_message_id'], message.message_id),
    )

    await state.set_state(state=GameForm.in_game)
    answer: Message = await message.answer(
        text=(
            'Успешно! Как только все сновидцы будут готовы, '
            'Хранитель сна начнет ваше путешествие.'
        ),
        reply_markup=KEYBOARD_HOME,
    )

    await set_user_messages_to_delete(
        event_key=MessagesEvents.IN_LOBBY,
        messages=[answer],
    )
    await process_game_in_redis(redis_key=game['redis_key'], set_game=game)
    redis_set(key=RedisKeys.USER_GAME_LOBBY_NUMBER.format(id_telegram=str(user.id_telegram)), value=game['number'])
    if len(game['players']) == GameParams.PLAYERS_MAX:
        process_avaliable_game_numbers(remove_number=game['number'])
