
from sqlalchemy.sql import select
from sqlalchemy.sql.selectable import Select

from app.src.database.base_async_crud import (
    AsyncSession,
    BaseAsyncCrud,
)
from app.src.models.image import Image
from app.src.validators.image import ImageCategory


class ImageCrud(BaseAsyncCrud):
    """Класс CRUD запросов к базе данных к таблице Image."""

    async def retrieve_all_rules_ids_telegram(
        self,
        *,
        session: AsyncSession,
    ) -> list[str]:
        """Получает список id_telegram всех карточек правил, отсортированных по порядку."""
        query: Select = (
            select(Image.id_telegram)
            .where(Image.category == ImageCategory.RULES)
            .order_by(Image.name)
        )
        return (await session.execute(query)).scalars().all()

    async def retrieve_all_words_ids_telegram(
        self,
        *,
        session: AsyncSession,
    ) -> list[int]:
        """Получает список id_telegram всех карточек слов."""
        query: Select = (
            select(Image.id_telegram, Image.id_telegram_rotated)
            .where(Image.category == ImageCategory.WORDS)
        )
        pairs: list[tuple[int, int]] = (await session.execute(query)).all()
        return [value for pair in pairs for value in pair]


image_crud: ImageCrud = ImageCrud(
    model=Image,
    unique_columns=(
        'id_telegram',
        'local_path',
        'name',
    ),
    unique_columns_err='Пользователь с таким параметром уже добавлен в базу данных',
)
