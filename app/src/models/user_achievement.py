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
        comment='👺 Cущий кошмар: не отгадал(а) ни одного слова за спящего',
        server_default=0,
    )
    dream_master: Mapped[int] = mapped_column(
        comment='😻 Cон на яву: отгадал(а) все слова за спящего',
        server_default=0,
    )
    top_guesser: Mapped[int] = mapped_column(
        comment='🕵️‍♀️ Яркие сны: угадал(а) больше всего слов за спящего',
        server_default=0,
    )
    top_buka: Mapped[int] = mapped_column(
        comment='🗿 Бу-бу-бука: получил(а) больше всего очков за буку',
        server_default=0,
    )
    top_fairy: Mapped[int] = mapped_column(
        comment='🧚‍♀️ Крестная фея: получил(а) больше всего очков за фею',
        server_default=0,
    )
    top_sandman: Mapped[int] = mapped_column(
        comment='🎭 Лицемерище: получил(а) больше всего очков за песочного человечка',
        server_default=0,
    )
    top_score: Mapped[int] = mapped_column(
        comment='🥇 Высший разум: получил(а) больше всего очков',
        server_default=0,
    )
    penalty_master: Mapped[int] = mapped_column(
        comment='🌚 Кайфоломщик: получил(а) больше всего пенальти',
        server_default=0,
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

    achievements: Mapped['User'] = relationship(
        'User',
        back_populates='achievements',
    )
