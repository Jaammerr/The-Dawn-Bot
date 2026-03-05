import asyncio
from typing import Any, Optional, Tuple, Union

import httpx


class OnyxCaptchaSolver:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://onyxsolver.com",
        max_attempts: int = 60,
        poll_interval: float = 3.0,
        timeout: float = 30.0,
        proxy: Optional[str] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts
        self.poll_interval = poll_interval

        self.client = httpx.AsyncClient(
            timeout=timeout,
            proxies=(proxy if proxy else None),
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def create_task(
        self,
        website_url: str,
        website_key: str,
        rqdata: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> Tuple[bool, Union[str, str]]:
        url = f"{self.base_url}/api/createTask"

        task: dict[str, Any] = {
            "type": "PopularCaptchaTask" if proxy else "PopularCaptchaTaskProxyless",
            "websiteURL": website_url,
            "websiteKey": website_key,
            "devid": "87PSHLXW"
        }
        if rqdata:
            task["rqdata"] = rqdata
        if proxy:
            task["proxy"] = proxy

        payload = {"clientKey": self.api_key, "task": task}

        try:
            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("errorId") == 0 and "taskId" in data:
                return True, str(data["taskId"])

            return False, data.get("errorDescription") or f"Failed to create task: {data}"

        except httpx.HTTPStatusError as err:
            return False, f"HTTP error while creating task: {err}"

        except httpx.TimeoutException:
            return False, "Timeout error while creating task"

        except Exception as e:
            return False, f"Unexpected error while creating task: {e}"

    async def get_task_result(self, task_id: str) -> Tuple[bool, Union[dict[str, Any], str]]:
        url = f"{self.base_url}/api/getTaskResult"
        payload = {"clientKey": self.api_key, "taskId": task_id}

        for _ in range(self.max_attempts):
            try:
                resp = await self.client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") == "ready" and data.get("solution"):
                    return True, data["solution"]

                if data.get("errorId") not in (None, 0):
                    return False, data.get("errorDescription") or f"Task error: {data}"

                await asyncio.sleep(self.poll_interval)

            except httpx.HTTPStatusError as err:
                return False, f"HTTP error while getting task result: {err}"

            except httpx.TimeoutException:
                return False, "Timeout error while getting task result"

            except Exception as e:
                return False, f"Unexpected error while getting task result: {e}"

        return False, "Max attempts exhausted"

    async def report_task_result(self, task_id: str, result: str) -> Tuple[bool, Union[dict[str, Any], str]]:
        url = f"{self.base_url}/api/reportTaskResult"
        payload = {"clientKey": self.api_key, "taskId": task_id, "result": result}

        try:
            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            return True, resp.json()

        except httpx.HTTPStatusError as err:
            return False, f"HTTP error while reporting result: {err}"

        except httpx.TimeoutException:
            return False, "Timeout error while reporting result"

        except Exception as e:
            return False, f"Unexpected error while reporting result: {e}"

    async def get_balance(self) -> Tuple[bool, Union[float, str]]:
        url = f"{self.base_url}/api/getBalance"
        payload = {"clientKey": self.api_key}

        try:
            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if "balance" in data:
                return True, float(data["balance"])

            if data.get("errorId") not in (None, 0):
                return False, data.get("errorDescription") or f"Balance error: {data}"

            return False, f"Unexpected balance response: {data}"

        except httpx.HTTPStatusError as err:
            return False, f"HTTP error while getting balance: {err}"

        except httpx.TimeoutException:
            return False, "Timeout error while getting balance"

        except Exception as e:
            return False, f"Unexpected error while getting balance: {e}"

    async def solve(
        self,
        website_url: str,
        website_key: str,
        rqdata: Optional[str] = None,
        task_proxy: Optional[str] = None,
    ) -> Tuple[bool, str]:
        success, created = await self.create_task(
            website_url=website_url,
            website_key=website_key,
            rqdata=rqdata,
            proxy=task_proxy,
        )
        if not success:
            return False, created

        task_id = str(created)

        success, solution = await self.get_task_result(task_id)
        if not success:
            return False, solution

        token = None
        if isinstance(solution, dict):
            token = (
                solution.get("gRecaptchaResponse")
                or solution.get("token")
                or solution.get("captchaResponse")
            )

        await self.report_task_result(task_id, result="success")
        return True, token
