import asyncio
import random

from typing import List, Callable, Optional, Any, Set
from loguru import logger

from loader import config, semaphore, file_operations
from core.bot import Bot
from models import Account
from utils import Progress
from console import Console
from database import initialize_database


class ApplicationManager:
    def __init__(self):
        self.accounts_with_initial_delay: Set[str] = set()
        self.module_map = {
            "register": (config.accounts_to_register, self._process_registration),
            "farm": (config.accounts_to_farm, self._process_farm),
            "complete_tasks": (config.accounts_to_farm, self._process_complete_tasks),
            "export_stats": (config.accounts_to_farm, self._process_export_stats),
            "re_verify_accounts": (config.accounts_to_reverify, self._process_reverify),
        }

    async def initialize(self) -> None:
        await initialize_database()
        await file_operations.setup_files()
        self.reset_initial_delays()

    def reset_initial_delays(self) -> None:
        self.accounts_with_initial_delay.clear()

    async def _safe_execute_module(
            self,
            account: Account,
            process_func: Callable,
            progress: Optional[Progress] = None
    ) -> Any:
        try:
            async with semaphore:
                bot = Bot(account)
                await account.init_values()

                try:
                    if config.delay_before_start.min > 0:
                        should_delay = (
                                process_func != self._process_farm or
                                account.email not in self.accounts_with_initial_delay
                        )

                        if should_delay:
                            random_delay = random.randint(
                                config.delay_before_start.min,
                                config.delay_before_start.max
                            )
                            logger.info(f"Account: {account.email} | Sleep for {random_delay} sec")
                            await asyncio.sleep(random_delay)

                            if process_func == self._process_farm:
                                self.accounts_with_initial_delay.add(account.email)

                    result = await process_func(bot)

                    if progress is not None and process_func != self._process_farm:
                        progress.increment()
                        logger.debug(f"Progress: {progress.processed}/{progress.total}")

                    return result
                finally:
                    await bot.close_session()

        except Exception as e:
            logger.exception(e)
            logger.error(f"Error processing account {account.email}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _execute_module_for_accounts(
            self,
            accounts: List[Account],
            process_func: Callable
    ) -> tuple[Any]:
        progress = Progress(len(accounts))
        if process_func != self._process_farm:
            logger.debug(f"Progress: 0/{progress.total}")

        tasks = [
            self._safe_execute_module(account, process_func, progress)
            for account in accounts
        ]
        return await asyncio.gather(*tasks)

    @staticmethod
    async def _process_registration(bot: Bot) -> None:
        operation_result = await bot.process_registration()
        await file_operations.export_result(operation_result, "register")

    @staticmethod
    async def _process_reverify(bot: Bot) -> None:
        operation_result = await bot.process_reverify_email()
        await file_operations.export_result(operation_result, "re-verify")

    @staticmethod
    async def _process_farm(bot: Bot) -> None:
        await bot.process_farming()

    @staticmethod
    async def _process_export_stats(bot: Bot) -> None:
        data = await bot.process_get_user_info()
        await file_operations.export_stats(data)

    @staticmethod
    async def _process_complete_tasks(bot: Bot) -> None:
        operation_result = await bot.process_complete_tasks()
        await file_operations.export_result(operation_result, "tasks")

    async def _farm_continuously(self, accounts: List[Account]) -> None:
        while True:
            random.shuffle(accounts)
            await self._execute_module_for_accounts(accounts, self._process_farm)
            await asyncio.sleep(5)

    async def run(self) -> None:
        await self.initialize()

        while True:
            Console().build()

            if config.module not in self.module_map:
                logger.error(f"Unknown module: {config.module}")
                break

            accounts, process_func = self.module_map[config.module]
            random.shuffle(accounts)

            if not accounts:
                logger.error(f"No accounts for {config.module}")
                input("\nPress Enter to continue...")
                continue

            if config.module == "farm":
                await self._farm_continuously(accounts)
            else:
                await self._execute_module_for_accounts(accounts, process_func)
                input("\nPress Enter to continue...")
