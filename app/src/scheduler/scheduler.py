from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.src.database.database import sync_engine

scheduler: AsyncIOScheduler = AsyncIOScheduler(
    executors={'default': AsyncIOExecutor()},
    jobstores={'default': SQLAlchemyJobStore(engine=sync_engine)},
)
