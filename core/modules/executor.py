from core.bot.base import Bot
from loader import file_operations
from models import Account, OperationResult


class ModuleExecutor:
    def __init__(self, account: Account):
        self.account = account
        self.bot = Bot(account)

    async def _process_login(self) -> None:
        operation_result = await self.bot.process_login()
        if isinstance(operation_result, dict):
            await file_operations.export_result(operation_result, "login")

    # async def _process_complete_tasks(self) -> None:
    #     operation_result = await self.bot.process_complete_tasks()
    #     if isinstance(operation_result, dict):
    #         await file_operations.export_result(operation_result, "tasks")

    async def _process_export_stats(self) -> None:
        operation_result = await self.bot.process_export_stats()
        if isinstance(operation_result, dict):
            await file_operations.export_stats(operation_result)

    async def _process_farm(self) -> None:
        await self.bot.process_farm()
