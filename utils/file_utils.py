import asyncio
import aiofiles

from pathlib import Path
from aiocsv import AsyncWriter
from loguru import logger

from models import ModuleType, OperationResult, StatisticData



class FileOperations:
    def __init__(self, base_path: str = "./results"):
        self.base_path = Path(base_path)
        self.lock = asyncio.Lock()
        self.module_paths: dict[ModuleType, dict[str, Path]] = {
            "register": {
                "success": self.base_path / "registration" / "registration_success.txt",
                "failed": self.base_path / "registration" / "registration_failed.txt",
            },
            "tasks": {
                "success": self.base_path / "tasks" / "tasks_success.txt",
                "failed": self.base_path / "tasks" / "tasks_failed.txt",
            },
            "stats": {
                "base": self.base_path / "stats" / "accounts_stats.csv",
            },
            "accounts": {
                "unverified": self.base_path / "accounts" / "unverified_accounts.txt",
                "banned": self.base_path / "accounts" / "banned_accounts.txt",
                "unregistered": self.base_path / "accounts" / "unregistered_accounts.txt",
            },
            "re-verify": {
                "success": self.base_path / "re_verify" / "reverify_success.txt",
                "failed": self.base_path / "re_verify" / "reverify_failed.txt",
            }
        }

    async def setup_files(self):
        self.base_path.mkdir(exist_ok=True)

        for module, paths in self.module_paths.items():
            for path_type, file_path in paths.items():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.touch(exist_ok=True)

        stats_path = self.module_paths["stats"]["base"]
        if stats_path.stat().st_size == 0:
            async with aiofiles.open(stats_path, "w", newline='') as f:
                writer = AsyncWriter(f)
                await writer.writerow([
                    "Email",
                    "Referral Code",
                    "Points",
                    "Referral Points",
                    "Total Points",
                    "Registration Date",
                    "Completed Tasks",
                ])

    async def export_result(self, result: OperationResult, module: ModuleType):
        if module not in self.module_paths:
            raise ValueError(f"Unknown module: {module}")

        file_path = self.module_paths[module][
            "success" if result["status"] else "failed"
        ]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, "a") as file:
                    await file.write(f"{result['identifier']}:{result['data']}\n")
            except IOError as e:
                logger.error(f"Account: {result['identifier']} | Error writing to file (IOError): {e}")
            except Exception as e:
                logger.error(f"Account: {result['identifier']} | Error writing to file: {e}")


    async def export_unverified_email(self, email: str, password: str):
        file_path = self.module_paths["accounts"]["unverified"]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, "a") as file:
                    await file.write(f"{email}:{password}\n")
            except IOError as e:
                logger.error(f"Account: {email} | Error writing to file (IOError): {e}")
            except Exception as e:
                logger.error(f"Account: {email} | Error writing to file: {e}")

    async def export_banned_email(self, email: str, password: str):
        file_path = self.module_paths["accounts"]["banned"]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, "a") as file:
                    await file.write(f"{email}:{password}\n")
            except IOError as e:
                    logger.error(f"Account: {email} | Error writing to file (IOError): {e}")
            except Exception as e:
                logger.error(f"Account: {email} | Error writing to file: {e}")


    async def export_unregistered_email(self, email: str, password: str):
        file_path = self.module_paths["accounts"]["unregistered"]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, "a") as file:
                    await file.write(f"{email}:{password}\n")
            except IOError as e:
                logger.error(f"Account: {email} | Error writing to file (IOError): {e}")
            except Exception as e:
                logger.error(f"Account: {email} | Error writing to file: {e}")


    async def export_stats(self, data: StatisticData):
        file_path = self.module_paths["stats"]["base"]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, mode="a", newline="") as f:
                    writer = AsyncWriter(f)

                    if not data or not data["referralPoint"] or not data["rewardPoint"]:
                        return

                    task_points = 0
                    if data["rewardPoint"]["twitter_x_id_points"] == 5000 and data["rewardPoint"]["discordid_points"] == 5000 and data["rewardPoint"]["telegramid_points"] == 5000:
                        task_points = 15000

                    await writer.writerow(
                        [
                            data["referralPoint"]["email"],
                            data["referralPoint"]["referralCode"],
                            data["rewardPoint"]["points"],
                            data["referralPoint"]["commission"],
                            float(data["rewardPoint"]["points"])
                            + float(data["referralPoint"]["commission"]) + task_points,
                            data["rewardPoint"]["registerpointsdate"],
                            True if task_points == 15000 else False,
                        ]
                    )

            except IOError as e:
                logger.error(f"Error writing to file (IOError): {e}")

            except Exception as e:
                logger.error(f"Error writing to file: {e}")
