import asyncio
import pytz

from datetime import datetime, timedelta
from typing import Tuple, Any, Optional, Literal, Dict
from better_proxy import Proxy
from loguru import logger

from loader import config, file_operations, captcha_solver, proxy_manager
from models import Account, OperationResult, StatisticData

from core.api.dawn import DawnExtensionAPI
from utils import EmailValidator, LinkExtractor, operation_failed, operation_success, operation_export_stats_success, operation_export_stats_failed, validate_error, handle_sleep
from database import Accounts
from core.exceptions.base import APIError, SessionRateLimited, CaptchaSolvingFailed, APIErrorType, ProxyForbidden, EmailValidationFailed


class Bot:
    def __init__(self, account_data: Account):
        self.account_data = account_data

    @staticmethod
    async def handle_invalid_account(email: str, password: str, reason: Literal["unverified", "banned", "unregistered", "unlogged", "invalid_proxy"], log: bool = True, invalid_proxy: str = None) -> None:
        if reason == "unverified":
            if log:
                logger.error(f"Account: {email} | Email not verified, run <<Register & Verify accounts>> module | Removed from list")
            await file_operations.export_invalid_account(email, password, "unverified")

        elif reason == "banned":
            if log:
                logger.error(f"Account: {email} | Account is banned | Removed from list")
            await file_operations.export_invalid_account(email, password, "banned")

        elif reason == "unregistered":
            if log:
                logger.error(f"Account: {email} | Email not registered, run <<Register & Verify accounts>> module | Removed from list")
            await file_operations.export_invalid_account(email, password, "unregistered")

        elif reason == "unlogged":
            if log:
                logger.error(f"Account: {email} | Account not logged in, run <<Login accounts>> module | Removed from list")
            await file_operations.export_invalid_account(email, password, "unlogged")

        elif reason == "invalid_proxy":
            await file_operations.export_invalid_proxy_account(email, password, invalid_proxy)

        for account in config.accounts_to_farm:
            if account.email == email:
                config.accounts_to_farm.remove(account)

    async def handle_api_error(
            self,
            error: APIError,
            attempt: int,
            max_attempts: int,
            context: Literal["registration", "verify", "login", "tasks", "stats", "keepalive"],
            db_account_value: Optional[Accounts],
    ) -> None | OperationResult | StatisticData:

        is_last_attempt = attempt == max_attempts - 1
        email = self.account_data.email
        password = self.account_data.password
        error_delay = config.attempts_and_delay_settings.error_delay
        attempts_reached_phrase = "register" if context == "registration" else "verify" if context == "verify" else "login" if context == "login" else "complete tasks" if context == "tasks" else "export stats" if context == "stats" else "send keepalive"

        def retry_log(msg: str):
            logger.warning(f"Account: {email} | {msg} | Attempt: {attempt + 1}/{max_attempts} | Retrying in {error_delay} seconds")

        def final_fail():
            logger.error(f"Account: {email} | Max attempts reached, unable to {attempts_reached_phrase}")
            if context == "stats":
                return operation_export_stats_failed()
            return operation_failed(email, password)

        match error.error_type:
            case APIErrorType.INCORRECT_CAPTCHA:
                retry_log("Captcha answer incorrect")
                if not is_last_attempt:
                    await asyncio.sleep(error_delay)
                    return None

            case APIErrorType.CAPTCHA_EXPIRED:
                retry_log("Captcha expired")
                if not is_last_attempt:
                    await asyncio.sleep(error_delay)
                    return None

            case APIErrorType.INVALID_CAPTCHA_TOKEN:
                retry_log("Invalid captcha token")
                if not is_last_attempt:
                    await asyncio.sleep(error_delay)
                    return None

            case APIErrorType.EMAIL_EXISTS:
                logger.warning(f"Account: {email} | Email already exists")
                return operation_success(email, password)

            case APIErrorType.UNVERIFIED_EMAIL:
                await self.handle_invalid_account(email, password, "unverified")
                return operation_failed(email, password)

            case APIErrorType.BANNED:
                await self.handle_invalid_account(email, password, "banned")
                return operation_failed(email, password)

            case APIErrorType.UNREGISTERED_EMAIL:
                await self.handle_invalid_account(email, password, "unregistered")
                return operation_failed(email, password)

            case APIErrorType.SESSION_EXPIRED:
                await self.handle_invalid_account(email, password, "unlogged")
                if db_account_value:
                    await db_account_value.delete()

                # logger.warning(f"Account: {email} | Session expired, need to re-login | Exported to <<unlogged_accounts.txt>>")
                # return operation_failed(email, password)

                logger.warning(f"Account: {email} | Session expired, logging in..")
                await self.process_login(check_if_account_logged_in=False)
                return None

            case _:
                if "Something went wrong" in error.error_message:
                    logger.warning(f"Account: {email} | Most likely email domain <{email.split('@')[1]}> is banned")
                    if context in {"tasks", "stats"}:
                        await self.handle_invalid_account(email, password, "banned", log=False)
                        return operation_failed(email, password) if context != "stats" else operation_export_stats_failed()
                else:
                    logger.error(f"Account: {email} | Error occurred during {attempts_reached_phrase} (APIError): {error}")

        return final_fail()

    async def handle_generic_exception(
            self,
            error: Exception,
            attempt: int,
            max_attempts: int,
            context: Literal["registration", "verify", "login", "tasks", "stats", "keepalive"],
            db_account_value: Optional[Accounts],
    ) -> None | StatisticData | OperationResult:
        is_last_attempt = attempt == max_attempts - 1
        email = self.account_data.email
        password = self.account_data.password
        error_phrase = "registering" if context == "registration" else "verifying" if context == "verify" else "logging in" if context == "login" else "completing tasks" if context == "tasks" else "exporting stats" if context == "stats" else "sending keepalive"
        attempts_reached_phrase = "register" if context == "registration" else "verify" if context == "verify" else "login" if context == "login" else "complete tasks" if context == "tasks" else "export stats" if context == "stats" else "send keepalive"
        error_text = validate_error(error)

        logger.error(f"Account: {email} | Error occurred while {error_phrase}: {error_text}")

        if not is_last_attempt:
            await self._update_account_proxy(db_account_value, attempt)
            return None
        else:
            logger.error(f"Account: {email} | Max attempts reached, unable to {attempts_reached_phrase}")
            if context == "stats":
                return operation_export_stats_failed()
            return operation_failed(email, password)

    @staticmethod
    def get_sleep_until(blocked: bool = False) -> datetime:
        duration = timedelta(seconds=config.keepalive_interval)
        return datetime.now(pytz.UTC) + duration

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
                self.account_data.password
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


    async def _extract_link(self) -> dict:
        if config.redirect_settings.enabled:
            confirm_url = await LinkExtractor(
                imap_server=config.redirect_settings.imap_server,
                email=config.redirect_settings.email,
                password=config.redirect_settings.password,
                redirect_email=self.account_data.email
            ).extract_link(None if config.redirect_settings.use_proxy is False else self.account_data.proxy)
        else:
            confirm_url = await LinkExtractor(
                imap_server=self.account_data.imap_server,
                email=self.account_data.email,
                password=self.account_data.password,
            ).extract_link(None if config.imap_settings.use_proxy_for_imap is False else self.account_data.proxy)

        return confirm_url

    async def _update_account_proxy(self, account_data: Accounts, attempt: int | str) -> None:
        max_attempts = config.attempts_and_delay_settings.max_register_attempts if config.module == "registration" else config.attempts_and_delay_settings.max_login_attempts if config.module == "login" else config.attempts_and_delay_settings.max_tasks_attempts if config.module == "complete_tasks" else config.attempts_and_delay_settings.max_stats_attempts if config.module == "export_stats" else config.attempts_and_delay_settings.max_attempts_to_verify_email

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

            proxy = await proxy_manager.get_proxy()
            await account_data.update_account_proxy(proxy.as_url if isinstance(proxy, Proxy) else proxy)

        else:
            proxy_changed_log = (
                f"Account: {self.account_data.email} | Proxy change disabled | "
                f"Retrying in {config.attempts_and_delay_settings.error_delay}s.. | "
                f"Attempt: {attempt + 1}/{max_attempts}.."
            )

        logger.info(proxy_changed_log)
        await asyncio.sleep(config.attempts_and_delay_settings.error_delay)

    async def get_captcha_data(
            self,
            api: DawnExtensionAPI,
            captcha_type: Literal["image", "turnistale"],
            max_attempts: int = 5,
            app_id: Optional[str] = None,
    ) -> Tuple[str, Any, Optional[Any]] | str:
        async def handle_image_captcha() -> Tuple[str, str, Optional[Any]]:
            logger.info(f"Account: {self.account_data.email} | Solving image captcha...")
            puzzle_id = await api.get_puzzle_id(app_id=app_id)
            image = await api.get_puzzle_image(puzzle_id, app_id=app_id)

            logger.info(f"Account: {self.account_data.email} | Got puzzle image, solving...")
            answer, solved, *rest = await captcha_solver.solve_image(image)

            if solved and len(answer) == 6:
                logger.success(f"Account: {self.account_data.email} | Puzzle solved: {answer}")
                return puzzle_id, answer, rest[0] if rest else None

            if len(answer) != 6 and rest:
                await captcha_solver.report_bad(rest[0])

            raise ValueError(answer)

        async def handle_turnistale_captcha() -> tuple[Any, Any | None]:
            logger.info(f"Account: {self.account_data.email} | Solving Cloudflare challenge...")
            answer, solved, *rest = await captcha_solver.solve_turnistale()

            if solved:
                logger.success(f"Account: {self.account_data.email} | Cloudflare challenge solved")
                return answer, rest[0] if rest else None

            raise ValueError(f"Failed to solve Cloudflare challenge: {answer}")

        handler = handle_image_captcha if captcha_type == "image" else handle_turnistale_captcha
        for attempt in range(max_attempts):
            try:
                return await handler()
            except (SessionRateLimited, ProxyForbidden):
                raise
            except Exception as e:
                logger.error(
                    f"Account: {self.account_data.email} | Error occurred while solving captcha ({captcha_type}): {str(e)} | Retrying..."
                )
                if attempt == max_attempts - 1:
                    raise CaptchaSolvingFailed(f"Failed to solve captcha after {max_attempts} attempts")

    async def process_get_app_id(self, api: DawnExtensionAPI) -> Optional[str]:
        max_attempts = config.attempts_and_delay_settings.max_attempts_to_receive_app_id
        error_delay = config.attempts_and_delay_settings.error_delay

        for attempt in range(max_attempts):
            is_last_attempt = attempt == max_attempts - 1

            try:
                logger.info(f"Account: {self.account_data.email} | Getting app ID...")
                app_id = await api.get_app_id()

                logger.success(f"Account: {self.account_data.email} | Received app ID: {app_id}")
                return app_id

            except APIError as error:
                logger.error(f"Account: {self.account_data.email} | Failed to get app ID (APIError): {error}")
                return None

            except Exception as error:
                if not is_last_attempt:
                    proxy = await proxy_manager.get_proxy()
                    api = DawnExtensionAPI(proxy=proxy.as_url if isinstance(proxy, Proxy) else proxy)

                    logger.error(f"Account: {self.account_data.email} | Failed to get app ID: {error} | Proxy changed | Retrying in {error_delay} seconds...")
                    await asyncio.sleep(error_delay)
                else:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to get app ID")
                    return None

    async def _get_confirmation_key(self, api: DawnExtensionAPI) -> Optional[str]:
        confirm_url = await self._extract_link()
        if not confirm_url["status"]:
            return None

        try:
            return confirm_url["data"].split("key=")[1]
        except IndexError:
            response = await api.clear_request(confirm_url["data"])
            return response.url.split("key=")[1]


    @staticmethod
    async def _verify_registration(api: DawnExtensionAPI, key: str) -> dict:
        # captcha_token, task_id = await self.get_captcha_data(
        #     api=api,
        #     captcha_type="turnistale",
        #     app_id=app_id,
        # )

        return await api.verify_registration(key)


    async def _register_account(self, api: DawnExtensionAPI, app_id: str) -> dict:
        captcha_token, task_id = await self.get_captcha_data(
            api=api,
            captcha_type="turnistale",
            app_id=app_id,
        )

        return await api.register(
            email=self.account_data.email,
            password=self.account_data.password,
            app_id=app_id,
            captcha_token=captcha_token,
        )

    async def _login_account(self, api: DawnExtensionAPI, app_id: str) -> str:
        puzzle_id, answer, task_id = await self.get_captcha_data(
            api=api,
            captcha_type="image",
            app_id=app_id,
        )

        return await api.login(
            email=self.account_data.email,
            password=self.account_data.password,
            app_id=app_id,
            puzzle_id=puzzle_id,
            answer=answer,
        )

    @staticmethod
    async def _prepare_account_proxy_and_app_id(db_account_value: Accounts) -> Tuple[str | Proxy, Optional[str]]:
        if db_account_value and (db_account_value.active_account_proxy, db_account_value.app_id):
            proxy = db_account_value.active_account_proxy
            if not proxy:
                proxy = await proxy_manager.get_proxy()
                await db_account_value.update_account(proxy=proxy.as_url if isinstance(proxy, Proxy) else proxy)
            app_id = db_account_value.app_id
        else:
            proxy = await proxy_manager.get_proxy()
            app_id = None

        return proxy.as_url if isinstance(proxy, Proxy) else proxy, app_id

    async def process_registration(self) -> OperationResult:
        max_attempts = config.attempts_and_delay_settings.max_register_attempts

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if config.application_settings.skip_logged_accounts and db_account_value and db_account_value.auth_token:
                    logger.warning(f"Account: {self.account_data.email} | Account already logged in, skipped")
                    return operation_failed(self.account_data.email, self.account_data.password)

                proxy, app_id = await self._prepare_account_proxy_and_app_id(db_account_value)
                if not await self._is_email_valid(proxy):
                    return operation_failed(self.account_data.email, self.account_data.password)

                api = DawnExtensionAPI(proxy=proxy if isinstance(proxy, str) else proxy.as_url)
                app_id = await self.process_get_app_id(api=api) if not app_id else app_id

                if not app_id:
                    return operation_failed(self.account_data.email, self.account_data.password)

                if not db_account_value:
                    db_account_value = await Accounts.create_or_update_account(email=self.account_data.email, password=self.account_data.password, app_id=app_id, proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                await self._register_account(api=api, app_id=app_id)
                logger.info(f"Account: {self.account_data.email} | Registered, waiting for email...")

                key = await self._get_confirmation_key(api=api)
                if not key:
                    logger.error(f"Account: {self.account_data.email} | Confirmation link not found | Exported to <<unverified_accounts.txt>>")
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified", log=False)
                    return OperationResult(
                        identifier=self.account_data.email,
                        data=self.account_data.password,
                        status=False,
                    )

                logger.success(f"Account: {self.account_data.email} | Link found, confirming registration...")
                await self._verify_registration(api=api, key=key)

                logger.success(f"Account: {self.account_data.email} | Registration verified and completed")
                return operation_success(self.account_data.email, self.account_data.password)

            except APIError as error:
                result = await self.handle_api_error(error, attempt, max_attempts, "registration", db_account_value)
                if result is not None:
                    return result

            except EmailValidationFailed as error:
                if attempt == max_attempts - 1:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to register")
                    return operation_failed(self.account_data.email, self.account_data.password)

                logger.error(f"Account: {self.account_data.email} | {error}")
                await self._update_account_proxy(db_account_value, attempt)

            except Exception as error:
                result = await self.handle_generic_exception(error, attempt, max_attempts, "registration", db_account_value)
                if result is not None:
                    return result

            finally:
                if api:
                    await api.close_session()

    async def process_verify(self) -> OperationResult:
        max_attempts = config.attempts_and_delay_settings.max_attempts_to_verify_email
        link_sent = False

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if config.application_settings.skip_logged_accounts and db_account_value and db_account_value.auth_token:
                    logger.warning(f"Account: {self.account_data.email} | Account already logged in, skipped")
                    return operation_failed(self.account_data.email, self.account_data.password)

                proxy, app_id = await self._prepare_account_proxy_and_app_id(db_account_value)
                if not await self._is_email_valid(proxy):
                    return operation_failed(self.account_data.email, self.account_data.password)

                api = DawnExtensionAPI(proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                app_id = await self.process_get_app_id(api=api) if not app_id else app_id
                if not app_id:
                    return operation_failed(self.account_data.email, self.account_data.password)

                if not db_account_value:
                    await Accounts.create_or_update_account(email=self.account_data.email, password=self.account_data.password, app_id=app_id, proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                if not link_sent:
                    logger.info(f"Account: {self.account_data.email} | Sending verification email...")
                    puzzle_id, answer, task_id = await self.get_captcha_data(api=api, captcha_type="image", app_id=app_id)
                    await api.resend_verify_link(email=self.account_data.email, puzzle_id=puzzle_id, answer=answer, app_id=app_id)

                    logger.success(f"Account: {self.account_data.email} | Verification email sent, waiting for email...")
                    link_sent = True

                key = await self._get_confirmation_key(api=api)
                if not key:
                    logger.error(f"Account: {self.account_data.email} | Confirmation link not found | Exported to <<unverified_accounts.txt>>")
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified", log=False)
                    return operation_failed(self.account_data.email, self.account_data.password)

                logger.success(f"Account: {self.account_data.email} | Link found, verifying account..")
                await self._verify_registration(api=api, key=key)

                logger.success(f"Account: {self.account_data.email} | Account verified successfully")
                return operation_success(self.account_data.email, self.account_data.password)

            except APIError as error:
                result = await self.handle_api_error(error, attempt, max_attempts, "verify", db_account_value)
                if result is not None:
                    return result

            except EmailValidationFailed as error:
                if attempt == max_attempts - 1:
                    logger.error(f"Account: {self.account_data.email} | Max attempts reached, unable to verify")
                    return operation_failed(self.account_data.email, self.account_data.password)

                logger.error(f"Account: {self.account_data.email} | {error}")
                await self._update_account_proxy(db_account_value, attempt)

            except Exception as error:
                result = await self.handle_generic_exception(error, attempt, max_attempts, "verify", db_account_value)
                if result is not None:
                    return result

            finally:
                if api:
                    await api.close_session()

    async def process_login(self, check_if_account_logged_in: bool = True) -> OperationResult:
        max_attempts = config.attempts_and_delay_settings.max_login_attempts

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if check_if_account_logged_in is True:
                    if config.application_settings.skip_logged_accounts and db_account_value and db_account_value.auth_token:
                        logger.warning(f"Account: {self.account_data.email} | Account already logged in, skipped")
                        return operation_failed(self.account_data.email, self.account_data.password)

                proxy, app_id = await self._prepare_account_proxy_and_app_id(db_account_value)
                api = DawnExtensionAPI(proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                app_id = await self.process_get_app_id(api=api) if not app_id else app_id
                if not app_id:
                    return operation_failed(self.account_data.email, self.account_data.password)

                if not db_account_value:
                    db_account_value = await Accounts.create_or_update_account(email=self.account_data.email, password=self.account_data.password, app_id=app_id, proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                auth_token = await self._login_account(api=api, app_id=app_id)
                await db_account_value.update_account(auth_token=auth_token)

                logger.success(f"Account: {self.account_data.email} | Account logged in | Session saved to database")
                return operation_success(self.account_data.email, self.account_data.password)

            except APIError as error:
                result = await self.handle_api_error(error, attempt, max_attempts, "login", db_account_value)
                if result is not None:
                    return result

            except Exception as error:
                result = await self.handle_generic_exception(error, attempt, max_attempts, "login", db_account_value)
                if result is not None:
                    return result

            finally:
                if api:
                    await api.close_session()


    async def process_complete_tasks(self) -> OperationResult:
        max_attempts = config.attempts_and_delay_settings.max_tasks_attempts

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if not db_account_value or not db_account_value.auth_token:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unlogged")
                    return operation_failed(self.account_data.email, self.account_data.password)

                proxy, app_id = await self._prepare_account_proxy_and_app_id(db_account_value)
                api = DawnExtensionAPI(auth_token=db_account_value.auth_token, proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                app_id = await self.process_get_app_id(api=api) if not app_id else app_id
                if not app_id:
                    return operation_failed(self.account_data.email, self.account_data.password)

                logger.info(f"Account: {self.account_data.email} | Completing tasks...")
                user_info = await api.user_info(app_id=app_id)
                if all([
                    user_info["rewardPoint"].get("twitter_x_id_points") == 5000,
                    user_info["rewardPoint"].get("discordid_points") == 5000,
                    user_info["rewardPoint"].get("telegramid_points") == 5000
                ]):
                    logger.warning(f"Account: {self.account_data.email} | Tasks already completed")
                    return operation_success(self.account_data.email, self.account_data.password)

                await api.complete_tasks(app_id=app_id)
                logger.success(f"Account: {self.account_data.email} | Tasks completed successfully")
                return operation_success(self.account_data.email, self.account_data.password)

            except APIError as error:
                result = await self.handle_api_error(error, attempt, max_attempts, "tasks", db_account_value)
                if result is not None:
                    return result

            except Exception as error:
                result = await self.handle_generic_exception(error, attempt, max_attempts, "tasks", db_account_value)
                if result is not None:
                    return result

            finally:
                if api:
                    await api.close_session()


    async def process_export_stats(self) -> StatisticData:
        max_attempts = config.attempts_and_delay_settings.max_stats_attempts

        for attempt in range(max_attempts):
            db_account_value = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if not db_account_value or not db_account_value.auth_token:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unlogged")
                    return operation_export_stats_failed()

                proxy, app_id = await self._prepare_account_proxy_and_app_id(db_account_value)
                api = DawnExtensionAPI(auth_token=db_account_value.auth_token, proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                app_id = await self.process_get_app_id(api=api) if not app_id else app_id
                if not app_id:
                    return operation_export_stats_failed()

                logger.info(f"Account: {self.account_data.email} | Exporting accounts stats...")
                user_info = await api.user_info(app_id=app_id)

                logger.success(f"Account: {self.account_data.email} | Account stats retrieved successfully")
                return operation_export_stats_success(user_info)

            except APIError as error:
                result = await self.handle_api_error(error, attempt, max_attempts, "stats", db_account_value)
                if result is not None:
                    return result

            except Exception as error:
                result = await self.handle_generic_exception(error, attempt, max_attempts, "stats", db_account_value)
                if result is not None:
                    return result

            finally:
                if api:
                    await api.close_session()


    async def process_farm(self):
        max_attempts = config.attempts_and_delay_settings.max_attempts_to_send_keepalive

        for attempt in range(max_attempts):
            db_account_value = None
            sleep_duration = None
            api = None

            try:
                db_account_value = await Accounts.get_account(email=self.account_data.email)
                if not db_account_value or not db_account_value.auth_token:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unlogged")
                    return

                proxy, app_id = await self._prepare_account_proxy_and_app_id(db_account_value)
                api = DawnExtensionAPI(auth_token=db_account_value.auth_token, proxy=proxy if isinstance(proxy, str) else proxy.as_url)

                app_id = await self.process_get_app_id(api=api) if not app_id else app_id
                if not app_id:
                    return

                if db_account_value.sleep_until:
                    sleep_duration = await handle_sleep(self.account_data.email, db_account_value.sleep_until)
                    if sleep_duration:
                        return

                logger.info(f"Account: {self.account_data.email} | Sending keepalive...")
                await api.keepalive(self.account_data.email, app_id=app_id)
                logger.success(f"Account: {self.account_data.email} | Keepalive sent successfully")

            except APIError as error:
                result = await self.handle_api_error(error, attempt, max_attempts, "keepalive", db_account_value)
                if result is not None:
                    return

            except Exception as error:
                if "Proxy Authentication Required" in str(error) and config.application_settings.disable_auto_proxy_change:
                    logger.error(f"Account: {self.account_data.email} | Proxy authentication failed | Account deleted from farming")
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "invalid_proxy", invalid_proxy=api.proxy)
                    return

                result = await self.handle_generic_exception(error, attempt, max_attempts, "keepalive", db_account_value)
                if result is not None:
                    return

            finally:
                if sleep_duration is False or sleep_duration is None and db_account_value:
                    duration = timedelta(seconds=config.application_settings.keepalive_interval)
                    utc_duration = datetime.now(pytz.UTC) + duration
                    await db_account_value.set_sleep_until(utc_duration)

                if api:
                    await api.close_session()

