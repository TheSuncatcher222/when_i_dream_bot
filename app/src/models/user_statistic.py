from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql import expression

from app.src.database.database import (
    Base,
    TableNames,
)

if TYPE_CHECKING:
    from app.src.models.user import User


class UserStatistic(Base):
    """Декларативная модель представления статистики пользователя."""

    __tablename__ = TableNames.user_statistic
    __table_args__ = {'comment': 'Статистика пользователей'}

    # Primary keys.

    id: Mapped[int] = mapped_column(
        comment='ID',
        primary_key=True,
        autoincrement=True,
    )

    # Fields.

    last_game_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment='Дата и время последней игры',
        nullable=True,
        server_default=expression.null(),
    )
    top_penalties: Mapped[int] = mapped_column(
        comment='Общее количество штрафов',
        server_default='0',
    )
    total_quits: Mapped[int] = mapped_column(
        comment='Общее количество выходов из игры',
        server_default='0',
    )
    top_score: Mapped[int] = mapped_column(
        comment='Общее количество очков',
        server_default='0',
    )
    top_score_buka: Mapped[int] = mapped_column(
        comment='Общее количество очков за буку',
        server_default='0',
    )
    top_score_fairy: Mapped[int] = mapped_column(
        comment='Общее количество очков за фею',
        server_default='0',
    )
    top_score_sandman: Mapped[int] = mapped_column(
        comment='Общее количество очков за песочного человека',
        server_default='0',
    )
    top_score_sleeper: Mapped[int] = mapped_column(
        comment='Общее количество очков за сновидца',
        server_default='0',
    )
    total_wins: Mapped[int] = mapped_column(
        comment='Общее количество побед',
        server_default='0',
    )

    # Foreign keys.

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            column=f'{TableNames.user}.id',
            name=f'{TableNames.user_statistic}_{TableNames.user}_fkey',
            ondelete='CASCADE',
        ),
        comment='ID пользователя',
        nullable=False,
        unique=True,
    )

    # Relationships.

    user: Mapped['User'] = relationship(
        'User',
        back_populates='statistics',
    )
