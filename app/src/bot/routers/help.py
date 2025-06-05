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
from aiogram.types import (
    InputMediaPhoto,
    Message,
)

from app.src.bot.routers.start import command_start
from app.src.utils.image import get_rules_ids_telegram
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import (
    RoutersCommands,
    KEYBOARD_HELP,
)

router: Router = Router()


class HelpForm(StatesGroup):
    """
    Состояния формы роутера.
    """

    in_help = State()

    _help_message_id: int


@router.message(F.text == RoutersCommands.HELP)
async def help(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Обрабатывает команду "Помощь".
    """
    await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))
    answer: Message = await message.answer(
        text=(
            'Предисловие.\n\n'

            'Дорогие друзья! Целью создания данного бота было не сделать игру '
            '"Пока я сплю" доступной онлайн, а лишь освободить игроков от необходимости '
            'иметь при себе ее физический экземпляр. Я всей душой рекомендую играть '
            'в настолку, только собравшись всем вместе. Лишь в этом случае вы сможете '
            'по-настоящему ощутить атмосферу этой потрясающей игры!\n\n'

            '1. Создание новой игры.\n\n'

            'Чтобы начать игру, одному из игроков нужно вызвать команду «Создать игру». '
            'В ответ бот пришлёт номер лобби и четырёхзначный пароль. Эти данные '
            'нужно передать всем, с кем ты хочешь отправиться в мир грёз (см. пункт 2)\n\n'

            '2. Присоединение к существующей игровой сессии.\n\n'

            'Чтобы присоединиться к созданной игре, необходимо использовать команду '
            '"Присоединиться к игре". В ответном сообщении бот пришлет список '
            'доступных лобби и попросит указать номер нужного. В ответном сообщении'
            'нужно указать только номер лобби. Если номер указан верно, бот запросит '
            'пароль для входа - его нужно узнать у того, кто создавал игру (см. пункт 1).'
        ),
        reply_markup=KEYBOARD_HELP,
    )
    await state.set_state(HelpForm.in_help)
    await state.update_data(_help_message_id=answer.message_id)


@router.message(HelpForm.in_help)
async def in_help(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == RoutersCommands.HELP_RULES:
        await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))
        return await message.answer_media_group(
            media=[
                InputMediaPhoto(media=media_id)
                for media_id
                in await get_rules_ids_telegram()
            ],
        )

    if message.text != RoutersCommands.HOME:
        return await delete_messages_list(chat_id=message.chat.id, messages_ids=(message.message_id,))

    state_data: dict[str, Any] = await state.get_data()
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=(message.message_id, state_data['_help_message_id']),
    )
    await state.clear()
    await command_start(message=message)
