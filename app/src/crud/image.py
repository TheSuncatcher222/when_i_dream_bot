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

    async def retrieve_all_roles_ids_telegram(
        self,
        *,
        session: AsyncSession,
    ) -> dict[str, str]:
        """Получает список id_telegram всех карточек персонажей."""
        query: Select = (
            select(Image.name, Image.id_telegram)
            .where(Image.category == ImageCategory.CHARACTERS)
        )
        result = await session.execute(query)
        return dict(result.all())

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
    ) -> list[tuple[str, int, int]]:
        """Получает словарь {name: id_telegram} всех карточек слов."""
        query: Select = (
            select(Image.name, Image.id_telegram, Image.id_telegram_rotated)
            .where(Image.category == ImageCategory.WORDS)
        )
        return (await session.execute(query)).all()


image_crud: ImageCrud = ImageCrud(
    model=Image,
    unique_columns=(
        'id_telegram',
        'local_path',
        'name',
    ),
    unique_columns_err='Пользователь с таким параметром уже добавлен в базу данных',
)
