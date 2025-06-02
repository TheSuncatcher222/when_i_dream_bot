from typing import Any

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql import (
    select,
    update,
)
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from app.src.database.base_async_crud import BaseAsyncCrud
from app.src.database.database import AsyncSession
from app.src.models.user_achievement import UserAchievement


class UserAchievementCrud(BaseAsyncCrud):
    """Класс CRUD запросов к базе данных к таблице UserAchievement."""

    async def retrieve_by_user_id(
        self,
        *,
        user_id: int,
        session: AsyncSession,
    ) -> UserAchievement | None:
        """Получает один объект из базы данных по указанному id."""
        query: Select = select(UserAchievement).where(UserAchievement.user_id == user_id)
        result: UserAchievement | None = (await session.execute(query)).scalars().first()
        if result is None:
            self._raise_value_error_not_found(id=user_id)
        return result

    async def increment_by_telegram_id(
        self,
        *,
        user_id_telegram: int,
        obj_data: dict[str, Any],
        session: AsyncSession,
        perform_cleanup: bool = True,
        perform_commit: bool = True,
    ) -> UserAchievement | None:
        """Увеличивает счетчик полей одного объекта из базы данных по указанному user_id_telegram."""
        if perform_cleanup:
            obj_data: dict[str, Any] = self._clean_obj_data_non_model_fields(obj_data=obj_data)

        increment_values: dict[str, Any] = {}
        for k, v in obj_data.items():
            attr = getattr(UserAchievement, k, None)
            if isinstance(attr, InstrumentedAttribute) and isinstance(v, (int, float)):
                increment_values[attr] = attr + v

        if increment_values:
            stmt: Update = (
                update(UserAchievement)
                .where(UserAchievement.user.id_telegram == user_id_telegram)
                .values(**increment_values)
                .returning(self.model)
            )
            obj: UserAchievement = (await session.execute(stmt)).scalars().first()
        else:
            obj: None = None

        if perform_commit:
            await session.commit()

        return obj


user_achievement_crud: UserAchievementCrud = UserAchievementCrud(
    model=UserAchievement,
    unique_columns=('user_id',),
    unique_columns_err='Пользователь с таким user_id уже добавлен в базу данных',
)
