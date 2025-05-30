from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.src.config.config import Timezones
from app.src.database.database import sync_engine

scheduler: AsyncIOScheduler = AsyncIOScheduler(
    timezone=Timezones.MOSCOW,
    executors={'default': AsyncIOExecutor()},
    jobstores={'default': SQLAlchemyJobStore(engine=sync_engine)},
)


class SchedulerJobNames:
    """
    Класс представления названий (id) задач планировщика.
    """

    # Image.
    SYNC_IMAGES: str = 'sync_images'

    # Game.
    GAME_END_ROUND: str = 'game_{number}_end_round'
