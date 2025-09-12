from asyncio import (
    create_task,
    gather,
    sleep as async_sleep,
    Task,
)

from aiogram import (
    Router,
    F,
)
from aiogram.types import Message

from app.src.bot.bot import bot
from app.src.crud.image import image_crud
from app.src.database.database import async_session_maker
from app.src.models.image import Image
from app.src.utils.auth import IsAdmin
from app.src.utils.message import delete_messages_list
from app.src.utils.reply_keyboard import RoutersCommands

router: Router = Router()


@router.message(
    IsAdmin(),
    F.text == RoutersCommands.SEND_TEST_IMAGE,
)
async def send_test_picture(message: Message):
    """
    Обрабатывает команду "Тест картинок".
    """
    async with async_session_maker() as session:
        images: list[Image] = await image_crud.retrieve_all_words_ids_telegram(
            session=session,
        )
    tasks: list[Task] = [
        create_task(
            bot.send_photo(
                chat_id=message.chat.id,
                photo=image.id_telegram,
            )
        )
        for image in images[:5]
    ]
    answers: list[Message] = await gather(*tasks)
    await async_sleep(1)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[a.message_id for a in answers] + [message.message_id],
    )
