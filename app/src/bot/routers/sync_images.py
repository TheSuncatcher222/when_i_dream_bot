from asyncio import sleep as async_sleep

from aiogram import (
    Router,
    F,
)
from aiogram.types import Message

from app.src.utils.auth import IsAdmin
from app.src.utils.image import sync_images
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import RoutersCommands
from app.src.scheduler.scheduler import (
    SchedulerJobNames,
    scheduler,
)

router: Router = Router()


@router.message(
    IsAdmin(),
    F.text == RoutersCommands.SYNC_IMAGES,
)
async def command_sync_images(message: Message):
    """
    Создает задачу синхронизации картинок.
    """
    scheduler.add_job(
        id=SchedulerJobNames.SYNC_IMAGES,
        func=sync_images,
        max_instances=1,
        replace_existing=False,
    )
    await message.answer(text='Синхронизация запущена')
    await async_sleep(1)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=(message.message_id, message.message_id + 1),
    )
