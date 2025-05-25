"""
Модуль утилит приложения "image".
"""

from asyncio import (
    Semaphore as AsyncSemaphore,
    Task as AsyncTask,
    gather as asyncio_gather,
    sleep as asyncio_sleep,
)
from re import sub as re_sub
from pathlib import Path

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    FSInputFile,
    Message,
)

from app.src.bot.bot import bot
from app.src.config.config import (
    Dirs,
    settings,
)
from app.src.crud.image import image_crud
from app.src.database.database import async_session_maker
from app.src.utils.message import delete_messages_list
from app.src.validators.image import ImageCategory


async def get_rules_ids_telegram() -> list[str]:
    """Получает список id_telegram всех карточек правил, отсортированных по порядку."""
    # TODO. Интегрировать Redis
    async with async_session_maker() as session:
        return await image_crud.retrieve_all_rules_ids_telegram(session=session)


async def sync_images() -> None:
    """Проверяет и синхронизирует картинки на сервере telegram и локально."""
    async with async_session_maker() as session:
        db_images: dict[str, str | int] = {
            image.local_path: {
                'id': image.id,
                'id_telegram': image.id_telegram,
            }
            for image
            in await image_crud.retrieve_all(session=session, limit=None)
        }

    semaphore: AsyncSemaphore = AsyncSemaphore(value=5)
    tasks: list[AsyncTask] = [
        __inspect_obj_with_semaphore(
            obj=obj,
            dir_name=dir.name,
            db_images=db_images,
            semaphore=semaphore,
        )
        for dir in Dirs.get_all_cards()
        for obj in dir.iterdir()
    ]
    await asyncio_gather(*tasks)

    if db_images:
        async with async_session_maker() as session:
            await image_crud.delete_all_by_ids(
                obj_ids=[obj['id'] for obj in db_images.values()],
                session=session,
            )

    message: Message = await bot.send_message(
        chat_id=settings.ADMIN_NOTIFY_ID,
        text='Синхронизация успешно завершена ✅',
    )
    await asyncio_sleep(1)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )


async def __inspect_obj(
    obj: Path,
    dir_name: str,
    db_images: dict[str, str | int],
) -> None:
    """Проверяет один объект в рамках логики функции check_images."""
    if obj.is_dir() or not obj.name.endswith('.jpg'):
        await bot.send_message(
            chat_id=settings.ADMIN_NOTIFY_ID,
            text=f'Find unexpected object {obj}, it is not ".jpg" image',
        )
        return

    obj_local_path: str = str(obj.relative_to(Dirs.DIR_RES))
    db_obj: dict[str, str] = db_images.pop(obj_local_path, None)
    if db_obj and await bot.get_file(file_id=db_obj['id_telegram']):
        return

    while 1:
        try:
            message: Message = await bot.send_photo(
                chat_id=settings.ADMIN_NOTIFY_ID,
                photo=FSInputFile(path=obj),
                caption='Perform image res sync...',
                disable_notification=True,
            )
            break
        except TelegramRetryAfter:
            await asyncio_sleep(15)

    async with async_session_maker() as session:
        if db_obj:
            await image_crud.update_by_id(
                obj_id=db_obj['id'],
                obj_dat={'id_telegram': message.photo[-1].file_id},
                session=session,
            )
        else:
            order, card_name = __parse_obj_name(obj=obj, dir_name=dir_name)
            await image_crud.create(
                obj_data={
                    'id_telegram': message.photo[-1].file_id,
                    'local_path': obj_local_path,
                    'name': card_name,
                    'order': order,
                    'category': ImageCategory.get_category_by_dir(dir_name=dir_name),
                },
                session=session,
            )

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )


async def __inspect_obj_with_semaphore(
    obj: Path,
    dir_name: str,
    db_images: dict[str, str | int],
    semaphore: AsyncSemaphore,
) -> None:
    async with semaphore:
        await __inspect_obj(obj=obj, dir_name=dir_name, db_images=db_images)


def __parse_obj_name(obj: Path, dir_name: str) -> tuple[int, str]:
    """Парсит название изображения."""
    if dir_name == Dirs.WORDS:
        order, card_name_first, card_name_second = obj.stem.split('_')
        card_name: str = f'{card_name_first} | {card_name_second}'
    else:
        order, card_name = obj.stem.split('_')
    card_name: str = re_sub(pattern='-', repl=' ', string=card_name)
    return int(order), card_name
