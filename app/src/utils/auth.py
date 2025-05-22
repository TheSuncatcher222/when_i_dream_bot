from aiogram.filters import Filter
from aiogram.types import Message

from app.src.config.config import settings


class IsAdmin(Filter):
    """
    Фильтр доступа для администраторов.
    """

    async def __call__(self, message: Message) -> bool:
        return check_if_user_is_admin(user_id_telegram=message.from_user.id)


def check_if_user_is_admin(user_id_telegram: int | str) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    """
    return str(user_id_telegram) in settings.BOT_ADMIN_IDS
