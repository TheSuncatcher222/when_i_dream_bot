from typing import Iterable

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
)
from aiogram.methods.delete_message import DeleteMessage
from aiogram.types import Message

from app.src.bot.bot import bot
from app.src.database.database import RedisKeys
from app.src.utils.redis_app import (
    redis_get,
    redis_set,
    redis_delete,
)


class MessagesEvents:
    """Класс представления событий отправки сообщений."""

    IN_LOBBY: str = 'IN_LOBBY'
    GAME_DESTROY: str = 'GAME_DESTROY'
    GAME_DROP: str = 'GAME_DROP'
    RETELL: str = 'RETELL'
    ROLE: str = 'ROLE'
    ROUND_STARTED: str = 'ROUND_STARTED'
    SET_PENALTY: str = 'SET_PENALTY'
    WORD: str = 'WORD'

    @classmethod
    def get_all_events(cls) -> tuple[str]:
        return (
            cls.IN_LOBBY,
            cls.GAME_DESTROY,
            cls.GAME_DROP,
            cls.RETELL,
            cls.ROLE,
            cls.ROUND_STARTED,
            cls.SET_PENALTY,
            cls.WORD,
        )

    @classmethod
    def get_redis_key(cls, chat_id: int | str, event_key: str) -> str:
        """Формирует ключ в Redis."""
        if event_key == cls.IN_LOBBY:
            return RedisKeys.MESSAGES_IN_LOBBY.format(id_telegram=chat_id)
        elif event_key == cls.GAME_DESTROY:
            return RedisKeys.MESSAGE_GAME_DESTROY.format(id_telegram=chat_id)
        elif event_key == cls.GAME_DROP:
            return RedisKeys.MESSAGE_GAME_DROP.format(id_telegram=chat_id)
        elif event_key == cls.RETELL:
            return RedisKeys.MESSAGE_RETELL.format(id_telegram=chat_id)
        elif event_key == cls.ROLE:
            return RedisKeys.MESSAGE_ROLE.format(id_telegram=chat_id)
        elif event_key == cls.ROUND_STARTED:
            return RedisKeys.MESSAGE_ROUND_STARTED.format(id_telegram=chat_id)
        elif event_key == cls.SET_PENALTY:
            return RedisKeys.MESSAGE_SET_PENALTY.format(id_telegram=chat_id)
        elif event_key == cls.WORD:
            return RedisKeys.MESSAGE_WORD.format(id_telegram=chat_id)


# TODO. Попробовать интеграцию bot.delete_messages
async def delete_messages_list(
    chat_id: int,
    messages_ids: Iterable[int],
    raise_exception: bool = False,
    reverse: bool = True,
) -> None:
    """
    Удаляет указанные сообщения в телеграм чате/группе.
    """
    for message_id in reversed(messages_ids) if reverse else messages_ids:
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


async def set_user_messages_to_delete(
    event_key: list[int],
    messages: Iterable[Message],
) -> None:
    """Добавляет ID сообщений чата игрока для удаления в список по указанному ключу."""
    redis_set(
        key=MessagesEvents.get_redis_key(chat_id=messages[0].chat.id, event_key=event_key),
        value=[message.message_id for message in messages],
    )


async def delete_user_messages(
    chat_id: int | str,
    event_key: str | None = None,
    all_event_keys: bool = False,
) -> None:
    """Удаляет сообщения игрока по заданному ключу или все."""
    if all_event_keys:
        event_keys: list[str] = MessagesEvents.get_all_events()
    else:
        event_keys: tuple[str] = (event_key,)

    for k in event_keys:
        redis_key: str = MessagesEvents.get_redis_key(chat_id=chat_id, event_key=k)
        messages_ids: tuple[int] | None = redis_get(key=redis_key)
        if messages_ids:
            await delete_messages_list(chat_id=chat_id, messages_ids=messages_ids)
            redis_delete(key=redis_key)
