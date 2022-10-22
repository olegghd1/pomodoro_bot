import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tgbot.config import token
from tgbot.db.aiosqlite_db import create_table, change_sprint_or_timer_on_finish
from tgbot.handlers.user import register_user_handlers
from tgbot.middlewares.scheduler import SchedulerMiddleware

logger = logging.getLogger(__name__)


def register_all_middlewares(dp, scheduler):
    dp.setup_middleware(SchedulerMiddleware(scheduler))


def register_all_handlers(dp):
    register_user_handlers(dp)


async def set_default_commands(bot: Bot):
    await bot.set_my_commands(
        commands=[
            BotCommand('settings', 'change sprint details, like duration or rest time'),
            BotCommand('cancel', 'cancel current pomodoro or sprint'),
            BotCommand('rules', "what's this all about")
        ]
    )


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format=u'%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s',
    )
    logger.info("Starting bot")

    storage = MemoryStorage()
    bot = Bot(token=token, parse_mode='HTML')
    dp = Dispatcher(bot, storage=storage)

    scheduler = AsyncIOScheduler()

    register_all_middlewares(dp, scheduler)
    register_all_handlers(dp)
    await create_table()
    await set_default_commands(bot)
    # start
    try:
        scheduler.start()
        await dp.start_polling()
    finally:
        await change_sprint_or_timer_on_finish()
        await dp.storage.close()
        await dp.storage.wait_closed()
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Bot stopped!")