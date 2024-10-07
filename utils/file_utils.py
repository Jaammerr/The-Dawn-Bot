import asyncio

import aiofiles

from pathlib import Path
from aiocsv import AsyncWriter
from models import ModuleType, OperationResult, StatisticData


# lock = Lock()
#
#
# def verify_files_and_folders(module: str) -> None:
#     if not os.path.exists("./results"):
#         os.makedirs("./results")
#
#     if module == "register":
#         if not os.path.exists("./results/registration_success.txt"):
#             open("./results/registration_success.txt", "w").close()
#         if not os.path.exists("./results/registration_failed.txt"):
#             open("./results/registration_failed.txt", "w").close()
#
#
# async def export_result(result: tuple[str, str, bool], module: str) -> None:
#     async with lock:
#         verify_files_and_folders(module)
#
#         if module == "register":
#             success_path = "./results/registration_success.txt"
#             failed_path = "./results/registration_failed.txt"
#
#             email, password, status = result
#             file_path = success_path if status else failed_path
#
#             async with aiofiles.open(file_path, "a") as file:
#                 await file.write(f"{email}:{password}\n")


class FileOperations:
    def __init__(self, base_path: str = "./results"):
        self.base_path = Path(base_path)
        self.lock = asyncio.Lock()
        self.module_paths: dict[ModuleType, dict[str, Path]] = {
            "register": {
                "success": self.base_path / "registration_success.txt",
                "failed": self.base_path / "registration_failed.txt",
            },
            "tasks": {
                "success": self.base_path / "tasks_success.txt",
                "failed": self.base_path / "tasks_failed.txt",
            },
            "stats": {
                "base": self.base_path / "accounts_stats.csv",
            },
        }

    async def setup_files(self):
        self.base_path.mkdir(exist_ok=True)
        for module_paths in self.module_paths.values():
            for path in module_paths.values():
                path.touch(exist_ok=True)

        async with aiofiles.open(self.module_paths["stats"]["base"], "w") as f:
            writer = AsyncWriter(f)
            await writer.writerow(
                [
                    "Email",
                    "Referral Code",
                    "Points",
                    "Referral Points",
                    "Total Points",
                    "Registration Date",
                    "Completed Tasks",
                ]
            )

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
                print(f"Error writing to file: {e}")

    async def export_stats(self, data: StatisticData):
        file_path = self.module_paths["stats"]["base"]
        async with self.lock:
            try:
                async with aiofiles.open(file_path, mode="a", newline="") as f:
                    writer = AsyncWriter(f)

                    if not data or not data["referralPoint"] or not data["rewardPoint"]:
                        return

                    await writer.writerow(
                        [
                            data["referralPoint"]["email"],
                            data["referralPoint"]["referralCode"],
                            data["rewardPoint"]["points"],
                            data["referralPoint"]["commission"],
                            float(data["rewardPoint"]["points"])
                            + float(data["referralPoint"]["commission"]),
                            data["rewardPoint"]["registerpointsdate"],
                            (
                                True
                                if data["rewardPoint"]["twitter_x_id_points"] == 5000
                                and data["rewardPoint"]["discordid_points"] == 5000
                                and data["rewardPoint"]["telegramid_points"] == 5000
                                else False
                            ),
                        ]
                    )

            except IOError as e:
                print(f"Ошибка при записи в файл: {e}")
