"""
Модуль базового класса асинхронных CRUD запросов в базу данных.
"""


from sqlalchemy.sql import (
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.sql.dml import (
    Delete,
    Insert,
    Update,
)
from sqlalchemy.sql.selectable import Select

from app.src.database.database import (
    AsyncSession,
    Base,
)

PAGINATION_LIMIT_DEFAULT: int = 15
PAGINATION_OFFSET_DEFAULT: int = 0


class BaseAsyncCrud():
    """Базовый класс асинхронных CRUD запросов к базе данных."""

    def __init__(
        self,
        *,
        model: Base,
        unique_columns: tuple[str] = None,
        unique_columns_err: str = 'Объект уже существует',
    ):
        self.model = model
        self.unique_columns_err = unique_columns_err
        self.unique_columns = unique_columns

    async def create(
        self,
        *,
        obj_data: dict[str, any],
        session: AsyncSession,
        perform_cleanup: bool = True,
        perform_commit: bool = True,
    ) -> Base:
        """Создает один объект в базе данных."""
        await self._check_unique(obj_data=obj_data, session=session)

        if perform_cleanup:
            obj_data: dict[str, any] = self._clean_obj_data_non_model_fields(obj_data=obj_data)

        stmt: Insert = insert(self.model).values(**obj_data).returning(self.model)
        obj: Base = (await session.execute(stmt)).scalars().first()

        if perform_commit:
            await session.commit()

        return obj

    async def retrieve_all(
        self,
        *,
        limit: int = PAGINATION_LIMIT_DEFAULT,
        offset: int = PAGINATION_OFFSET_DEFAULT,
        session: AsyncSession,
    ) -> list[Base]:
        """Получает несколько объектов из базы данных."""
        query: Select = select(self.model).limit(limit).offset(offset)
        result: list[Base] = (await session.execute(query)).scalars().all()
        return result

    async def retrieve_by_id(
        self,
        *,
        obj_id: int,
        session: AsyncSession,
    ) -> Base:
        """Получает один объект из базы данных по указанному id."""
        query: Select = select(self.model).where(self.model.id == obj_id)
        result: Base | None = (await session.execute(query)).scalars().first()
        if result is None:
            self._raise_value_error_not_found(id=obj_id)
        return result

    async def update_by_id(
        self,
        *,
        obj_id: int,
        obj_data: dict[str, any],
        session: AsyncSession,
        perform_check_unique: bool = False,
        perform_cleanup: bool = True,
        perform_commit: bool = True,
    ) -> Base:
        """Обновляет один объект из базы данных по указанному id."""
        if perform_cleanup:
            obj_data: dict[str, any] = self._clean_obj_data_non_model_fields(obj_data=obj_data)

        query: Select = select(self.model).where(self.model.id == obj_id)
        if (await session.execute(query)).scalars().first() is None:
            self._raise_value_error_not_found(id=obj_id)

        if perform_check_unique:
            await self._check_unique(obj_data=obj_data, session=session)

        stmt: Update = (
            update(self.model)
            .where(self.model.id == obj_id)
            .values(**obj_data)
            .returning(self.model)
        )
        obj: Base = (await session.execute(stmt)).scalars().first()

        if perform_commit:
            await session.commit()

        return obj

    async def delete_by_id(
        self,
        *,
        obj_id: int,
        session: AsyncSession,
        perform_commit: bool = True,
    ) -> None:
        """
        Удаляет один объект из базы данных по указанному id.
        """
        stmt: Delete = delete(self.model).where(self.model.id == obj_id)
        await session.execute(stmt)

        if perform_commit:
            await session.commit()

    async def _check_unique(
        self,
        *,
        obj_data: dict[str, any],
        session: AsyncSession,
    ) -> None:
        """Проверяет уникальность переданных значений."""
        if self.unique_columns is None:
            return

        conditions: list = []
        for column_name in self.unique_columns:
            conditions.append(getattr(self.model, column_name) == obj_data[column_name])
        query: Select = select(self.model).filter(*conditions)

        if (await session.execute(query)).scalar() is not None:
            raise ValueError(self.unique_columns_err)

    def _clean_obj_data_non_model_fields(
        self,
        *,
        obj_data: dict[str, any],
    ) -> dict[str, any]:
        """
        Удаляет из переданных данных поля, которые не являются колонками модели.
        Возвращает новый словарь obj_data без удаленных полей.

        Атрибуты:
            obj_data: dict[str, any] - данные для обновления объекта
        """
        model_valid_columns: set[str] = {
            col.name
            for col
            in self.model.__table__.columns
        }
        return {
            k: v
            for k, v
            in obj_data.items()
            if k in model_valid_columns
        }

    def _raise_value_error_not_found(
        self,
        id: int | None = None,
        ids: list[int] | None = None,
    ) -> None:
        """Выбрасывает ValueError."""
        if id is not None:
            detail: str = 'Объект с id {id} не найден'.format(id=id)
        elif ids is not None:
            detail = 'Объекты с id {ids} не найдены'.format(ids=ids)
        else:
            detail = 'Объект не найден'
        raise ValueError(detail)
