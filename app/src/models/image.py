from sqlalchemy import (
    Integer,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)
from sqlalchemy.sql import expression

from app.src.database.database import (
    Base,
    TableNames,
)
from app.src.validators.image import (
    ImageParams,
    ImageCategory,
)


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
    id_telegram_rotated: Mapped[str] = mapped_column(
        String(length=ImageParams.ID_TELEGRAM_LEN_MAX),
        comment='id в Telegram (перевернутое)',
        unique=True,
        nullable=True,
        server_default=expression.null(),
    )
    local_path: Mapped[str] = mapped_column(
        String(length=ImageParams.LOCAL_PATH_LEN_MAX),
        comment='путь',
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        String(length=ImageParams.NAME_LEN_MAX),
        comment='название',
        unique=True,
    )
    category: Mapped[ImageCategory] = mapped_column(
        Integer,
        comment="категория",
    )
