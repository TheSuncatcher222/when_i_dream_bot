from aiogram import Router
from aiogram.types import Message

from app.src.bot.routers.start import command_start
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import RoutersCommands

router: Router = Router()


@router.message()
async def fallback(message: Message):
    """
    Обрабатывает неперехваченное любым другим роутером сообщение.
    """
    if message.chat.type != 'private':
        return

    if message.text == RoutersCommands.HOME:
        await delete_messages_list(
            chat_id=message.chat.id,
            messages_ids=list(range(message.message_id-10, message.message_id + 1)),
        )
        return await command_start(message=message, from_command_start=False)

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )
