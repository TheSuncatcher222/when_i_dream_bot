from aiogram import (
    Dispatcher,
    Router,
)
from aiogram.fsm.storage.memory import MemoryStorage

from app.src.bot.routers.fallback import router as fallback
from app.src.bot.routers.start import router as start

dp: Dispatcher = Dispatcher(
    storage=MemoryStorage(),
)

routers: tuple[Router] = ()

# WARNING! Нельзя редактировать:
routers: tuple[Router] = (
    start,
    *routers,
    fallback,
)

for router in routers:
    dp.include_router(router)
