import asyncio
import httpx

from typing import Any, Tuple


class AntiCaptchaImageSolver:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10)

        self.create_task_url = "https://api.anti-captcha.com/createTask"
        self.get_task_result_url = "https://api.anti-captcha.com/getTaskResult"

    async def solve(self, image: str) -> Tuple[str, bool]:
        try:

            captcha_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "ImageToTextTask",
                    "body": image,
                    "phrase": False,
                    "case": False,
                    "numeric": 1,
                    "math": True,
                },
            }

            resp = await self.client.post(self.create_task_url, json=captcha_data)

            if resp.status_code == 200:
                if resp.json().get("errorId") == 0:
                    return await self.get_captcha_result(resp.json().get("taskId"))
                return resp.json().get("errorDescription"), False
            else:
                return "Incorrect data", False

        except httpx.RequestError as err:
            return str(err), False

        except Exception as err:
            return str(err), False

    async def get_captcha_result(self, task_id: str) -> Tuple[Any, bool]:
        try:
            for _ in range(10):
                resp = await self.client.post(
                    self.get_task_result_url,
                    json={"clientKey": self.api_key, "taskId": str(task_id)},
                )

                if resp.status_code == 200:
                    result = resp.json()

                    if int(result.get("errorId")) != 0:
                        return result.get("errorDescription"), False

                    if result.get("status") == "ready":
                        return result["solution"].get("text", ""), True

                await asyncio.sleep(5)

        except httpx.RequestError as err:
            return str(err), False

        except Exception as err:
            return str(err), False

        return "Max time for solving exhausted", False
