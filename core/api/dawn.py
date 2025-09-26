import asyncio
import json
import uuid

from datetime import datetime, timezone
from typing import Literal

from curl_cffi.requests import AsyncSession, Response
from utils.processing.handlers import require_extension_token, require_session_token, require_privy_auth_token
from core.exceptions.base import APIError, SessionRateLimited, ServerError, ProxyForbidden



class APIClient:
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
                if response_data.get("status") is False:
                    raise APIError(
                        f"API returned an error: {response_data}", response_data
                    )

            elif "success" in str(response_data):
                if response_data.get("success") is False:
                    raise APIError(
                        f"API returned an error: {response_data}", response_data
                    )

            elif "error" in str(response_data):
                raise APIError(
                    f"API returned an error: {response_data}", response_data
                )

            elif "message" in str(response_data):
                if response_data.get("message") in ["Invalid token", "Custom domain user limit exceeded"]:
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
        url: str,
        request_type: Literal["POST", "GET", "OPTIONS"] = "POST",
        json_data: dict = None,
        params: dict = None,
        headers: dict = None,
        cookies: dict = None,
        verify: bool = True,
        return_full_response: bool = False,
        max_retries: int = 2,
        retry_delay: float = 3.0,
    ):
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
                        raise APIError(f"Access forbidden - {response.status_code} | Details: {response.text[0:100]}", response.json())

                    if response.status_code in (500, 502, 503, 504):
                        raise ServerError(f"Server error - {response.status_code}")

                    try:
                        response_json = response.json()
                        await self._verify_response(response_json)
                        return response_json
                    except json.JSONDecodeError:
                        raise ServerError(f"Failed to decode response, most likely server error")

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
    def __init__(
            self,
            privy_auth_token: str = None,
            session_token: str = None,
            extension_token: str = None,
            proxy: str = None
    ):
        super().__init__(proxy)
        self.privy_auth_token = privy_auth_token
        self.session_token = session_token
        self.extension_token = extension_token

    async def init_auth(self, email: str) -> dict:
        headers = {
            'Host': 'auth.privy.io',
            'Connection': 'keep-alive',
            'privy-client': 'react-auth:2.24.0',
            'privy-ui': 't',
            'privy-app-id': 'cmfb724md0057la0bs4tg0vf1',
            'User-Agent': self.user_agent,
            'accept': 'application/json',
            'privy-ca-id': str(uuid.uuid4()),
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
        }

        json_data = {
            'email': email,
        }

        return await self.send_request(
            url='https://auth.privy.io/api/v1/passwordless/init',
            request_type='POST',
            json_data=json_data,
            headers=headers,
        )

    async def authenticate(self, email: str, code: str) -> dict:
        headers = {
            'Host': 'auth.privy.io',
            'Connection': 'keep-alive',
            'privy-client': 'react-auth:2.24.0',
            'privy-app-id': 'cmfb724md0057la0bs4tg0vf1',
            'User-Agent': self.user_agent,
            'accept': 'application/json',
            'privy-ca-id': str(uuid.uuid4()),
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
        }

        json_data = {
            'email': email,
            'code': code,
            'mode': 'login-or-sign-up',
        }

        return await self.send_request(
            url='https://auth.privy.io/api/v1/passwordless/authenticate',
            request_type='POST',
            json_data=json_data,
            headers=headers,
        )


    @require_session_token
    async def extension_auth(self) -> dict:
        headers = {
            'Host': 'api.dawninternet.com',
            'Connection': 'keep-alive',
            'x-privy-token': self.session_token,
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        params = {
            'jwt': 'true',
            'role': 'extension',
        }

        response = await self.send_request(
            url='https://api.dawninternet.com/auth',
            request_type='GET',
            headers=headers,
            params=params,
        )

        return response


    @require_extension_token
    async def request_user_info(self, user_id: str) -> dict:
        headers = {
            'Host': 'api.dawninternet.com',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Authorization': f'Bearer {self.extension_token}',
            'Accept': '*/*',
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Content-Type': 'application/json',
        }

        params = {
            'user_id': user_id,
        }

        return await self.send_request(
            url='https://api.dawninternet.com/point',
            request_type='GET',
            headers=headers,
            params=params,
        )


    @require_extension_token
    async def extension_ping(self, user_id: str, extension_id: str = "fpdkjdnhkakefebpekbdhillbhonfjjp") -> dict:
        headers = {
            'Host': 'api.dawninternet.com',
            'Connection': 'keep-alive',
            'User-Agent': self.user_agent,
            'Authorization': f'Bearer {self.extension_token}',
            'Accept': '*/*',
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Content-Type': 'application/json',
        }

        params = {
            'role': 'extension',
        }

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        json_data = {
            'user_id': user_id,
            'extension_id': extension_id,
            'timestamp': timestamp,
        }

        response = await self.send_request(
            url='https://api.dawninternet.com/ping',
            request_type='POST',
            headers=headers,
            params=params,
            json_data=json_data,
        )

        if response["message"] != "pong":
            raise APIError(f"Ping failed: {response}")

        return response


    @require_session_token
    async def append_referral_code(self, referral_code: str) -> dict:
        headers = {
            'Host': 'api.dawninternet.com',
            'Connection': 'keep-alive',
            'sec-ch-ua-platform': '"Windows"',
            'x-privy-token': self.session_token,
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Content-Type': 'application/json',
        }

        json_data = {
            'referralCode': referral_code,
        }

        return await self.send_request(
            url='https://api.dawninternet.com/referral/use',
            request_type='POST',
            headers=headers,
            json_data=json_data,
        )


    @require_session_token
    async def get_referral_code(self) -> dict:
        headers = {
            'Host': 'api.dawninternet.com',
            'Connection': 'keep-alive',
            'x-privy-token': self.session_token,
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        return await self.send_request(
            url='https://api.dawninternet.com/referral/my-code',
            request_type='GET',
            headers=headers,
        )


    @require_session_token
    async def request_referral_stats(self) -> dict:
        headers = {
            'Host': 'api.dawninternet.com',
            'Connection': 'keep-alive',
            'x-privy-token': self.session_token,
            'User-Agent': self.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        return await self.send_request(
            url='https://api.dawninternet.com/referral/stats',
            request_type='GET',
            headers=headers,
        )


    @require_privy_auth_token
    async def refresh_privy_session(self, refresh_token: str) -> dict:
        headers = {
            'Host': 'auth.privy.io',
            'Connection': 'keep-alive',
            'authorization': f'Bearer {self.privy_auth_token}',
            'privy-client': 'react-auth:2.24.0',
            'privy-app-id': 'cmfb724md0057la0bs4tg0vf1',
            'User-Agent': self.user_agent,
            'accept': 'application/json',
            'privy-ca-id': str(uuid.uuid4()),
            'Origin': 'chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
        }

        json_data = {
            'refresh_token': refresh_token,
        }

        return await self.send_request(
            url='https://auth.privy.io/api/v1/sessions',
            request_type='POST',
            json_data=json_data,
            headers=headers,
        )
