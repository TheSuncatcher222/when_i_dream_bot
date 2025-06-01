from enum import StrEnum
from pprint import pformat
import traceback

from app.src.bot.bot import (
    Bot,
    bot,
)
from app.src.config.config import settings

TELEGRAM_MESSAGE_MAX_LEN: int = 4000


class LoggerIcons(StrEnum):
    """
    Класс представления иконок сообщений логов.
    """

    CRITICAL: str = '❌'
    INFO: str = 'i️'
    WARNING: str = '⚠️'


class TelegramLogger:
    """
    Класс логирования в Telegram-сообщения.
    """

    def __init__(self):
        self.bot: Bot = bot
        self.admin_chat_id: int = settings.ADMIN_NOTIFY_ID

    async def info(
        self,
        msg: str,
        extra: dict | None = None,
        exc: BaseException | None = None,
    ) -> None:
        await self.__send_message(msg=msg, extra=extra, exc=exc, _type='INFO')

    async def warning(
        self,
        msg: str,
        extra: dict | None = None,
        exc: BaseException | None = None,
    ) -> None:
        await self.__send_message(msg=msg, extra=extra, exc=exc, _type='WARNING')

    async def critical(
        self,
        msg: str,
        extra: dict | None = None,
        exc: BaseException | None = None,
    ) -> None:
        await self.__send_message(msg=msg, extra=extra, exc=exc, _type='CRITICAL')

    async def __send_message(
        self,
        msg: str,
        _type: str,
        extra: dict | None = None,
        exc: BaseException | None = None,
    ) -> None:
        msg: str = f'{LoggerIcons[_type].value} {_type}: {msg}'
        if extra:
            msg += '\n' + pformat(extra, width=50, compact=True)
        if exc:
            tb_prefix: str = '\n\nTraceback:\n'
            tb: str = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            diff: int = TELEGRAM_MESSAGE_MAX_LEN - len(msg) - len(tb_prefix) - len(tb)
            if diff < 0:
                cut: int = (len(tb) + diff) // 2 - len('\n...\n')
                tb: str = tb[:cut] + '\n...\n' + tb[-cut:]
            msg += tb_prefix + tb
        await self.bot.send_message(chat_id=self.admin_chat_id, text=msg)


logger: TelegramLogger = TelegramLogger()
