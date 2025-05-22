from aiogram import Bot

from app.src.config.config import settings

bot: Bot = Bot(token=settings.BOT_TOKEN)
