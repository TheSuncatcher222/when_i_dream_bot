from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Dirs:
    """Класс представления путей и папок."""

    # Base.
    DIR_SRC: Path = Path(__file__).parent.parent

    # Res.
    DIR_RES: Path = DIR_SRC / 'res'

    CHARACTERS: Path = 'characters'
    RULES: Path = 'rules'
    WORDS: Path = 'words'
    DIR_CHARACTERS: Path = DIR_RES / CHARACTERS
    DIR_RULES: Path = DIR_RES / RULES
    DIR_WORDS: Path = DIR_RES / WORDS

    @classmethod
    def get_all_cards(cls) -> list[Path]:
        return (
            cls.DIR_CHARACTERS,
            cls.DIR_RULES,
            cls.DIR_WORDS,
        )


class Settings(BaseSettings):
    """Класс представления переменных окружения."""

    model_config = SettingsConfigDict(
        env_file='../../../.env',
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
    ADMIN_IDS: list[str]
    ADMIN_NOTIFY_ID: str
    BOT_TOKEN: str
    DEBUG_DB: bool = False
    DEBUG_LOGGING: bool = False


settings = Settings()


class TimeIntervals:
    """Класс представления таймаутов."""

    # Seconds.

    SECONDS_IN_1_MINUTE: int = 60
    SECONDS_IN_1_HOUR: int = SECONDS_IN_1_MINUTE * 60
    SECONDS_IN_1_DAY: int = SECONDS_IN_1_HOUR * 24
