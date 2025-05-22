from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql import (
    expression,
    func,
)

from app.src.database.database import (
    Base,
    TableNames,
)
from app.src.validators.user import UserParams

if TYPE_CHECKING:
    from app.src.models.user_achievement import UserAchievement
    from app.src.models.user_statistic import UserStatistic


class User(Base):
    """Декларативная модель представления пользователя."""

    __tablename__ = TableNames.user
    __table_args__ = {'comment': 'Пользователь'}

    # Primary keys.

    id: Mapped[int] = mapped_column(
        comment='ID',
        primary_key=True,
        autoincrement=True,
    )

    # Fields.

    country: Mapped[str] = mapped_column(
        String(length=UserParams.COUNTRY_LEN_MAX),
        comment='страна',
        nullable=True,
        server_default=expression.null(),
    )
    datetime_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment='дата и время старта бота',
        server_default=func.now(),
    )
    datetime_stop: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment='дата и время остановки бота',
        nullable=True,
        server_default=expression.null(),
    )
    id_telegram: Mapped[str] = mapped_column(
        String(length=UserParams.ID_TELEGRAM_LEN_MAX),
        comment='id в Telegram',
        unique=True,
    )
    message_main_last_id: Mapped[int] = mapped_column(
        comment='id последнего сообщения "Главная"',
        nullable=True,
        server_default=expression.null(),
    )
    name_first: Mapped[str] = mapped_column(
        String(length=UserParams.NAME_FIRST_LEN_MAX),
        comment='имя',
        nullable=True,
        server_default=expression.null(),
    )
    name_last: Mapped[str] = mapped_column(
        String(length=UserParams.NAME_LAST_LEN_MAX),
        comment='фамилия',
        nullable=True,
        server_default=expression.null(),
    )
    username: Mapped[str] = mapped_column(
        String(length=UserParams.USERNAME_LEN_MAX),
        comment='username в Telegram',
        nullable=True,
        server_default=expression.null(),
    )

    # Relationships.

    achievements: Mapped['UserAchievement'] = relationship(
        'UserAchievement',
        back_populates='user',
    )
    statistics: Mapped['UserStatistic'] = relationship(
        'UserStatistic',
        back_populates='user',
    )
