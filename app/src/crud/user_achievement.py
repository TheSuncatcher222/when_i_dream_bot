from sqlalchemy.sql import select
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


user_achievement_crud: UserAchievementCrud = UserAchievementCrud(
    model=UserAchievement,
    unique_columns=('user_id',),
    unique_columns_err='Пользователь с таким user_id уже добавлен в базу данных',
)
