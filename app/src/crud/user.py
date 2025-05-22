
from sqlalchemy.sql import (
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.sql.selectable import Select

from app.src.database.base_async_crud import (
    AsyncSession,
    BaseAsyncCrud,
)
from app.src.models.user import User


class UserCrud(BaseAsyncCrud):
    """Класс CRUD запросов к базе данных к таблице User."""

    async def create(self, *, obj_data, session, perform_cleanup = True, perform_commit = True):
        """
        Создает один объект в базе данных.
        Изменяет значение "id_telegram" в тип данных str.
        """
        if 'id_telegram' in obj_data:
            obj_data['id_telegram'] = str(obj_data['id_telegram'])
        return await super().create(obj_data=obj_data, session=session, perform_cleanup=perform_cleanup, perform_commit=perform_commit)

    async def retrieve_by_id_telegram(
        self,
        *,
        obj_id_telegram: int |str,
        session: AsyncSession,
    ) -> User | None:
        """
        Получает один объект из базы данных по указанному id_telegram.
        """
        query: Select = select(self.model).where(self.model.id_telegram == str(obj_id_telegram))
        return (await session.execute(query)).scalars().first()


user_crud: UserCrud = UserCrud(
    model=User,
    unique_columns=('id_telegram',),
    unique_columns_err='Пользователь с таким id_telegram уже добавлен в базу данных',
)
