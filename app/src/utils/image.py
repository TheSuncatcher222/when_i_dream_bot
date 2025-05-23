"""
Модуль утилит приложения "image".
"""

from app.src.crud.image import image_crud
from app.src.database.database import async_session_maker


async def get_rules_ids_telegram() -> list[str]:
    """Получает список id_telegram всех карточек правил, отсортированных по порядку."""
    # TODO. Интегрировать Redis
    async with async_session_maker() as session:
        return await image_crud.retrieve_all_rules_ids_telegram(session=session)
