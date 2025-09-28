import asyncio
import pytz

from datetime import datetime, timedelta
from typing import Optional, Literal
from better_proxy import Proxy
from loguru import logger

from loader import config, file_operations, proxy_manager
from models import Account, OperationResult

from core.api.dawn import DawnExtensionAPI
from utils import EmailValidator, LinkExtractor, operation_failed, operation_success, validate_error, handle_sleep
from database import Accounts
from core.exceptions.base import APIError, APIErrorType, EmailValidationFailed


class Bot:
    def __init__(self, account_data: Account):
        self.account_data = account_data
        self._db_account: Optional[Accounts] = None

    @staticmethod
    async def handle_invalid_account(email: str, password: str, reason: Literal["unverified", "banned", "unregistered", "unlogged", "invalid_proxy"], log: bool = True, invalid_proxy: str = None) -> None:

        if reason == "unlogged":
            if log:
                logger.error(f"Account: {email} | Account not logged in, run <<Register & Login accounts>> module | Removed from list")
            await file_operations.export_invalid_account(email, password, "unlogged")

        elif reason == "invalid_proxy":
            await file_operations.export_invalid_proxy_account(email, password, invalid_proxy)

        for account in config.accounts_to_farm:
            if account.email == email:
                config.accounts_to_farm.remove(account)

    @staticmethod
    async def _set_next_sleep_until(db_account_value: Accounts) -> None:
        if db_account_value:
            duration = timedelta(seconds=config.application_settings.ping_interval)
            utc_duration = datetime.now(pytz.UTC) + duration
            await db_account_value.set_sleep_until(utc_duration)

    @staticmethod
    async def _prepare_proxy() -> str:
        proxy = await proxy_manager.get_proxy()
        return proxy.as_url if isinstance(proxy, Proxy) else proxy

    async def _validate_email(self, proxy: str = None) -> dict:
        proxy = Proxy.from_str(proxy) if proxy else None

        if config.redirect_settings.enabled:
            result = await EmailValidator(
                config.redirect_settings.imap_server,
                config.redirect_settings.email,
                config.redirect_settings.password
            ).validate(None if config.redirect_settings.use_proxy is False else proxy)
        else:
            result = await EmailValidator(
                self.account_data.imap_server,
                self.account_data.email,
                self.account_data.email_password
            ).validate(None if config.imap_settings.use_proxy_for_imap is False else proxy)

        return result

    async def _is_email_valid(self, proxy: str = None) -> bool:
        result = await self._validate_email(proxy)
        if not result["status"]:
            if "validation failed" in result["data"]:
                raise EmailValidationFailed(f"Email validation failed: {result['data']}")

            logger.error(f"Account: {self.account_data.email} | Email is invalid: {result['data']}")
            return False
        return True

    async def _extract_link(self, proxy: str = None) -> dict:
        if config.redirect_settings.enabled:
            confirm_url = await LinkExtractor(
                imap_server=config.redirect_settings.imap_server,
                email=config.redirect_settings.email,
                password=config.redirect_settings.password,
                redirect_email=self.account_data.email
            ).extract_link(None if config.imap_settings.use_proxy_for_imap is False else proxy)
        else:
            confirm_url = await LinkExtractor(
                imap_server=self.account_data.imap_server,
                email=self.account_data.email,
                password=self.account_data.email_password,
            ).extract_link(None if config.imap_settings.use_proxy_for_imap is False else proxy)

        return confirm_url

    async def _update_account_proxy(self, account_data: Accounts, attempt: int | str) -> None:
        max_attempts = config.attempts_and_delay_settings.max_login_attempts \
            if config.module == "login" \
            else config.attempts_and_delay_settings.max_tasks_attempts \
            if config.module == "complete_tasks" \
            else config.attempts_and_delay_settings.max_stats_attempts \
            if config.module == "export_stats" \
            else config.attempts_and_delay_settings.max_farm_attempts

        if config.application_settings.disable_auto_proxy_change is False:
            proxy_changed_log = (
                f"Account: {self.account_data.email} | Proxy changed | "
                f"Retrying in {config.attempts_and_delay_settings.error_delay}s.. | "
                f"Attempt: {attempt + 1}/{max_attempts}.."
            )

            if not account_data:
                logger.info(proxy_changed_log)
                await asyncio.sleep(config.attempts_and_delay_settings.error_delay)
                return

            if account_data.active_account_proxy:
                await proxy_manager.release_proxy(account_data.active_account_proxy)

            proxy = await self._prepare_proxy()
            await account_data.update_account_proxy(proxy)

        else:
            proxy_changed_log = (
                f"Account: {self.account_data.email} | Proxy change disabled | "
                f"Retrying in {config.attempts_and_delay_settings.error_delay}s.. | "
                f"Attempt: {attempt + 1}/{max_attempts}.."
            )

        logger.info(proxy_changed_log)
        await asyncio.sleep(config.attempts_and_delay_settings.error_delay)

    async def _get_confirmation_code(self, proxy: str = None) -> Optional[str]:
        confirm_url = await self._extract_link(proxy)
        if not confirm_url["status"]:
            return None

        return confirm_url["data"]

    async def process_login(self, check_if_account_logged_in: bool = True) -> OperationResult | None:
        max_attempts = config.attempts_and_delay_settings.max_login_attempts

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if check_if_account_logged_in:
                    if config.application_settings.skip_logged_accounts and db_account_value and all([
                        db_account_value.extension_token,
                        db_account_value.privy_auth_token,
                        db_account_value.session_token,
                    ]):
                        logger.success(f"Account: {self.account_data.email} | Account already logged in, skipped")
                        return operation_failed(self.account_data.email, self.account_data.email_password)

                proxy = await self._prepare_proxy() if not db_account_value or not db_account_value.active_account_proxy else db_account_value.active_account_proxy
                api = DawnExtensionAPI(proxy=proxy)

                if not await self._is_email_valid(proxy=proxy):
                    return operation_failed(self.account_data.email, self.account_data.email_password)

                logger.info(f"Account: {self.account_data.email} | Initiating authentication..")
                await api.init_auth(self.account_data.email)
                logger.success(f"Account: {self.account_data.email} | Authentication initiated, confirmation code sent to email")

                code = await self._get_confirmation_code()
                if not code:
                    return operation_failed(self.account_data.email, self.account_data.email_password)

                logger.info(f"Account: {self.account_data.email} | Confirming authentication..")
                auth_data = await api.authenticate(self.account_data.email, code)

                session_token = auth_data.get('token')
                privy_auth_token = auth_data.get('privy_access_token')
                refresh_token = auth_data.get('refresh_token')

                logger.info(f"Account: {self.account_data.email} | Authenticating to extension..")
                api.session_token = session_token
                ext_auth_data = await api.extension_auth()

                extension_token = ext_auth_data.get('session_token')
                logger.success(f"Account: {self.account_data.email} | Authenticated to extension")

                if not all([session_token, privy_auth_token, extension_token, refresh_token]):
                    logger.error(f"Account: {self.account_data.email} | Failed to retrieve all tokens")
                    return operation_failed(self.account_data.email, self.account_data.email_password)

                user_id = ext_auth_data["user"]["id"]
                await Accounts.create_or_update_account(
                    email=self.account_data.email,
                    email_password=self.account_data.email_password,
                    user_id=user_id,
                    session_token=session_token,
                    privy_auth_token=privy_auth_token,
                    extension_token=extension_token,
                    refresh_token=refresh_token,
                    proxy=proxy
                )

                logger.success(f"Account: {self.account_data.email} | Account logged in | Session saved to database")
                return operation_success(self.account_data.email, self.account_data.email_password)

            except APIError as error:
                if error.error_type == APIErrorType.INVALID_CREDENTIALS:
                    logger.error(f"Account: {self.account_data.email} | Invalid confirmation code | Retrying in {config.attempts_and_delay_settings.error_delay}s | Attempt: {attempt + 1}/{max_attempts}")
                    await asyncio.sleep(config.attempts_and_delay_settings.error_delay)
                    continue

                logger.error(f"Account: {self.account_data.email} | Error occurred during login (APIError): {error} | Skipped permanently")
                return operation_failed(self.account_data.email, self.account_data.email_password)

            except Exception as error:
                is_last_attempt = attempt == max_attempts - 1
                if is_last_attempt:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to login | Last error: {error} | Skipped permanently")
                    return operation_failed(self.account_data.email, self.account_data.email_password)

                error = validate_error(error)
                logger.error(f"Account: {self.account_data.email} | Error occurred during login (Generic Exception): {error}")
                await self._update_account_proxy(db_account_value, attempt)

            finally:
                if api:
                    await api.close_session()

    async def process_export_stats(self) -> OperationResult | None:
        max_attempts = config.attempts_and_delay_settings.max_stats_attempts

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if not db_account_value or not all([
                    db_account_value.extension_token,
                    db_account_value.privy_auth_token,
                    db_account_value.session_token,
                    db_account_value.refresh_token,
                ]):
                    await self.handle_invalid_account(self.account_data.email, self.account_data.email_password, "unlogged")
                    return None

                api = DawnExtensionAPI(
                    privy_auth_token=db_account_value.privy_auth_token,
                    extension_token=db_account_value.extension_token,
                    session_token=db_account_value.session_token,
                    proxy=db_account_value.active_account_proxy
                )

                logger.info(f"Account: {self.account_data.email} | Retrieving account stats..")
                user_info = await api.request_user_info(user_id=db_account_value.user_id)

                referral_stats = await api.request_referral_stats()
                logger.success(f"Account: {self.account_data.email} | Account stats retrieved")

                stats = {
                    "user_id": db_account_value.user_id,
                    "user_info": user_info,
                    "referral_stats": referral_stats
                }
                return operation_success(self.account_data.email, self.account_data.email_password, data=stats)

            except APIError as error:
                is_last_attempt = attempt == max_attempts - 1
                if is_last_attempt:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to retrieve stats | Last error: {error} | Skipped permanently")
                    return operation_failed(self.account_data.email, self.account_data.email_password, data={})

                if error.error_type in (APIErrorType.INVALID_TOKEN, APIErrorType.PING_INTERVAL_VIOLATION, APIErrorType.CUSTOM_DOMAIN_VIOLATION):
                    logger.warning(f"Account: {self.account_data.email} | Bug on DAWN side, cannot complete request, relogin account..")
                    operation_result = await self.process_login(check_if_account_logged_in=False)
                    if operation_result and operation_result["status"] is True:
                        continue

                    return operation_failed(self.account_data.email, self.account_data.email_password, data={})

                logger.error(f"Account: {self.account_data.email} | Error occurred during stats retrieval (APIError): {error} | Skipped permanently")
                return operation_failed(self.account_data.email, self.account_data.email_password, data={})

            except Exception as error:
                is_last_attempt = attempt == max_attempts - 1
                if is_last_attempt:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to retrieve stats | Last error: {error} | Skipped permanently")
                    return operation_failed(self.account_data.email, self.account_data.email_password, data={})

                error = validate_error(error)
                logger.error(f"Account: {self.account_data.email} | Error occurred during sending ping (Generic Exception): {error}")
                await self._update_account_proxy(db_account_value, attempt)

            finally:
                if api:
                    await api.close_session()

    async def process_farm(self) -> None:
        max_attempts = config.attempts_and_delay_settings.max_farm_attempts
        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if not db_account_value or not all([
                    db_account_value.extension_token,
                    db_account_value.privy_auth_token,
                    db_account_value.session_token,
                    db_account_value.refresh_token,
                ]):
                    await self.handle_invalid_account(self.account_data.email, self.account_data.email_password, "unlogged")
                    return None

                api = DawnExtensionAPI(
                    privy_auth_token=db_account_value.privy_auth_token,
                    extension_token=db_account_value.extension_token,
                    session_token=db_account_value.session_token,
                    proxy=db_account_value.active_account_proxy
                )

                if db_account_value.sleep_until:
                    sleep_duration = await handle_sleep(db_account_value.sleep_until)
                    if sleep_duration:
                        return

                logger.info(f"Account: {self.account_data.email} | Sending ping..")
                await api.extension_ping(user_id=db_account_value.user_id)
                logger.success(f"Account: {self.account_data.email} | Ping sent")
                await self._set_next_sleep_until(db_account_value)

            except APIError as error:
                logger.error(f"Account: {self.account_data.email} | Error occurred during sending ping (APIError): {error} | Skipped until next cycle")
                await self._set_next_sleep_until(db_account_value)
                return None

            except Exception as error:
                if "Proxy Authentication Required" in str(error) and config.application_settings.disable_auto_proxy_change:
                    logger.error(f"Account: {self.account_data.email} | Proxy authentication failed | Account deleted from farming")
                    await self.handle_invalid_account(self.account_data.email, self.account_data.email_password, "invalid_proxy", invalid_proxy=api.proxy)
                    return None

                is_last_attempt = attempt == max_attempts - 1
                if is_last_attempt:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to send ping | Last error: {error} | Skipped until next cycle")
                    await self._set_next_sleep_until(db_account_value)
                    return None

                error = validate_error(error)
                logger.error(f"Account: {self.account_data.email} | Error occurred during sending ping (Generic Exception): {error}")
                await self._update_account_proxy(db_account_value, attempt)

            finally:
                if api:
                    await api.close_session()
