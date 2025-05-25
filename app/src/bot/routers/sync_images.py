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
    if scheduler.get_job(job_id=SchedulerJobNames.SYNC_IMAGES):
        answer_text: str = 'Синхронизация уже в процессе'
    else:
        answer_text: str = 'Синхронизация запущена'
        scheduler.add_job(
            id=SchedulerJobNames.SYNC_IMAGES,
            func=sync_images,
        )

    await message.answer(text=answer_text)
    await async_sleep(1)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id, message.message_id + 1],
    )
