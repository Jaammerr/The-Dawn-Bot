from datetime import datetime, timedelta
from typing import Tuple, Any, Optional, Literal

import pytz
from loguru import logger
from loader import config, file_operations, captcha_solver, headers_manager
from models import Account, OperationResult, StatisticData

from .api import DawnExtensionAPI
from utils import EmailValidator, LinkExtractor
from database import Accounts
from .exceptions.base import APIError, SessionRateLimited, CaptchaSolvingFailed, APIErrorType


class Bot(DawnExtensionAPI):
    def __init__(self, account: Account):
        super().__init__(account)

    async def get_captcha_data(self, captcha_type: Literal["image", "turnistale"]) -> Tuple[str, Any, Optional[Any]] | str:
        for _ in range(5):
            try:
                if captcha_type == "image":
                    puzzle_id = await self.get_puzzle_id()
                    image = await self.get_puzzle_image(puzzle_id)

                    logger.info(
                        f"Account: {self.account_data.email} | Got puzzle image, solving..."
                    )
                    answer, solved, *rest = await captcha_solver.solve_image(image)

                    if solved and len(answer) == 6:
                        logger.success(
                            f"Account: {self.account_data.email} | Puzzle solved: {answer}"
                        )
                        return puzzle_id, answer, rest[0] if rest else None

                    if len(answer) != 6 and rest:
                        await captcha_solver.report_bad(rest[0])

                    logger.error(
                        f"Account: {self.account_data.email} | Failed to solve puzzle: {answer} | Retrying..."
                    )

                elif captcha_type == "turnistale":
                    logger.info(f"Account: {self.account_data.email} | Solving Cloudflare challenge...")
                    answer, solved, *rest = await captcha_solver.solve_turnistale()

                    if solved:
                        logger.success(
                            f"Account: {self.account_data.email} | Cloudflare challenge solved"
                        )
                        return answer

                    logger.error(
                        f"Account: {self.account_data.email} | Failed to solve Cloudflare challenge: {answer} | Retrying..."
                    )

            except SessionRateLimited:
                raise

            except Exception as e:
                logger.error(
                    f"Account: {self.account_data.email} | Error occurred while solving captcha ({captcha_type}): {str(e)} | Retrying..."
                )

        raise CaptchaSolvingFailed("Failed to solve captcha after 5 attempts")

    async def clear_account_and_session(self) -> None:
        if await Accounts.get_account(email=self.account_data.email):
            await Accounts.delete_account(email=self.account_data.email)
        self.session = self._create_session()


    @staticmethod
    async def handle_invalid_account(email: str, password: str, reason: Literal["unverified", "banned", "unregistered"]) -> None:
        if reason == "unverified":
            logger.error(f"Account: {email} | Email not verified, run re-verify module | Removed from farming")
            await file_operations.export_unverified_email(email, password)

        elif reason == "banned":
            logger.error(f"Account: {email} | Account is banned | Removed from list")
            await file_operations.export_banned_email(email, password)

        elif reason == "unregistered":
            logger.error(f"Account: {email} | Account is not registered | Removed from list")
            await file_operations.export_unregistered_email(email, password)

        for account in config.accounts_to_farm:
            if account.email == email:
                config.accounts_to_farm.remove(account)


    async def _validate_email(self) -> dict:
        if config.redirect_settings.enabled:
            result = await EmailValidator(
                config.redirect_settings.imap_server,
                config.redirect_settings.email,
                config.redirect_settings.password
            ).validate(None if config.redirect_settings.use_proxy is False else self.account_data.proxy)
        else:
            result = await EmailValidator(
                self.account_data.imap_server,
                self.account_data.email,
                self.account_data.password
            ).validate(None if config.use_proxy_for_imap is False else self.account_data.proxy)

        return result


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
            ).extract_link(None if config.redirect_settings.use_proxy is False else self.account_data.proxy)

        return confirm_url

    async def process_reverify_email(self, link_sent: bool = False) -> OperationResult:
        task_id = None

        try:
            result = await self._validate_email()
            if not result["status"]:
                logger.error(f"Account: {self.account_data.email} | Email is invalid: {result['data']}")
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.info(f"Account: {self.account_data.email} | Re-verifying email...")
            puzzle_id, answer, task_id = await self.get_captcha_data("image")

            if not link_sent:
                await self.resend_verify_link(puzzle_id, answer)
                logger.info(f"Account: {self.account_data.email} | Successfully resent verification email, waiting for email...")
                link_sent = True

            confirm_url = await self._extract_link()
            if not confirm_url["status"]:
                logger.error(f"Account: {self.account_data.email} | Confirmation link not found: {confirm_url['data']}")
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.success(
                f"Account: {self.account_data.email} | Link found, confirming email..."
            )

            try:
                key = confirm_url["data"].split("key=")[1]
            except IndexError:
                response = await self.clear_request(confirm_url["data"])
                key = response.url.split("key=")[1]

            cloudflare_token = await self.get_captcha_data("turnistale")
            await self.verify_registration(key, cloudflare_token)

            logger.success(f"Email verified successfully")
            return OperationResult(
                identifier=self.account_data.email,
                data=self.account_data.password,
                status=True,
            )

        except APIError as error:
            match error.error_type:
                case APIErrorType.INCORRECT_CAPTCHA:
                    logger.warning(f"Account: {self.account_data.email} | Captcha answer incorrect, re-solving...")
                    if task_id:
                        await captcha_solver.report_bad(task_id)
                    return await self.process_reverify_email(link_sent=link_sent)

                case APIErrorType.EMAIL_EXISTS:
                    logger.warning(f"Account: {self.account_data.email} | Email already exists")

                case APIErrorType.CAPTCHA_EXPIRED:
                    logger.warning(f"Account: {self.account_data.email} | Captcha expired, re-solving...")
                    return await self.process_reverify_email(link_sent=link_sent)

                case APIErrorType.SESSION_EXPIRED:
                    logger.warning(f"Account: {self.account_data.email} | Session expired, re-logging in...")
                    await self.clear_account_and_session()
                    return await self.process_reverify_email(link_sent=link_sent)

                case _:
                    logger.error(f"Account: {self.account_data.email} | Failed to re-verify email: {error}")

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to reverify email: {error}"
            )

        return OperationResult(
            identifier=self.account_data.email,
            data=self.account_data.password,
            status=False,
        )


    async def process_registration(self) -> OperationResult:
        task_id = None

        try:
            result = await self._validate_email()
            if not result["status"]:
                logger.error(f"Account: {self.account_data.email} | Email is invalid: {result['data']}")
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.info(f"Account: {self.account_data.email} | Registering...")
            puzzle_id, answer, task_id = await self.get_captcha_data("image")

            await self.register(puzzle_id, answer)
            logger.info(
                f"Account: {self.account_data.email} | Registered, waiting for email..."
            )

            confirm_url = await self._extract_link()
            if not confirm_url["status"]:
                logger.error(f"Account: {self.account_data.email} | Confirmation link not found: {confirm_url['data']}")
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.success(
                f"Account: {self.account_data.email} | Link found, confirming registration..."
            )

            try:
                key = confirm_url["data"].split("key=")[1]
            except IndexError:
                response = await self.clear_request(confirm_url["data"])
                key = response.url.split("key=")[1]

            cloudflare_token = await self.get_captcha_data("turnistale")
            await self.verify_registration(key, cloudflare_token)

            logger.success(f"Registration verified and completed")
            return OperationResult(
                identifier=self.account_data.email,
                data=self.account_data.password,
                status=True,
            )


        except APIError as error:
            match error.error_type:
                case APIErrorType.INCORRECT_CAPTCHA:
                    logger.warning(f"Account: {self.account_data.email} | Captcha answer incorrect, re-solving...")
                    if task_id:
                        await captcha_solver.report_bad(task_id)
                    return await self.process_registration()

                case APIErrorType.EMAIL_EXISTS:
                    logger.warning(f"Account: {self.account_data.email} | Email already exists")

                case APIErrorType.CAPTCHA_EXPIRED:
                    logger.warning(f"Account: {self.account_data.email} | Captcha expired, re-solving...")
                    return await self.process_registration()

                case _:
                    if "Something went wrong" in error.error_message:
                        logger.warning(f"Account: {self.account_data.email} | Most likely email domain <{self.account_data.email.split('@')[1]}> is banned")
                    else:
                        logger.error(f"Account: {self.account_data.email} | Failed to register: {error}")

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to register: {error}"
            )

        return OperationResult(
            identifier=self.account_data.email,
            data=self.account_data.password,
            status=False,
        )

    @staticmethod
    def get_sleep_until(blocked: bool = False) -> datetime:
        duration = (
            timedelta(minutes=10)
            if blocked
            else timedelta(seconds=config.keepalive_interval)
        )
        return datetime.now(pytz.UTC) + duration

    async def process_farming(self) -> None:
        try:
            db_account_data = await Accounts.get_account(email=self.account_data.email)

            if db_account_data and db_account_data.session_blocked_until:
                if await self.handle_sleep(db_account_data.session_blocked_until):
                    return

            if not db_account_data or not db_account_data.auth_token:
                if not await self.login_new_account():
                    return

            elif not await self.handle_existing_account(db_account_data):
                return

            await self.perform_farming_actions()

        except SessionRateLimited:
            await self.handle_session_blocked()


        except APIError as error:
            match error.error_type:
                case APIErrorType.UNVERIFIED_EMAIL:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified")

                case APIErrorType.BANNED:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")

                case APIErrorType.UNREGISTERED_EMAIL:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unregistered")

                case APIErrorType.SESSION_EXPIRED:
                    logger.warning(f"Account: {self.account_data.email} | Session expired, re-logging in...")
                    await self.clear_account_and_session()
                    return await self.process_farming()

                case _:
                    if "Something went wrong" in error.error_message:
                        await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")
                    else:
                        logger.error(f"Account: {self.account_data.email} | Failed to farm: {error}")


        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to farm: {error}"
            )

        return

    async def process_get_user_info(self) -> StatisticData:
        try:
            db_account_data = await Accounts.get_account(email=self.account_data.email)

            if not db_account_data or not db_account_data.auth_token:
                if not await self.login_new_account():
                    return StatisticData(
                        success=False, referralPoint=None, rewardPoint=None
                    )

            elif not await self.handle_existing_account(db_account_data, verify_sleep=False):
                return StatisticData(
                    success=False, referralPoint=None, rewardPoint=None
                )

            user_info = await self.user_info()
            logger.success(
                f"Account: {self.account_data.email} | Successfully got user info"
            )
            return StatisticData(
                success=True,
                referralPoint=user_info["referralPoint"],
                rewardPoint=user_info["rewardPoint"],
            )

        except SessionRateLimited:
            await self.handle_session_blocked()

        except APIError as error:
            match error.error_type:
                case APIErrorType.UNVERIFIED_EMAIL:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified")

                case APIErrorType.BANNED:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")

                case APIErrorType.UNREGISTERED_EMAIL:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unregistered")

                case APIErrorType.SESSION_EXPIRED:
                    logger.warning(f"Account: {self.account_data.email} | Session expired, re-logging in...")
                    await self.clear_account_and_session()
                    return await self.process_get_user_info()

                case _:
                    if "Something went wrong" in error.error_message:
                        await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")
                    else:
                        logger.error(
                            f"Account: {self.account_data.email} | Failed to get user info: {error}"
                        )

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to get user info: {error}"
            )

        return StatisticData(success=False, referralPoint=None, rewardPoint=None)

    async def process_complete_tasks(self) -> OperationResult:
        try:
            db_account_data = await Accounts.get_account(email=self.account_data.email)
            if db_account_data is None:
                if not await self.login_new_account():
                    return OperationResult(
                        identifier=self.account_data.email,
                        data=self.account_data.password,
                        status=False,
                    )
            else:
                await self.handle_existing_account(db_account_data, verify_sleep=False)

            logger.info(f"Account: {self.account_data.email} | Completing tasks... | It may take a while")
            await self.complete_tasks()

            logger.success(
                f"Account: {self.account_data.email} | Successfully completed tasks"
            )
            return OperationResult(
                identifier=self.account_data.email,
                data=self.account_data.password,
                status=True,
            )

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to complete tasks: {error}"
            )
            return OperationResult(
                identifier=self.account_data.email,
                data=self.account_data.password,
                status=False,
            )

    async def login_new_account(self):
        task_id = None

        try:
            logger.info(f"Account: {self.account_data.email} | Logging in...")
            puzzle_id, answer, task_id = await self.get_captcha_data("image")

            await self.login(puzzle_id, answer)
            logger.info(f"Account: {self.account_data.email} | Successfully logged in")

            await Accounts.create_account(email=self.account_data.email, app_id=self.account_data.appid, auth_token=headers_manager.BEARER_TOKEN)
            return True

        except APIError as error:
            match error.error_type:
                case APIErrorType.INCORRECT_CAPTCHA:
                    logger.warning(f"Account: {self.account_data.email} | Captcha answer incorrect, re-solving...")
                    if task_id:
                        await captcha_solver.report_bad(task_id)
                    return await self.login_new_account()

                case APIErrorType.UNVERIFIED_EMAIL:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified")
                    return False

                case APIErrorType.UNREGISTERED_EMAIL:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unregistered")
                    return False

                case APIErrorType.BANNED:
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")
                    return False

                case APIErrorType.CAPTCHA_EXPIRED:
                    logger.warning(f"Account: {self.account_data.email} | Captcha expired, re-solving...")
                    return await self.login_new_account()

                case _:
                    if "Something went wrong" in error.error_message:
                        await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")
                    else:
                        logger.error(f"Account: {self.account_data.email} | Failed to login: {error}")

                    return False

        except CaptchaSolvingFailed:
            sleep_until = self.get_sleep_until()
            await Accounts.set_sleep_until(self.account_data.email, sleep_until)
            logger.error(
                f"Account: {self.account_data.email} | Failed to solve captcha after 5 attempts, sleeping..."
            )
            return False

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to login: {error}"
            )
            return False

    async def handle_existing_account(self, db_account_data, verify_sleep: bool = True) -> bool | None:
        if verify_sleep:
            if db_account_data.sleep_until and await self.handle_sleep(
                db_account_data.sleep_until
            ):
                return False

        headers_manager.BEARER_TOKEN = db_account_data.auth_token
        status, result = await self.verify_session()
        if not status:
            logger.warning(
                f"Account: {self.account_data.email} | Session is invalid, re-logging in: {result}"
            )
            await self.clear_account_and_session()
            return await self.process_farming()

        logger.info(f"Account: {self.account_data.email} | Using existing session")
        return True

    async def handle_session_blocked(self):
        await self.clear_account_and_session()
        logger.error(
            f"Account: {self.account_data.email} | Session rate-limited | Sleeping..."
        )
        sleep_until = self.get_sleep_until(blocked=True)
        await Accounts.set_session_blocked_until(email=self.account_data.email, session_blocked_until=sleep_until, app_id=self.account_data.appid)

    async def handle_sleep(self, sleep_until):
        current_time = datetime.now(pytz.UTC)
        sleep_until = sleep_until.replace(tzinfo=pytz.UTC)

        if sleep_until > current_time:
            sleep_duration = (sleep_until - current_time).total_seconds()
            logger.debug(
                f"Account: {self.account_data.email} | Sleeping until next action {sleep_until} (duration: {sleep_duration:.2f} seconds)"
            )
            return True

        return False

    async def close_session(self):
        try:
            await self.session.close()
        except Exception as error:
            logger.debug(
                f"Account: {self.account_data.email} | Failed to close session: {error}"
            )

    async def perform_farming_actions(self):
        try:
            await self.keepalive()
            logger.success(
                f"Account: {self.account_data.email} | Sent keepalive request"
            )

            user_info = await self.user_info()
            logger.info(
                f"Account: {self.account_data.email} | Total points earned: {user_info['rewardPoint']['points']}"
            )

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to perform farming actions: {error}"
            )

        finally:
            new_sleep_until = self.get_sleep_until()
            await Accounts.set_sleep_until(
                email=self.account_data.email, sleep_until=new_sleep_until
            )
