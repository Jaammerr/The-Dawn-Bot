import asyncio
from typing import Any, Tuple
import httpx


class AntiCaptchaImageSolver:
    BASE_URL = "https://api.anti-captcha.com"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10)

    async def solve(self, image: str) -> Tuple[str, bool]:
        try:
            captcha_data = {
                "clientKey": self.api_key,
                "softId": 1201,
                "task": {
                    "type": "ImageToTextTask",
                    "body": image,
                    "phrase": False,
                    "case": True,
                    "numeric": 0,
                    "math": False,
                    "minLength": 6,
                    "maxLength": 6,
                    "comment": "Pay close attention to the letter case.",
                },
            }

            resp = await self.client.post(
                f"{self.BASE_URL}/createTask", json=captcha_data
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("errorId") == 0:
                return await self.get_captcha_result(data.get("taskId"))
            return data.get("errorDescription"), False

        except httpx.HTTPStatusError as err:
            return f"HTTP error occurred: {err}", False
        except Exception as err:
            return f"An unexpected error occurred: {err}", False

    async def get_captcha_result(self, task_id: int | str) -> Tuple[Any, bool]:
        for _ in range(10):
            try:
                resp = await self.client.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id},
                )
                resp.raise_for_status()
                result = resp.json()

                if result.get("errorId") != 0:
                    return result.get("errorDescription"), False

                if result.get("status") == "ready":
                    return result["solution"].get("text", ""), True

                await asyncio.sleep(3)

            except httpx.HTTPStatusError as err:
                return f"HTTP error occurred: {err}", False
            except Exception as err:
                return f"An unexpected error occurred: {err}", False

        return "Max time for solving exhausted", False

    async def report_bad(self, task_id: int | str) -> Tuple[Any, bool]:
        try:
            resp = await self.client.post(
                f"{self.BASE_URL}/reportIncorrectImageCaptcha",
                json={"clientKey": self.api_key, "taskId": task_id},
            )
            resp.raise_for_status()
            return resp.json(), True
        except httpx.HTTPStatusError as err:
            return f"HTTP error occurred: {err}", False
        except Exception as err:
            return f"An unexpected error occurred: {err}", False
