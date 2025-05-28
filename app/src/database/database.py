"""
Модуль соединения с базой данных через SQLAlchemy.
"""

from typing import AsyncGenerator

from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.src.config.config import settings

DATABASE_ASYNC_URL: str = f'postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.POSTGRES_DB}'
DATABASE_SYNC_URL: str = f'postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.POSTGRES_DB}'

async_engine: AsyncEngine = create_async_engine(
    url=DATABASE_ASYNC_URL,
    echo=settings.DEBUG_DB,
)

async_session_maker: async_sessionmaker = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
)

sync_engine = create_engine(
    DATABASE_SYNC_URL,
    echo=settings.DEBUG_DB,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


class Base(DeclarativeBase):
    """Инициализирует фабрику создания декларативных классов моделей."""


class TableNames:
    """
    Класс представления названий таблиц в базе данных.
    """

    game: str = 'table_game'
    image: str = 'table_image'
    user: str = 'table_user'
    user_statistic: str = 'table_user_statistic'
    user_achievement: str = 'table_user_achievement'


class RedisKeys:
    """Класс представления Redis ключей."""

    __PREFIX_SRC: str = 'src_'

    __PREFIX_GAME: str = __PREFIX_SRC + 'game_'
    GAME_LOBBY: str = __PREFIX_GAME + 'lobby_{number}'

    __PREFIX_CARDS: str = __PREFIX_SRC + 'cards_'
    ROLES: str = __PREFIX_CARDS + 'roles'
    WORDS: str = __PREFIX_CARDS + 'words'


redis_engine: Redis = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB_CACHE,
    decode_responses=True,
)
