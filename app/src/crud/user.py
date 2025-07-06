from sqlalchemy.orm.strategy_options import selectinload
from sqlalchemy.sql import select
from sqlalchemy.sql.selectable import Select

from app.src.database.base_async_crud import (
    AsyncSession,
    BaseAsyncCrud,
)
from app.src.models.user import User
from app.src.models.user_statistic import UserStatistic


class UserCrud(BaseAsyncCrud):
    """Класс CRUD запросов к базе данных к таблице User."""

    async def create(self, *, obj_data, session, perform_cleanup = True, perform_commit = True):
        """
        Создает один объект в базе данных.
        Изменяет значение "id_telegram" в тип данных str.

        Создает объект статистики достижений.
        """
        from app.src.crud.user_achievement import user_achievement_crud
        from app.src.crud.user_statistic import user_statistic_crud

        if 'id_telegram' in obj_data:
            obj_data['id_telegram'] = str(obj_data['id_telegram'])

        user: User = await super().create(obj_data=obj_data, session=session, perform_cleanup=perform_cleanup, perform_commit=False)
        await user_achievement_crud.create(obj_data={'user_id': user.id}, session=session, perform_commit=False)
        await user_statistic_crud.create(obj_data={'user_id': user.id}, session=session, perform_commit=perform_commit)

        return user

    async def retrieve_by_id_telegram(
        self,
        *,
        obj_id_telegram: int |str,
        session: AsyncSession,
    ) -> User | None:
        """
        Получает один объект из базы данных по указанному id_telegram.
        """
        query: Select = select(User).where(User.id_telegram == str(obj_id_telegram))
        return (await session.execute(query)).scalars().first()

    async def retrieve_players_statistic(
        self,
        *,
        session: AsyncSession,
    ) -> list[User] | None:
        """
        Получает список игроков с их статистикой из базы данных.
        """
        query: Select = (
            select(User)
            .join(User.statistics)
            .options(
                selectinload(User.achievements),
                selectinload(User.statistics),
            )
            .order_by(
                UserStatistic.top_score.desc(),
                UserStatistic.total_wins.desc(),
                UserStatistic.total_quits.asc(),
                UserStatistic.total_games.asc(),
                UserStatistic.user_id.asc(),
            )
        )
        return (await session.execute(query)).scalars().all()


user_crud: UserCrud = UserCrud(
    model=User,
    unique_columns=('id_telegram',),
    unique_columns_err='Пользователь с таким id_telegram уже добавлен в базу данных',
)
