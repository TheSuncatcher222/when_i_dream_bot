from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

DIR_SRC: Path = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Класс представления переменных окружения."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding="UTF-8",
        extra="allow",
    )

    """Настройки базы данных PostgreSQL."""
    DB_HOST: str = 'postgresql'
    DB_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_PASSWORD: str
    POSTGRES_USER: str

    """Настройки базы данных Redis."""
    REDIS_HOST: str = 'redis'
    REDIS_PORT: int = 6379
    REDIS_DB_CACHE: int = 0

    """Настройки Telegram Bot."""
    BOT_ADMIN_IDS: list[str]
    BOT_TOKEN: str
    DEBUG_DB: bool = False
    DEBUG_LOGGING = False


settings = Settings()


class TimeIntervals:
    """Класс представления таймаутов."""

    # Seconds.

    SECONDS_IN_1_MINUTE: int = 60
    SECONDS_IN_1_HOUR: int = SECONDS_IN_1_MINUTE * 60
    SECONDS_IN_1_DAY: int = SECONDS_IN_1_HOUR * 24
