from aiogram import (
    Dispatcher,
    Router,
)
from aiogram.fsm.storage.memory import MemoryStorage

from app.src.bot.routers.fallback import router as fallback
from app.src.bot.routers.help import router as help
from app.src.bot.routers.ping import router as ping
from app.src.bot.routers.start import router as start

dp: Dispatcher = Dispatcher(
    storage=MemoryStorage(),
)

routers: tuple[Router] = (
    help,
    ping,
)

for router in (start, *routers, fallback):
    dp.include_router(router)
