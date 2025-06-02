"""
Модуль утилит приложения "image".
"""

from asyncio import (
    Semaphore as AsyncSemaphore,
    Task as AsyncTask,
    gather as asyncio_gather,
    sleep as asyncio_sleep,
)
from random import shuffle
from re import sub as re_sub
from pathlib import Path
from typing import Any

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    FSInputFile,
    Message,
)
from PIL import Image
from tempfile import NamedTemporaryFile

from app.src.bot.bot import bot
from app.src.config.config import (
    Dirs,
    settings,
)
from app.src.crud.image import image_crud
from app.src.database.database import (
    async_session_maker,
    RedisKeys,
)
from app.src.utils.message import delete_messages_list
from app.src.validators.image import ImageCategory
from app.src.utils.redis_app import (
    redis_delete,
    redis_get,
    redis_set,
)


async def get_role_image_cards() -> dict[str, str]:
    """Получает id_telegram карт ролей."""
    cards_ids: dict[str, str] | None = redis_get(key=RedisKeys.ROLES)
    if not cards_ids:
        async with async_session_maker() as session:
            cards_ids: dict[str, str] = await image_crud.retrieve_all_rules_ids_telegram(session=session)
            redis_set(key=RedisKeys.ROLES, value=cards_ids)
    return cards_ids


async def get_rules_ids_telegram() -> list[str]:
    """Получает список id_telegram всех карточек правил, отсортированных по порядку."""
    rules_ids: list[str] = redis_get(key=RedisKeys.RULES)
    if not rules_ids:
        async with async_session_maker() as session:
            rules_ids: list[str] = await image_crud.retrieve_all_rules_ids_telegram(session=session)
        redis_set(key=RedisKeys.RULES, value=rules_ids)
    return rules_ids


async def get_shuffled_words_cards() -> list[int]:
    """Генерирует случайный порядок карт слов для игры."""
    cards_ids: list[int] = redis_get(key=RedisKeys.WORDS)
    if not cards_ids:
        async with async_session_maker() as session:
            cards_ids: list[int] = await image_crud.retrieve_all_words_ids_telegram(session=session)
            redis_set(key=RedisKeys.WORDS, value=cards_ids)
    shuffle(cards_ids)
    return cards_ids


async def sync_images() -> None:
    """Проверяет и синхронизирует картинки на сервере telegram и локально."""
    async with async_session_maker() as session:
        db_images: dict[str, str | int] = {
            image.local_path: {
                'id': image.id,
                'id_telegram': image.id_telegram,
                'id_telegram_rotated': image.id_telegram_rotated,
            }
            for image
            in await image_crud.retrieve_all(session=session, limit=None)
        }

    semaphore: AsyncSemaphore = AsyncSemaphore(value=5)
    tasks: list[AsyncTask] = [
        __sync_image_with_semaphore(
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

    for key in (RedisKeys.ROLES, RedisKeys.WORDS):
        redis_delete(key=key)

    message: Message = await bot.send_message(
        chat_id=settings.ADMIN_NOTIFY_ID,
        text='Синхронизация успешно завершена ✅',
    )
    await asyncio_sleep(1)
    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=[message.message_id],
    )


async def __check_if_is_needed_to_sync(
    obj: Path,
    db_obj: dict[str, str | int],
) -> bool:
    if obj.is_dir() or not obj.name.endswith('.jpg'):
        await bot.send_message(
            chat_id=settings.ADMIN_NOTIFY_ID,
            text=f'Find unexpected object {obj}, it is not ".jpg" image',
        )
        return False

    if db_obj and await bot.get_file(file_id=db_obj['id_telegram']):
        if not obj.is_relative_to(Dirs.DIR_WORDS) or await bot.get_file(file_id=db_obj['id_telegram_rotated']):
            return False

    return True


async def __sync_image(
    obj: Path,
    dir_name: str,
    db_images: dict[str, str | int],
) -> None:
    """Проверяет один объект в рамках логики функции check_images."""
    obj_local_path: str = str(obj.relative_to(Dirs.DIR_RES))
    db_obj: dict[str, str | int] | None = db_images.pop(obj_local_path, None)

    if not await __check_if_is_needed_to_sync(obj=obj, db_obj=db_obj):
        return

    obj_data: dict[str, Any] = await __upload_images_to_telegram(
        obj=obj,
        obj_local_path=obj_local_path,
        db_obj=db_obj,
        dir_name=dir_name,
    )
    async with async_session_maker() as session:
        if db_obj:
            await image_crud.update_by_id(
                obj_id=db_obj['id'],
                obj_dat=obj_data,
                session=session,
            )
        else:
            await image_crud.create(
                obj_data=obj_data,
                session=session,
            )


def __parse_obj_name(obj: Path, dir_name: str) -> str:
    """Парсит название изображения."""
    if dir_name == Dirs.WORDS:
        _, card_name_first, card_name_second = obj.stem.split('_')
        card_name: str = f'{card_name_first} | {card_name_second}'
    else:
        _, card_name = obj.stem.split('_')
    card_name: str = re_sub(pattern='-', repl=' ', string=card_name)
    return card_name


async def __sync_image_with_semaphore(
    obj: Path,
    dir_name: str,
    db_images: dict[str, str | int],
    semaphore: AsyncSemaphore,
) -> None:
    async with semaphore:
        await __sync_image(obj=obj, dir_name=dir_name, db_images=db_images)


async def __upload_images_to_telegram(
    obj: Path,
    obj_local_path: str,
    db_obj: dict[str, str | int] | None,
    dir_name: str,
) -> dict[str, Any]:
    """Загружает картинки в telegram."""
    messages_ids: list[int] = []
    obj_data: dict[str, str] = {}

    for key in ('id_telegram', 'id_telegram_rotated'):
        while 1:
            try:
                if key == 'id_telegram':
                    message: Message = await bot.send_photo(
                        chat_id=settings.ADMIN_NOTIFY_ID,
                        photo=FSInputFile(path=obj),
                        caption='Perform image res sync...',
                        disable_notification=True,
                    )
                elif obj.is_relative_to(Dirs.DIR_WORDS):
                    with Image.open(obj) as image:
                        rotated_img: Image = image.rotate(180, expand=True)
                        with NamedTemporaryFile(suffix='.jpg') as tmp_file:
                            rotated_img.save(tmp_file, format='JPEG')
                            tmp_path: str = tmp_file.name
                            message: Message = await bot.send_photo(
                                chat_id=settings.ADMIN_NOTIFY_ID,
                                photo=FSInputFile(path=tmp_path),
                                caption='Perform image res sync...',
                                disable_notification=True,
                            )
                else:
                    break
            except TelegramRetryAfter:
                await asyncio_sleep(15)
                continue
            messages_ids.append(message.message_id)
            obj_data[key] = message.photo[-1].file_id
            break

    await delete_messages_list(
        chat_id=message.chat.id,
        messages_ids=messages_ids,
    )

    if not db_obj:
        obj_data.update(
        {
            'local_path': obj_local_path,
            'name': __parse_obj_name(obj=obj, dir_name=dir_name),
            'category': ImageCategory.get_category_by_dir(dir_name=dir_name),
        },
        )
    return obj_data
