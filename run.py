import asyncio
import random
import sys

from typing import Callable, Coroutine, Any
from loguru import logger
from loader import config, semaphore
from core.bot import Bot
from models import Account
from utils import export_results, setup
from console import Console
from database import initialize_database



async def run_module_safe(
    account: Account, process_func: Callable[[Bot], Coroutine[Any, Any, Any]]
) -> Any:
    async with semaphore:
        return await process_func(Bot(account))


async def process_registration(bot: Bot) -> tuple[str, str, bool]:
    status = await bot.process_registration()
    await bot.close_session()
    return bot.account_data.email, bot.account_data.password, status


async def process_farming(bot: Bot) -> None:
    await bot.process_farming()
    await bot.close_session()


async def process_complete_tasks(bot: Bot) -> None:
    await bot.process_complete_tasks()
    await bot.close_session()


# async def export_account_wallet(bot: Bot) -> tuple[str, str]:
#     return bot.account_data.email, await bot.export_account_wallet()


async def run_module(accounts, process_func, export_name: str = None):
    tasks = [run_module_safe(account, process_func) for account in accounts]
    results = await asyncio.gather(*tasks)
    if export_name:
        export_results(results, export_name)
    return results


async def run():
    await initialize_database()

    while True:
        Console().build()

        if config.module == "register":
            if not config.accounts_to_register:
                logger.error("No accounts to register")
                break
            await run_module(
                config.accounts_to_register, process_registration, "register"
            )

        elif config.module in ("farm_cycle", "farm_one_time"):
            if not config.accounts_to_farm:
                logger.error("No accounts to farm")
                break

            random.shuffle(config.accounts_to_farm)

            if config.module == "farm_one_time":
                await run_module(config.accounts_to_farm, process_farming)
            else:
                while True:
                    await run_module(config.accounts_to_farm, process_farming)

        elif config.module == "complete_tasks":
            if not config.accounts_to_farm:
                logger.error("No accounts to complete tasks")
                break

            random.shuffle(config.accounts_to_farm)
            await run_module(config.accounts_to_farm, process_complete_tasks)

        # elif config.module == "export_wallets":
        #     if not config.accounts_to_farm:
        #         logger.error("No accounts to export wallets")
        #         break
        #
        #     await run_module(
        #         config.accounts_to_farm, export_account_wallet, "export_wallets"
        #     )

        input("\n\nPress Enter to continue...")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    setup()
    asyncio.run(run())
