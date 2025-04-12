import asyncio
import json
import random
import names

from datetime import datetime, timezone
from typing import Literal

from curl_cffi.requests import AsyncSession, Response
from utils.processing.handlers import require_auth_token
from core.exceptions.base import APIError, SessionRateLimited, ServerError, ProxyForbidden
from loader import config




class APIClient:
    EXTENSION_API_URL = "https://www.aeropres.in/chromeapi/dawn"
    DASHBOARD_API_URL = "https://ext-api.dawninternet.com/chromeapi/dawn"

    def __init__(self, proxy: str = None):
        self.proxy = proxy
        self.session = self._create_session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    def _create_session(self) -> AsyncSession:
        session = AsyncSession(impersonate="chrome131", verify=False)
        session.timeout = 30

        if self.proxy:
            session.proxies = {
                "http": self.proxy,
                "https": self.proxy,
            }

        return session


    async def clear_request(self, url: str) -> Response:
        session = self._create_session()
        return await session.get(url, allow_redirects=True, verify=False)

    @staticmethod
    async def _verify_response(response_data: dict | list):
        if isinstance(response_data, dict):
            if "status" in str(response_data):
                if isinstance(response_data, dict):
                    if response_data.get("status") is False:
                        raise APIError(
                            f"API returned an error: {response_data}", response_data
                        )

            elif "success" in str(response_data):
                if isinstance(response_data, dict):
                    if response_data.get("success") is False:
                        raise APIError(
                            f"API returned an error: {response_data}", response_data
                        )

    async def close_session(self) -> None:
        try:
            await self.session.close()
        except:
            pass

    async def send_request(
        self,
        request_type: Literal["POST", "GET", "OPTIONS"] = "POST",
        api_type: Literal["EXTENSION", "DASHBOARD"] = "EXTENSION",
        method: str = None,
        json_data: dict = None,
        params: dict = None,
        url: str = None,
        headers: dict = None,
        cookies: dict = None,
        verify: bool = True,
        max_retries: int = 2,
        retry_delay: float = 3.0,
    ):
        url = url if url else f"{self.EXTENSION_API_URL}{method}" if api_type == "EXTENSION" else f"{self.DASHBOARD_API_URL}{method}"

        for attempt in range(max_retries):
            try:
                if request_type == "POST":
                    response = await self.session.post(
                        url,
                        json=json_data,
                        params=params,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies,
                    )
                elif request_type == "OPTIONS":
                    response = await self.session.options(
                        url,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies,
                    )
                else:
                    response = await self.session.get(
                        url,
                        params=params,
                        headers=headers if headers else self.session.headers,
                        cookies=cookies,
                    )

                if verify:
                    if response.status_code == 403 and "403 Forbidden" in response.text:
                        raise ProxyForbidden(f"Proxy forbidden - {response.status_code}")
                    elif response.status_code == 403:
                        raise SessionRateLimited("Session is rate limited or blocked by Cloudflare")

                    if response.status_code in (500, 502, 503, 504):
                        raise ServerError(f"Server error - {response.status_code}")

                    try:
                        response_json = response.json()
                        await self._verify_response(response_json)
                        return response_json
                    except json.JSONDecodeError:
                        raise ServerError(f"Failed to decode response, most likely server error")

                return response.text

            except ServerError as error:
                if attempt == max_retries - 1:
                    raise error
                await asyncio.sleep(retry_delay)

            except (APIError, SessionRateLimited, ProxyForbidden):
                raise

            except Exception as error:
                if attempt == max_retries - 1:
                    raise ServerError(
                        f"Failed to send request after {max_retries} attempts: {error}"
                    )
                await asyncio.sleep(retry_delay)

        raise ServerError(f"Failed to send request after {max_retries} attempts")


