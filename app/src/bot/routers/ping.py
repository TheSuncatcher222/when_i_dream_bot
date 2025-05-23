from asyncio import sleep as async_sleep

from aiogram import (
    Router,
    F,
)
from aiogram.types import Message

from app.src.utils.auth import IsAdmin
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import RoutersCommands

router: Router = Router()


@router.message(
    IsAdmin(),
    F.text == RoutersCommands.PING,
)
async def ping(message: Message):
    """
    Обрабатывает команду "Пинг".
    """
    await message.answer(text='Понг')
    await async_sleep(0.5)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )
