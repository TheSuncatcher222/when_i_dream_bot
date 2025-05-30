from typing import Any

from sqlalchemy.sql import (
    select,
    update,
)
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from app.src.database.database import AsyncSession
from app.src.database.base_async_crud import BaseAsyncCrud
from app.src.models.user_statistic import UserStatistic


class UserStatisticCrud(BaseAsyncCrud):
    """Класс CRUD запросов к базе данных к таблице UserStatistic."""

    async def retrieve_by_user_id(
        self,
        *,
        user_id: int,
        session: AsyncSession,
    ) -> UserStatistic | None:
        """Получает один объект из базы данных по указанному id."""
        query: Select = select(UserStatistic).where(UserStatistic.user_id == user_id)
        result: UserStatistic | None = (await session.execute(query)).scalars().first()
        if result is None:
            self._raise_value_error_not_found(id=user_id)
        return result

    async def update_by_user_id(
        self,
        *,
        user_id: int,
        obj_data: dict[str, Any],
        session: AsyncSession,
        perform_check_unique: bool = False,
        perform_cleanup: bool = True,
        perform_commit: bool = True,
    ) -> UserStatistic:
        """Обновляет один объект из базы данных по указанному user_id."""
        if perform_cleanup:
            obj_data: dict[str, Any] = self._clean_obj_data_non_model_fields(obj_data=obj_data)

        query: Select = select(UserStatistic).where(UserStatistic.user_id == user_id)
        if (await session.execute(query)).scalars().first() is None:
            self._raise_value_error_not_found(id=user_id)

        if perform_check_unique:
            await self._check_unique(obj_data=obj_data, session=session)

        stmt: Update = (
            update(UserStatistic)
            .where(UserStatistic.user_id == user_id)
            .values(**obj_data)
            .returning(self.model)
        )
        obj: UserStatistic = (await session.execute(stmt)).scalars().first()

        if perform_commit:
            await session.commit()

        return obj


user_statistic_crud: UserStatisticCrud = UserStatisticCrud(
    model=UserStatistic,
    unique_columns=('user_id',),
    unique_columns_err='Пользователь с таким user_id уже добавлен в базу данных',
)
