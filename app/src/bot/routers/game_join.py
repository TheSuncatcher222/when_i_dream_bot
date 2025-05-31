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
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    make_row_keyboard,
    KEYBOARD_HOME,
    KEYBOARD_LOBBY_HOST,
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
        answer: Message = await message.answer(text='В данный момент никто не собирается спать.')
        await asyncio_sleep(1)
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id, answer.message_id],
        )
        return await command_start(message=message)

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


    await state.set_state(state=GameForm.in_lobby_select_game)
    await message.answer(
        text = 'К какому сну ты хочешь присоединиться?\n' + '\n'.join(f'- {number}' for number in avaliable_games_numbers),
        reply_markup=make_row_keyboard(rows=rows),
    )


@router.message(GameForm.in_lobby_select_game)
async def asked_for_password(
    message: Message,
    state: FSMContext,
):
    """Запрашивает пароль игрового лобби."""
    if message.text == RoutersCommands.HOME:
        await state.clear()
        return await command_start(message=message)

    game: dict[str, Any] | None = process_game_in_redis(RedisKeys.GAME_LOBBY.format(number=message.text), get=True)
    success: bool = False

    if not game:
        text: str = 'Такого сна не существует.'
    elif game.get('started', False):
        text: str = 'Игроки уже крепко спят, присоединиться не получится.'
    else:
        success: bool = True
    if not success:
        answer: Message = await message.answer(text=text)
        await asyncio_sleep(1)
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id, answer.message_id],
        )

    await state.update_data(_join_game_number=message.text)
    await state.set_state(state=GameForm.in_lobby_enter_password)
    await message.answer(
        text='Узнай у Хранителя сна пароль и сообщи мне.',
        reply_markup=KEYBOARD_HOME,
    )


@router.message(GameForm.in_lobby_enter_password)
async def add_to_game(
    message: Message,
    state: FSMContext,
):
    """Добавляет пользователя в игровое лобби."""
    if message.text == RoutersCommands.HOME:
        await state.clear()
        return await command_start(message=message)

    state_data: dict[str, Any] = await state.get_data()
    game: dict[str, Any] | None = process_game_in_redis(RedisKeys.GAME_LOBBY.format(number=state_data['_join_game_number']), get=True)

    if message.text != game['password']:
        answer: Message = await message.answer(text='Увы, пароль оказался неправильным..')
        await asyncio_sleep(1)
        return await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=[message.message_id, answer.message_id],
        )

    async with async_session_maker() as session:
        user: User = await user_crud.retrieve_by_id_telegram(
            obj_id_telegram=message.from_user.id,
            session=session,
        )
    game['players'][user.id_telegram] = {
        'name': user.get_full_name(),
        'chat_id': message.chat.id,
    }
    process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    # TODO. Попробовать через bot.edit_message_text
    # TODO. bot.delete_messages!!!!!
    # TODO. Когда уходят с лобби - менять сообщение.
    await delete_messages_list(
        chat_id=game['host_chat_id'],
        messages_ids=[game['host_lobby_message_id']],
    )
    host_message: Message = await bot.send_message(
        chat_id=game['host_chat_id'],
        text=form_lobby_host_message(redis_key=game['redis_key']),
        reply_markup=KEYBOARD_LOBBY_HOST,
    )
    game["host_lobby_message_id"] = host_message.message_id
    process_game_in_redis(redis_key=game['redis_key'], set_game=game)

    await state.set_state(state=GameForm.in_game)
    await message.answer(
        text='Успешно!',
        reply_markup=KEYBOARD_HOME,
    )


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
