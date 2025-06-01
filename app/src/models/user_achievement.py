from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.src.database.database import (
    Base,
    TableNames,
)

if TYPE_CHECKING:
    from app.src.models.user import User


class UserAchievement(Base):
    """Декларативная модель представления достижений пользователя."""

    __tablename__ = TableNames.user_achievement
    __table_args__ = {'comment': 'Достижения пользователей'}

    # Primary keys.

    id: Mapped[int] = mapped_column(
        comment='ID',
        primary_key=True,
        autoincrement=True,
    )

    # Fields.

    nightmare: Mapped[int] = mapped_column(
        comment='Cущий кошмар',
        server_default='0',
    )
    dream_master: Mapped[int] = mapped_column(
        comment='Cон на яву',
        server_default='0',
    )
    top_penalties: Mapped[int] = mapped_column(
        comment='Кайфоломщик',
        server_default='0',
    )
    top_guesser: Mapped[int] = mapped_column(
        comment='Яркие сны',
        server_default='0',
    )
    top_buka: Mapped[int] = mapped_column(
        comment='Бу-бу-бука',
        server_default='0',
    )
    top_fairy: Mapped[int] = mapped_column(
        comment='Крестная фея',
        server_default='0',
    )
    top_sandman: Mapped[int] = mapped_column(
        comment='Лицемерище',
        server_default='0',
    )
    top_score: Mapped[int] = mapped_column(
        comment='Высший разум',
        server_default='0',
    )

    # Foreign keys.

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            column=f'{TableNames.user}.id',
            name=f'{TableNames.user_achievement}_{TableNames.user}_fkey',
            ondelete='CASCADE',
        ),
        comment='ID пользователя',
        nullable=False,
        unique=True,
    )

    # Relationships.

    user: Mapped['User'] = relationship(
        'User',
        back_populates='achievements',
    )
