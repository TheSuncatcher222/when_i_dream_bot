from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)
from aiogram.methods.delete_message import DeleteMessage

from app.src.bot.bot import bot


async def delete_messages_list(
    chat_id: int,
    messages_ids: list[int],
    raise_exception: bool = False,
) -> None:
    """
    Удаляет указанные сообщения в телеграм чате/группе.
    """
    messages_ids.reverse()
    for message_id in messages_ids:
        try:
            await bot(DeleteMessage(chat_id=chat_id, message_id=message_id))
        except TelegramForbiddenError:
            if raise_exception:
                raise
            return
        except TelegramBadRequest:
            if raise_exception:
                raise
            continue
