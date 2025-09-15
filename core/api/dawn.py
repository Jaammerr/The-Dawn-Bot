import asyncio
import json
import random
import names

from datetime import datetime, timezone
from typing import Literal, Tuple

from curl_cffi.requests import AsyncSession, Response
from utils.processing.handlers import require_auth_token
from core.exceptions.base import APIError, SessionRateLimited, ServerError, ProxyForbidden
from loader import config


class APIClient:
    EXTENSION_API_URL = "https://ext-api.dawninternet.com/api"
    DASHBOARD_API_URL = "https://ext-api.dawninternet.com/chromeapi/dawn"

    def __init__(self, proxy: str = None):
        self.proxy = proxy
        self.session = self._create_session()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

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
        # Унифицированная проверка {status:false} или {success:false}
        if isinstance(response_data, dict):
            if "status" in response_data and response_data.get("status") is False:
                raise APIError(f"API returned an error: {response_data}", response_data)
            if "success" in response_data and response_data.get("success") is False:
                raise APIError(f"API returned an error: {response_data}", response_data)

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
        return_full_response: bool = False,
        max_retries: int = 2,
        retry_delay: float = 3.0,
    ):
        url = (
            url
            if url
            else f"{self.EXTENSION_API_URL}{method}"
            if api_type == "EXTENSION"
            else f"{self.DASHBOARD_API_URL}{method}"
        )

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
                        raise ServerError("Failed to decode response, most likely server error")

                if return_full_response:
                    return response

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
            "user-agent": self.user_agent,
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "host": "ext-api.dawninternet.com",
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
            "user-agent": self.user_agent,
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "host": "ext-api.dawninternet.com",
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
            "user-agent": self.user_agent,
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "host": "ext-api.dawninternet.com",
        }

        params = {"app_v": "1.2.2"}

        response = await self.send_request(
            api_type="DASHBOARD",
            method="/v1/appid/getappid",
            request_type="GET",
            params=params,
            headers=headers,
        )
        return response["data"]["appid"]

    async def request_ip(self) -> str:
        # Попытка №1 — ipinfo, возвращаем полный response для статуса
        response = await self.send_request(
            request_type="GET",
            url="https://ipinfo.io/json",
            verify=False,
            return_full_response=True,
        )
        if response.status_code == 200:
            data = response.json()
            return data["ip"]

        # Попытка №2 — ipwho.is, тоже возвращаем объект response
        response2 = await self.send_request(
            request_type="GET",
            url="https://ipwho.is/",
            verify=False,
            return_full_response=True,
        )
        if response2.status_code == 200:
            data = response2.json()
            return data["ip"]

        raise ServerError(f"Failed to get IP after 2 attempts: {response2.status_code}")

    async def register(self, email: str, password: str, captcha_token: str, app_id: str) -> dict:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "cf-turnstile-response": captcha_token,
            "content-type": "application/json",
            "origin": "https://dashboard.dawninternet.com",
            "referer": "https://dashboard.dawninternet.com/",
            "user-agent": self.user_agent,
        }

        ip = await self.request_ip()

        json_data = {
            "first_name": names.get_first_name(),
            "last_name": names.get_last_name(),
            "email": email,
            "mobile": "",
            "country": random.choice(
                [
                    "AL",
                    "AD",
                    "AT",
                    "BY",
                    "BE",
                    "BA",
                    "BG",
                    "HR",
                    "CZ",
                    "DK",
                    "EE",
                    "FI",
                    "FR",
                    "DE",
                    "GR",
                    "HU",
                    "IS",
                    "IE",
                    "IT",
                    "LV",
                    "LI",
                    "LT",
                    "LU",
                    "MT",
                    "MD",
                    "MC",
                    "ME",
                    "NL",
                    "MK",
                    "NO",
                    "PL",
                    "PT",
                    "RO",
                    "RU",
                    "SM",
                    "RS",
                    "SK",
                    "SI",
                    "ES",
                    "SE",
                    "CH",
                    "UA",
                    "GB",
                    "VA",
                    "UA",
                ]
            ),
            "password": password,
            "referred_by": random.choice(config.referral_codes) if config.referral_codes else "",
            "is_marketing": False,
            "browser_name": "Chrome",
            "ip": ip,
        }

        return await self.send_request(
            url="https://validator.dawninternet.net/api/v3/dashboard/auth/signup",
            json_data=json_data,
            headers=headers,
        )

    @require_auth_token
    async def keepalive(self, email: str, app_id: str) -> dict | str:
        headers = {
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "authorization": f"Bearer {self.auth_token}",  # FIX: Bearer
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept-encoding": "gzip, deflate, br",
        }

        json_data = {
            "username": email,
            "extensionid": "fpdkjdnhkakefebpekbdhillbhonfjjp",
            "numberoftabs": 0,
            "_v": "1.2.2",
        }

        return await self.send_request(
            api_type="DASHBOARD",
            method="/v1/userreward/keepalive",
            json_data=json_data,
            verify=True,
            headers=headers,
            params={"appid": app_id},
        )

    @require_auth_token
    async def user_info(self, app_id: str) -> dict:
        # Совпадает с логикой второго кода
        headers = {
            "authorization": f"Bearer {self.auth_token}",  # FIX: Bearer
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept-encoding": "gzip, deflate, br",
        }

        response = await self.send_request(
            request_type="GET",
            api_type="EXTENSION",
            method="/atom/v1/userreferral/getpoint",
            headers=headers,
            params={"appid": app_id},
        )
        return response["data"]

    async def verify_registration(self, key: str) -> dict:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/json",
            "origin": "https://dashboard.dawninternet.com",
            "referer": "https://dashboard.dawninternet.com/",
            "user-agent": self.user_agent,
        }

        json_data = {
            "verification_key": key,
            "browser_name": None,
            "ip": None,
        }

        response = await self.send_request(
            url="https://validator.dawninternet.net/api/v3/dashboard/auth/verify",
            json_data=json_data,
            headers=headers,
        )
        return response["data"]

    async def verify_confirmation(self, key: str, captcha_token: str) -> dict:
        headers = {
            "accept": "*/*",
            "accept-language": "uk,en-US;q=0.9,en;q=0.8,ru;q=0.7",
            "content-type": "application/json",
            "origin": "https://verify.dawninternet.com",
            "user-agent": self.user_agent,
        }

        params = {"key": key}
        json_data = {"token": captcha_token}

        return await self.send_request(
            url="https://verify.dawninternet.com/chromeapi/dawn/v1/userverify/verifycheck",
            request_type="POST",
            json_data=json_data,
            params=params,
            headers=headers,
        )

    async def resend_verify_link(self, email: str, puzzle_id: str, answer: str, app_id: str) -> dict:
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,ru;q=0.8",
            "content-type": "application/json",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "user-agent": self.user_agent,
        }

        json_data = {
            "username": email,
            "puzzle_id": puzzle_id,
            "ans": answer,
        }

        return await self.send_request(
            url="https://ext-api.dawninternet.com/chromeapi/dawn/v1/user/resendverifylink/v2",
            json_data=json_data,
            params={"appid": app_id},
            headers=headers,
        )

    # =========================
    # Социальные задания (перенос логики из второго кода)
    # =========================

    @require_auth_token
    async def _get_points_and_maybe_award_social(self, app_id: str) -> dict:
        """
        Аналог get_points() из второго кода:
        - тянет /atom/v1/userreferral/getpoint
        - если twitter/discord/telegram < 1 — дергает обновление профиля для начисления
        Возвращает весь 'data' для дальнейшего использования.
        """
        headers = {
            "authorization": f"Bearer {self.auth_token}",
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept-encoding": "gzip, deflate, br",
        }

        resp = await self.send_request(
            request_type="GET",
            api_type="EXTENSION",
            method="/atom/v1/userreferral/getpoint",
            headers=headers,
            params={"appid": app_id},
        )

        data = resp.get("data", {}) if isinstance(resp, dict) else {}
        reward = data.get("rewardPoint", {}) if isinstance(data, dict) else {}

        # Если по какому-то социальному пункту < 1 — пробуем "доначислить" через /profile/update
        if reward.get("twitter_x_id_points", 0) < 1:
            await self._award_twitter_points(app_id)
        if reward.get("discordid_points", 0) < 1:
            await self._award_discord_points(app_id)
        if reward.get("telegramid_points", 0) < 1:
            await self._award_telegram_points(app_id)

        return data

    @require_auth_token
    async def _award_twitter_points(self, app_id: str) -> None:
        headers = {
            "authorization": f"Bearer {self.auth_token}",
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
        }
        payload = {"twitter_x_id": "twitter_x_id"}  # как во втором коде
        await self.send_request(
            api_type="DASHBOARD",
            method="/v1/profile/update",
            json_data=payload,
            params={"appid": app_id},
            headers=headers,
        )

    @require_auth_token
    async def _award_discord_points(self, app_id: str) -> None:
        headers = {
            "authorization": f"Bearer {self.auth_token}",
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
        }
        payload = {"discordid": "discordid"}  # как во втором коде
        await self.send_request(
            api_type="DASHBOARD",
            method="/v1/profile/update",
            json_data=payload,
            params={"appid": app_id},
            headers=headers,
        )

    @require_auth_token
    async def _award_telegram_points(self, app_id: str) -> None:
        headers = {
            "authorization": f"Bearer {self.auth_token}",
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
        }
        payload = {"telegramid": "telegramid"}  # как во втором коде
        await self.send_request(
            api_type="DASHBOARD",
            method="/v1/profile/update",
            json_data=payload,
            params={"appid": app_id},
            headers=headers,
        )

    @require_auth_token
    async def complete_tasks(self, app_id: str, delay: int = 1) -> dict:
        """
        ЗАМЕНА старой complete_tasks():
        - тянем текущие points
        - при необходимости «доначисляем» через profile/update
        - вновь возвращаем актуальные данные points
        """
        data_before = await self._get_points_and_maybe_award_social(app_id)
        await asyncio.sleep(delay)
        data_after = await self._get_points_and_maybe_award_social(app_id)
        return {
            "before": data_before,
            "after": data_after,
        }

    # =========================
    # Прочее
    # =========================

    async def verify_session(self, app_id: str) -> Tuple[bool, str]:
        """
        FIX: раньше вызывал user_info() без app_id — из-за этого падал.
        """
        try:
            await self.user_info(app_id)
            return True, "Session is valid"
        except ServerError:
            # серверные 5xx — сессия вероятно валидна, но упали на стороне API
            return True, "Server error"
        except APIError as error:
            return False, str(error)

    async def login(self, email: str, password: str, puzzle_id: str, answer: str, app_id: str) -> str:
        headers = {
            "user-agent": self.user_agent,
            "content-type": "application/json",
            "accept": "*/*",
            "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "accept-language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
            "accept-encoding": "gzip, deflate, br",
        }

        current_time = datetime.now(timezone.utc)
        formatted_datetime_str = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        json_data = {
            "username": email,
            "password": password,
            "logindata": {
                "_v": {"version": "1.2.2"},
                "datetime": formatted_datetime_str,
            },
            "puzzle_id": puzzle_id,
            "ans": answer,
            "appid": app_id,
        }

        response = await self.send_request(
            api_type="DASHBOARD",
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
