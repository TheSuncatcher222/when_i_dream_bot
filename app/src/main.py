from asyncio import run as asyncio_run
from os import path as os_path
from sys import path as sys_path

# INFO: добавляет корневую директорию проекта в sys.path для возможности
#       использования абсолютных путей импорта данных из модулей.
sys_path.append(os_path.abspath(os_path.join(os_path.dirname(__file__), '../..')))

from app.src.bot.bot import bot
from app.src.bot.dispatcher import dp
from app.src.scheduler.scheduler import scheduler


async def main() -> None:
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio_run(main())
