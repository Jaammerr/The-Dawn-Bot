import asyncio
import random

from typing import List, Any, Set, Optional, Callable, Coroutine
from loguru import logger

from core.modules.executor import ModuleExecutor
from loader import config, file_operations, semaphore, proxy_manager
from models import Account
from utils import Progress
from console import Console
from database import initialize_database, Accounts


class ApplicationManager:
    def __init__(self):
        self.accounts_with_initial_delay: Set[str] = set()
        self.module_map = {
            "login": (config.accounts_to_login, self._execute_module_for_accounts),
            "farm": (config.accounts_to_farm, self._farm_continuously),
            # "complete_tasks": (config.accounts_to_complete_tasks, self._execute_module_for_accounts),
            "export_stats": (config.accounts_to_export_stats, self._execute_module_for_accounts),
        }

    @staticmethod
    async def initialize() -> None:
        logger.info(f"Initializing database..")
        await initialize_database()
        logger.success(f"Database initialized")
        await file_operations.setup_files()


    async def _execute_module_for_accounts(
        self, accounts: List[Account], module_name: str
    ) -> list[Any]:
        progress = Progress(len(accounts))
        if module_name != "farm":
            logger.debug(f"Progress: 0/{progress.total}")

        if module_name == "export_stats":
            await file_operations.setup_stats()

        tasks = []
        for account in accounts:
            executor = ModuleExecutor(account)
            module_func = getattr(executor, f"_process_{module_name}")
            tasks.append(self._safe_execute_module(account, module_func, progress))

        return await asyncio.gather(*tasks)

    async def _safe_execute_module(
            self, account: Account, module_func: Callable, progress: Progress
    ) -> Optional[dict]:
        try:
            async with semaphore:
                if (
                    config.attempts_and_delay_settings.delay_before_start.min > 0
                    and config.attempts_and_delay_settings.delay_before_start.max > 0
                ):
                    if account.email not in self.accounts_with_initial_delay:
                        random_delay = random.randint(
                            config.attempts_and_delay_settings.delay_before_start.min, config.attempts_and_delay_settings.delay_before_start.max
                        )
                        logger.info(
                            f"Account: {account.email} | Initial delay set to {random_delay} seconds | Execution will start in {random_delay} seconds"
                        )
                        self.accounts_with_initial_delay.add(account.email)
                        await asyncio.sleep(random_delay)

                result = await module_func()
                if module_func.__name__ != "_process_farm":
                    progress.increment()
                    logger.debug(f"Progress: {progress.processed}/{progress.total}")

                return result

        except Exception as e:
            logger.error(f"Error processing account {account.email}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _farm_continuously(self, accounts: List[Account]) -> None:
        while True:
            accounts_with_expired_sleep, accounts_waiting_sleep = await Accounts().get_accounts_stats(
                emails=[
                    account.email for account in accounts
                ]
            )

            if accounts_with_expired_sleep == 0 and accounts_waiting_sleep == 0:
                logger.warning("No accounts to farming found, either you forgot to log in them or the file farm_accounts.txt is empty")
                input("Press Enter to continue...")
                return

            if accounts_with_expired_sleep > 0:
                if config.application_settings.shuffle_accounts:
                    random.shuffle(accounts)

                logger.info(f"{accounts_with_expired_sleep} accounts are ready to farm. Executing farm module for them.")
                await self._execute_module_for_accounts(accounts, "farm")
            else:
                logger.info(f"{accounts_waiting_sleep} accounts are sleeping. Waiting for any account to wake up.")

            await asyncio.sleep(10)

    @staticmethod
    async def _clean_accounts_proxies() -> None:
        logger.info("Cleaning all accounts proxies..")
        try:
            cleared_count = await Accounts().clear_all_accounts_proxies()
            logger.success(f"Successfully cleared proxies for {cleared_count} accounts")

        except Exception as e:
            logger.error(f"Error while clearing accounts proxies: {str(e)}")

    async def run(self) -> None:
        await self.initialize()

        while True:
            Console().build()

            if config.module == "clean_accounts_proxies":
                await self._clean_accounts_proxies()
                input("\nPress Enter to continue...")
                continue

            if config.module not in self.module_map:
                logger.error(f"Unknown module: {config.module}")
                break

            proxy_manager.load_proxy(config.proxies)
            accounts, process_func = self.module_map[config.module]
            random.shuffle(accounts)

            if not accounts:
                logger.error(f"No accounts for {config.module}")
                input("\nPress Enter to continue...")
                continue

            if config.module == "farm":
                await self._farm_continuously(accounts)
            else:
                await self._execute_module_for_accounts(accounts, config.module)
                input("\nPress Enter to continue...")
