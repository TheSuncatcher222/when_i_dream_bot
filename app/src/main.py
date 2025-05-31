from asyncio import run as asyncio_run
from os import path as os_path
from sys import path as sys_path

# INFO: добавляет корневую директорию проекта в sys.path для возможности
#       использования абсолютных путей импорта данных из модулей.
sys_path.append(os_path.abspath(os_path.join(os_path.dirname(__file__), '../..')))

from app.src.bot.bot import bot
from app.src.bot.dispatcher import dp
from app.src.scheduler.scheduler import scheduler


def on_startup() -> None:
    """Выполняет действия при запуске бота."""
    # INFO. Очистка кэша лобби.
    from app.src.database.database import RedisKeys
    from app.src.utils.redis_app import redis_delete
    redis_delete(key=RedisKeys.GAME_LOBBIES_AVALIABLE)


async def main() -> None:
    on_startup()
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio_run(main())
