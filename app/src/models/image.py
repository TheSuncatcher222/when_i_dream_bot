from sqlalchemy import String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.src.database.database import (
    Base,
    TableNames,
)
from app.src.validators.image import ImageParams


class Image(Base):
    """Декларативная модель представления изображения."""

    __tablename__ = TableNames.image
    __table_args__ = {'comment': 'Изображение'}

    # Primary keys.

    id: Mapped[int] = mapped_column(
        comment='ID',
        primary_key=True,
        autoincrement=True,
    )

    # Fields.

    id_telegram: Mapped[str] = mapped_column(
        String(length=ImageParams.ID_TELEGRAM_LEN_MAX),
        comment='id в Telegram',
        unique=True,
    )
    local_path: Mapped[str] = mapped_column(
        String(length=ImageParams.LOCAL_PATH_LEN_MAX),
        comment='путь к изображению',
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(length=ImageParams.NAME_LEN_MAX),
        comment='название',
        unique=True,
    )
    order: Mapped[int] = mapped_column(
        comment='порядковый номер',
    )
    category: Mapped[str] = mapped_column(
        String(length=ImageParams.CATEGORY_LEN_MAX),
        comment='категория',
    )