class DawnExtensionAPI(APIClient):
    def __init__(self, auth_token: str = None, proxy: str = None):
        super().__init__(proxy)
        self.auth_token = auth_token

    async def get_puzzle_id(self, app_id: str) -> str:
        headers = {
            'user-agent': self.user_agent,
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'host': 'ext-api.dawninternet.com',
        }

        response = await self.send_request(
            api_type="DASHBOARD",
            method="/v1/puzzle/get-puzzle",
            request_type="GET",
            params={"appid": app_id},
            headers=headers,
        )
        return response["puzzle_id"]

    async def get_puzzle_image(self, puzzle_id: str, app_id: str) -> str:
        headers = {
            'user-agent': self.user_agent,
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'host': 'ext-api.dawninternet.com',
        }

        response = await self.send_request(
            api_type="DASHBOARD",
            method="/v1/puzzle/get-puzzle-image",
            request_type="GET",
            params={"puzzle_id": puzzle_id, "appid": app_id},
            headers=headers,
        )

        return response.get("imgBase64")


    async def get_app_id(self) -> str:
        headers = {
            'user-agent': self.user_agent,
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'host': 'ext-api.dawninternet.com',
        }

        params = {
            'app_v': '1.1.4',
        }

        response = await self.send_request(
            api_type="DASHBOARD",
            method="/v1/appid/getappid",
            request_type="GET",
            params=params,
            headers=headers,
        )

        return response["data"]["appid"]

    async def register(self, email: str, password: str, captcha_token: str, app_id: str) -> dict:
        headers = {
            'user-agent': self.user_agent,
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': 'https://dashboard.dawninternet.com',
            'referer': 'https://dashboard.dawninternet.com/',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'accept-encoding': 'gzip, deflate, br'
        }

        json_data = {
            'firstname': names.get_first_name(),
            'lastname': names.get_last_name(),
            'email': email,
            'mobile': '',
            'country': random.choice([
                'AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CZ', 'DK',
                'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT', 'LV',
                'LI', 'LT', 'LU', 'MT', 'MD', 'MC', 'ME', 'NL', 'MK', 'NO',
                'PL', 'PT', 'RO', 'RU', 'SM', 'RS', 'SK', 'SI', 'ES', 'SE',
                'CH', 'UA', 'GB', 'VA', 'UA'
            ]),
            'password': password,
            'referralCode': random.choice(config.referral_codes) if config.referral_codes else "",
            'token': captcha_token,
            'isMarketing': False,
            'browserName': 'chrome',
        }

        return await self.send_request(
            api_type="DASHBOARD",
            method="/v2/dashboard/user/validate-register",
            json_data=json_data,
            params={"appid": app_id},
            headers=headers,
        )

    @require_auth_token
    async def keepalive(self, email: str, app_id: str) -> dict | str:
        headers = {
            'user-agent': self.user_agent,
            'content-type': 'application/json',
            'authorization': f'Berear {self.auth_token}',
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'accept-encoding': 'gzip, deflate, br'
        }

        json_data = {
            "username": email,
            "extensionid": "fpdkjdnhkakefebpekbdhillbhonfjjp",
            "numberoftabs": 0,
            "_v": "1.1.4",
        }

        return await self.send_request(
            method="/v1/userreward/keepalive",
            json_data=json_data,
            verify=False,
            headers=headers,
            params={"appid": app_id},
        )

    @require_auth_token
    async def user_info(self, app_id: str) -> dict:
        headers = {
            'authorization': f'Berear {self.auth_token}',
            'user-agent': self.user_agent,
            'content-type': 'application/json',
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'accept-encoding': 'gzip, deflate, br'
        }

        response = await self.send_request(
            url="https://www.aeropres.in/api/atom/v1/userreferral/getpoint",
            request_type="GET",
            headers=headers,
            params={"appid": app_id},
        )

        return response["data"]

    async def verify_registration(self, key: str, captcha_token: str) -> dict:
        headers = {
            'user-agent': self.user_agent,
            'content-type': 'application/json',
            'accept': '*/*',
            'origin': 'https://verify.dawninternet.com',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'accept-encoding': 'gzip, deflate, br'
        }

        return await self.send_request(
            url='https://verify.dawninternet.com/chromeapi/dawn/v1/userverify/verifycheck',
            json_data={"token": captcha_token},
            headers=headers,
            params={"key": key},
        )

    async def resend_verify_link(self, email: str, puzzle_id: str, answer: str, app_id: str) -> dict:
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ru;q=0.8',
            'content-type': 'application/json',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'user-agent': self.user_agent,
        }

        json_data = {
            'username': email,
            'puzzle_id': puzzle_id,
            'ans': answer,
        }

        return await self.send_request(
            method="/v1/user/resendverifylink/v2",
            json_data=json_data,
            params={"appid": app_id},
            headers=headers,
        )

    @require_auth_token
    async def complete_tasks(self, app_id: str, tasks: list[str] = None, delay: int = 1) -> None:
        if not tasks:
            tasks = ["telegramid", "discordid", "twitter_x_id"]

        headers = {
            'authorization': f'Brearer {self.auth_token}',
            'user-agent': self.user_agent,
            'content-type': 'application/json',
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'accept-encoding': 'gzip, deflate, br'
        }

        for task in tasks:
            await self.send_request(
                method="/v1/profile/update",
                json_data={task: task},
                headers=headers,
                params={"appid": app_id},
            )

            await asyncio.sleep(delay)

    async def verify_session(self) -> tuple[bool, str]:
        try:
            await self.user_info()
            return True, "Session is valid"

        except ServerError:
            return True, "Server error"

        except APIError as error:
            return False, str(error)

    async def login(self, email: str, password: str, puzzle_id: str, answer: str, app_id: str) -> str:
        headers = {
            'user-agent': self.user_agent,
            'content-type': 'application/json',
            'accept': '*/*',
            'origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'accept-language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'accept-encoding': 'gzip, deflate, br'
        }

        current_time = datetime.now(timezone.utc)
        formatted_datetime_str = (
            current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )

        json_data = {
            "username": email,
            "password": password,
            "logindata": {
                '_v': {
                    'version': '1.1.4',
                },
                'datetime': formatted_datetime_str,
            },
            "puzzle_id": puzzle_id,
            "ans": answer,
            "appid": app_id,
        }

        response = await self.send_request(
            method="/v1/user/login/v2",
            json_data=json_data,
            params={"appid": app_id},
            headers=headers,
        )

        bearer = response.get("data", {}).get("token")
        if bearer:
            return bearer
        else:
            raise APIError(f"Failed to login: {response}")
