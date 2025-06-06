from aiogram import (
    Dispatcher,
    Router,
)
from aiogram.fsm.storage.memory import MemoryStorage

from app.src.bot.routers.fallback import router as fallback
from app.src.bot.routers.help import router as help
from app.src.bot.routers.game_create import router  as game_create
from app.src.bot.routers.game_join import router as game_join
from app.src.bot.routers.ping import router as ping
from app.src.bot.routers.start import router as start
from app.src.bot.routers.statistic import router as statistic
from app.src.bot.routers.sync_images import router as sync_images

dp: Dispatcher = Dispatcher(
    storage=MemoryStorage(),
)

routers: tuple[Router] = (
    help,
    game_create,
    game_join,
    ping,
    statistic,
    sync_images,
)

for router in (*routers, start, fallback):
    dp.include_router(router)
