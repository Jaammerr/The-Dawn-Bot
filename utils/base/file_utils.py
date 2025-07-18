import asyncio
import time
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
                "unlogged": self.base_path / "accounts" / "unlogged_accounts.txt",
                "invalid_proxy": self.base_path / "accounts" / "invalid_proxy_accounts.txt",
            },
            "verify": {
                "success": self.base_path / "re_verify" / "verify_success.txt",
                "failed": self.base_path / "re_verify" / "verify_failed.txt",
            },
            "login": {
                "success": self.base_path / "login" / "login_success.txt",
                "failed": self.base_path / "login" / "login_failed.txt",
            },
        }

    async def setup_files(self):
        self.base_path.mkdir(exist_ok=True)
        for module_name, module_paths in self.module_paths.items():
            for path_key, path in module_paths.items():
                path.parent.mkdir(parents=True, exist_ok=True)

                if module_name == "stats":
                    continue
                else:
                    path.touch(exist_ok=True)

    async def setup_stats(self):
        self.base_path.mkdir(exist_ok=True)

        for module_name, module_paths in self.module_paths.items():
            if module_name == "stats":
                timestamp = int(time.time())

                for path_key, path in module_paths.items():
                    path.parent.mkdir(parents=True, exist_ok=True)

                    if path_key == "base":
                        new_path = path.parent / f"accounts_stats_{timestamp}.csv"
                        self.module_paths[module_name][path_key] = new_path
                        path = new_path

                        async with aiofiles.open(path, "w") as f:
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



    async def export_invalid_account(self, email: str, password: str | None, reason: str):
        if reason not in self.module_paths["accounts"]:
            raise ValueError(f"Unknown reason: {reason}")

        file_path = self.module_paths["accounts"][reason]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, "a") as file:
                    if password:
                        await file.write(f"{email}:{password}\n")
                    else:
                        await file.write(f"{email}\n")
            except IOError as e:
                logger.error(f"Account: {email} | Error writing to file (IOError): {e}")
            except Exception as e:
                logger.error(f"Account: {email} | Error writing to file: {e}")

    async def export_invalid_proxy_account(self, email: str, password: str | None, proxy: str):
        if "invalid_proxy" not in self.module_paths["accounts"]:
            raise ValueError("Invalid proxy path not found in module paths")

        file_path = self.module_paths["accounts"]["invalid_proxy"]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, "a") as file:
                    if password:
                        await file.write(f"{email}:{password}:{proxy}\n")
                    else:
                        await file.write(f"{email}:{proxy}\n")
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
