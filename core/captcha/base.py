import asyncio
import httpx

from typing import Optional


class CaptchaSolverBase:
    def __init__(
            self,
            api_key: str,
            max_attempts: int = 10,
            soft_id: int = None,
            base_url: str = "",
    ):
        self.api_key = api_key
        self.max_attempts = max_attempts
        self.soft_id = soft_id

        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10, verify=False)

    async def solve_cloudflare(self, site_key: str, page_url: str) -> tuple[bool, Optional[str]] | tuple[bool, str]:
        captcha_type = "TurnstileTaskProxyless"
        if self.base_url == "https://api.capsolver.com":
            captcha_type = "AntiTurnstileTaskProxyLess"

        captcha_data = {
            "clientKey": self.api_key,
            "task": {
                "type": captcha_type,
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        }

        if self.soft_id is not None:
            captcha_data["softId"] = self.soft_id

        try:
            resp = await self.client.post(f"{self.base_url}/createTask", json=captcha_data)
            resp.raise_for_status()
            data = resp.json()

            if data.get("errorId") == 0:
                task_id = data.get("taskId")
                return await self.get_captcha_result(task_id)
            return False, data.get("errorDescription", "Unknown error")

        except httpx.HTTPStatusError as err:
            return False, f"HTTP error: {err}"
        except httpx.TimeoutException:
            return False, "Request timed out"
        except Exception as err:
            return False, f"Unexpected error: {err}"

    async def get_captcha_result(self, task_id: int | str) -> tuple[bool, Optional[str]] | tuple[bool, str]:
        for _ in range(self.max_attempts):
            try:
                resp = await self.client.post(f"{self.base_url}/getTaskResult", json={"clientKey": self.api_key, "taskId": task_id})
                resp.raise_for_status()
                result = resp.json()

                if result.get("errorId") != 0:
                    return False, result.get("errorDescription", "Unknown error")

                if result.get("status") == "ready":
                    solution = result["solution"].get("token") or result["solution"].get("text") or result["solution"].get("gRecaptchaResponse")
                    return True, solution

                await asyncio.sleep(3)

            except httpx.HTTPStatusError as err:
                return False, f"HTTP error: {err}"
            except Exception as err:
                return False, f"Unexpected error: {err}"

        return False, "Max time for solving exhausted"


class AntiCaptchaSolver(CaptchaSolverBase):
    def __init__(self, api_key: str, base_url: str, max_attempts: int = 10):
        super().__init__(api_key, max_attempts, soft_id=1201, base_url=base_url)


class TwoCaptchaSolver(CaptchaSolverBase):
    def __init__(self, api_key: str, base_url: str, max_attempts: int = 10):
        super().__init__(api_key, max_attempts, soft_id=4706, base_url=base_url)


class CapmonsterSolver(CaptchaSolverBase):
    def __init__(self, api_key: str, base_url: str, max_attempts: int = 10):
        super().__init__(api_key, max_attempts, soft_id=None, base_url=base_url)


class CapsolverSolver(CaptchaSolverBase):
    def __init__(self, api_key: str, base_url: str, max_attempts: int = 10):
        super().__init__(api_key, max_attempts, soft_id=None, base_url=base_url)
