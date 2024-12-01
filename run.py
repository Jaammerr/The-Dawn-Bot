import asyncio
import random
import sys
from typing import Callable, Coroutine, Any, List, Set

from loguru import logger
from loader import config, semaphore, file_operations, single_semaphore
from core.bot import Bot
from models import Account
from utils import setup
from console import Console
from database import initialize_database


accounts_with_initial_delay: Set[str] = set()


async def run_module_safe(
        account: Account, process_func: Callable[[Bot], Coroutine[Any, Any, Any]]
) -> Any:
    global accounts_with_initial_delay

    async with semaphore if config.redirect_settings.enabled is False else single_semaphore:
        bot = Bot(account)
        try:
            if config.delay_before_start.min > 0:
                if process_func == process_farming and account.email not in accounts_with_initial_delay:
                    random_delay = random.randint(config.delay_before_start.min, config.delay_before_start.max)
                    logger.info(f"Account: {account.email} | Initial farming delay: {random_delay} sec")
                    await asyncio.sleep(random_delay)
                    accounts_with_initial_delay.add(account.email)

                elif process_func != process_farming:
                    random_delay = random.randint(config.delay_before_start.min, config.delay_before_start.max)
                    logger.info(f"Account: {account.email} | Sleep for {random_delay} sec")
                    await asyncio.sleep(random_delay)

            result = await process_func(bot)
            return result
        finally:
            await bot.close_session()


async def process_registration(bot: Bot) -> None:
    operation_result = await bot.process_registration()
    await file_operations.export_result(operation_result, "register")


async def process_re_verify_accounts(bot: Bot) -> None:
    operation_result = await bot.process_reverify_email()
    await file_operations.export_result(operation_result, "re-verify")


async def process_farming(bot: Bot) -> None:
    await bot.process_farming()


async def process_export_stats(bot: Bot) -> None:
    data = await bot.process_get_user_info()
    await file_operations.export_stats(data)


async def process_complete_tasks(bot: Bot) -> None:
    operation_result = await bot.process_complete_tasks()
    await file_operations.export_result(operation_result, "tasks")


async def run_module(
        accounts: List[Account], process_func: Callable[[Bot], Coroutine[Any, Any, Any]]
) -> tuple[Any]:
    tasks = [run_module_safe(account, process_func) for account in accounts]
    return await asyncio.gather(*tasks)


async def farm_continuously(accounts: List[Account]) -> None:
    while True:
        random.shuffle(accounts)
        await run_module(accounts, process_farming)
        await asyncio.sleep(10)


def reset_initial_delays():
    global accounts_with_initial_delay
    accounts_with_initial_delay.clear()


async def run() -> None:
    await initialize_database()
    await file_operations.setup_files()
    reset_initial_delays()

    module_map = {
        "register": (config.accounts_to_register, process_registration),
        "farm": (config.accounts_to_farm, farm_continuously),
        "complete_tasks": (config.accounts_to_farm, process_complete_tasks),
        "export_stats": (config.accounts_to_farm, process_export_stats),
        "re_verify_accounts": (config.accounts_to_reverify, process_re_verify_accounts),
    }

    while True:
        Console().build()

        if config.module not in module_map:
            logger.error(f"Unknown module: {config.module}")
            break

        accounts, process_func = module_map[config.module]

        if not accounts:
            logger.error(f"No accounts for {config.module}")
            break

        if config.module == "farm":
            await process_func(accounts)
        else:
            await run_module(accounts, process_func)
            input("\n\nPress Enter to continue...")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    setup()
    asyncio.run(run())
