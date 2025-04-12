from core.bot.base import Bot
from loader import file_operations
from models import Account


class ModuleExecutor:
    def __init__(self, account: Account):
        self.account = account
        self.bot = Bot(account)

    async def _process_registration(self) -> None:
        operation_result = await self.bot.process_registration()
        await file_operations.export_result(operation_result, "register")

    async def _process_verify(self) -> None:
        operation_result = await self.bot.process_verify()
        await file_operations.export_result(operation_result, "verify")

    async def _process_login(self) -> None:
        operation_result = await self.bot.process_login()
        await file_operations.export_result(operation_result, "login")

    async def _process_complete_tasks(self) -> None:
        operation_result = await self.bot.process_complete_tasks()
        await file_operations.export_result(operation_result, "tasks")

    async def _process_export_stats(self) -> None:
        data = await self.bot.process_export_stats()
        await file_operations.export_stats(data)

    async def _process_farm(self) -> None:
        await self.bot.process_farm()
