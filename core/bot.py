from datetime import datetime, timedelta
from typing import Tuple, Any, Optional, Literal

import pytz
from loguru import logger
from loader import config, file_operations
from models import Account, OperationResult, StatisticData

from .api import DawnExtensionAPI
from utils import EmailValidator, LinkExtractor
from database import Accounts
from .exceptions.base import APIError, SessionRateLimited, CaptchaSolvingFailed


class Bot(DawnExtensionAPI):
    def __init__(self, account: Account):
        super().__init__(account)

    async def get_captcha_data(self) -> Tuple[str, Any, Optional[Any]]:
        for _ in range(5):
            try:
                puzzle_id = await self.get_puzzle_id()
                image = await self.get_puzzle_image(puzzle_id)

                logger.info(
                    f"Account: {self.account_data.email} | Got puzzle image, solving..."
                )
                answer, solved, *rest = await self.solve_puzzle(image)

                if solved and len(answer) == 6:
                    logger.success(
                        f"Account: {self.account_data.email} | Puzzle solved: {answer}"
                    )
                    return puzzle_id, answer, rest[0] if rest else None

                if len(answer) != 6 and rest:
                    await self.report_invalid_puzzle(rest[0])

                if len(answer) > 30:
                    logger.error(
                        f"Account: {self.account_data.email} | Failed to solve puzzle: {answer} | Retrying..."
                    )
                else:
                    logger.error(
                        f"Account: {self.account_data.email} | Failed to solve puzzle: Incorrect answer | Retrying..."
                    )

            except SessionRateLimited:
                raise

            except Exception as e:
                logger.error(
                    f"Account: {self.account_data.email} | Error occurred while solving captcha: {str(e)} | Retrying..."
                )

        raise CaptchaSolvingFailed("Failed to solve captcha after 5 attempts")

    async def clear_account_and_session(self) -> None:
        if await Accounts.get_account(email=self.account_data.email):
            await Accounts.delete_account(email=self.account_data.email)
        self.session = self.setup_session()


    @staticmethod
    async def handle_invalid_account(email: str, password: str, reason: Literal["unverified", "banned"]) -> None:
        if reason == "unverified":
            logger.error(f"Account: {email} | Email not verified, run re-verify module | Removed from farming")
            await file_operations.export_unverified_email(email, password)

        else:
            logger.error(f"Account: {email} | Account is banned | Removed from farming")
            await file_operations.export_banned_email(email, password)

        for account in config.accounts_to_farm:
            if account.email == email:
                config.accounts_to_farm.remove(account)

    async def process_reverify_email(self, link_sent: bool = False) -> OperationResult:
        task_id = None

        try:
            result = await EmailValidator(
                self.account_data.imap_server if not config.redirect_settings.enabled else config.redirect_settings.imap_server,
                self.account_data.email if not config.redirect_settings.enabled else config.redirect_settings.email,
                self.account_data.password if not config.redirect_settings.enabled else config.redirect_settings.password
            ).validate(None if config.redirect_settings.enabled and not config.redirect_settings.use_proxy else self.account_data.proxy)
            if not result["status"]:
                logger.error(f"Account: {self.account_data.email} | Email is invalid: {result['data']}")
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.info(f"Account: {self.account_data.email} | Re-verifying email...")
            puzzle_id, answer, task_id = await self.get_captcha_data()

            if not link_sent:
                await self.resend_verify_link(puzzle_id, answer)
                logger.info(f"Account: {self.account_data.email} | Successfully resent verification email, waiting for email...")
                link_sent = True

            confirm_url = await LinkExtractor(
                mode="re-verify",
                imap_server=self.account_data.imap_server if not config.redirect_settings.enabled else config.redirect_settings.imap_server,
                email=self.account_data.email if not config.redirect_settings.enabled else config.redirect_settings.email,
                password=self.account_data.password if not config.redirect_settings.enabled else config.redirect_settings.password
            ).extract_link(None if config.redirect_settings.enabled and not config.redirect_settings.use_proxy else self.account_data.proxy)

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

            response = await self.clear_request(url=confirm_url["data"])
            if response.status_code == 200:
                logger.success(
                    f"Account: {self.account_data.email} | Successfully confirmed email"
                )
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=True,
                )

            logger.error(
                f"Account: {self.account_data.email} | Failed to confirm email"
            )


        except APIError as error:
            if error.error_message in error.BASE_MESSAGES:
                if error.error_message == "Incorrect answer. Try again!":
                    logger.warning(
                        f"Account: {self.account_data.email} | Captcha answer incorrect, re-solving..."
                    )
                    if task_id:
                        await self.report_invalid_puzzle(task_id)

                elif error.error_message == "email already exists":
                    logger.warning(f"Account: {self.account_data.email} | Email already exists")
                    return OperationResult(
                        identifier=self.account_data.email,
                        data=self.account_data.password,
                        status=False,
                    )

                else:
                    logger.warning(
                        f"Account: {self.account_data.email} | Captcha expired, re-solving..."
                    )

                return await self.process_reverify_email(link_sent=link_sent)

            logger.error(
                f"Account: {self.account_data.email} | Failed to re-verify email: {error}"
            )

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
            result = await EmailValidator(
                self.account_data.imap_server if not config.redirect_settings.enabled else config.redirect_settings.imap_server,
                self.account_data.email if not config.redirect_settings.enabled else config.redirect_settings.email,
                self.account_data.password if not config.redirect_settings.enabled else config.redirect_settings.password
            ).validate(None if config.redirect_settings.enabled and not config.redirect_settings.use_proxy else self.account_data.proxy)
            if not result["status"]:
                logger.error(f"Account: {self.account_data.email} | Email is invalid: {result['data']}")
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.info(f"Account: {self.account_data.email} | Registering...")
            puzzle_id, answer, task_id = await self.get_captcha_data()

            await self.register(puzzle_id, answer)
            logger.info(
                f"Account: {self.account_data.email} | Successfully registered, waiting for email..."
            )

            confirm_url = await LinkExtractor(
                mode="verify",
                imap_server=self.account_data.imap_server if not config.redirect_settings.enabled else config.redirect_settings.imap_server,
                email=self.account_data.email if not config.redirect_settings.enabled else config.redirect_settings.email,
                password=self.account_data.password if not config.redirect_settings.enabled else config.redirect_settings.password
            ).extract_link(None if config.redirect_settings.enabled and not config.redirect_settings.use_proxy else self.account_data.proxy)

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

            response = await self.clear_request(url=confirm_url["data"])
            if response.status_code == 200:
                logger.success(
                    f"Account: {self.account_data.email} | Successfully confirmed registration"
                )
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=True,
                )

            logger.error(
                f"Account: {self.account_data.email} | Failed to confirm registration"
            )

        except APIError as error:
            if error.error_message in error.BASE_MESSAGES:
                if error.error_message == "Incorrect answer. Try again!":
                    logger.warning(
                        f"Account: {self.account_data.email} | Captcha answer incorrect, re-solving..."
                    )
                    if task_id:
                        await self.report_invalid_puzzle(task_id)

                elif error.error_message == "email already exists":
                    logger.warning(f"Account: {self.account_data.email} | Email already exists")
                    return OperationResult(
                        identifier=self.account_data.email,
                        data=self.account_data.password,
                        status=False,
                    )

                elif error.error_message == "Something went wrong #BR4":
                    logger.warning(f"Account: {self.account_data.email} | Most likely email domain <{self.account_data.email.split('@')[1]}> is banned")
                    return OperationResult(
                        identifier=self.account_data.email,
                        data=self.account_data.password,
                        status=False,
                    )

                else:
                    logger.warning(
                        f"Account: {self.account_data.email} | Captcha expired, re-solving..."
                    )
                return await self.process_registration()

            logger.error(
                f"Account: {self.account_data.email} | Failed to register: {error}"
            )

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

            if not db_account_data or not db_account_data.headers:
                if not await self.login_new_account():
                    return

            elif not await self.handle_existing_account(db_account_data):
                return

            await self.perform_farming_actions()

        except SessionRateLimited:
            await self.handle_session_blocked()

        except APIError as error:
            if error.error_message == "Email not verified , Please check spam folder incase you did not get email":
                await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified")
            elif error.error_message == "Something went wrong #BRL4":
                await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")
            else:
                logger.error(
                    f"Account: {self.account_data.email} | Failed to farm: {error}"
                )


        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to farm: {error}"
            )

        return

    async def process_get_user_info(self) -> StatisticData:
        try:
            db_account_data = await Accounts.get_account(email=self.account_data.email)

            if db_account_data and db_account_data.session_blocked_until:
                if await self.handle_sleep(db_account_data.session_blocked_until):
                    return StatisticData(
                        success=False, referralPoint=None, rewardPoint=None
                    )

            if not db_account_data or not db_account_data.headers:
                if not await self.login_new_account():
                    return StatisticData(
                        success=False, referralPoint=None, rewardPoint=None
                    )

            elif not await self.handle_existing_account(db_account_data):
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
                await self.handle_existing_account(db_account_data)

            logger.info(f"Account: {self.account_data.email} | Completing tasks...")
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
            puzzle_id, answer, task_id = await self.get_captcha_data()

            await self.login(puzzle_id, answer)
            logger.info(f"Account: {self.account_data.email} | Successfully logged in")

            await Accounts.create_account(
                email=self.account_data.email, headers=self.session.headers
            )
            return True

        except APIError as error:
            if error.error_message in error.BASE_MESSAGES:
                if error.error_message == "Incorrect answer. Try again!":
                    logger.warning(
                        f"Account: {self.account_data.email} | Captcha answer incorrect, re-solving..."
                    )
                    if task_id:
                        await self.report_invalid_puzzle(task_id)

                elif error.error_message == "Email not verified , Please check spam folder incase you did not get email":
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "unverified")
                    return False

                elif error.error_message == "Something went wrong #BRL4":
                    await self.handle_invalid_account(self.account_data.email, self.account_data.password, "banned")
                    return False

                else:
                    logger.warning(
                        f"Account: {self.account_data.email} | Captcha expired, re-solving..."
                    )

                return await self.login_new_account()

            logger.error(
                f"Account: {self.account_data.email} | Failed to login: {error}"
            )
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

    async def handle_existing_account(self, db_account_data) -> bool | None:
        if db_account_data.sleep_until and await self.handle_sleep(
            db_account_data.sleep_until
        ):
            return False

        self.session.headers = db_account_data.headers
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
        await Accounts.set_session_blocked_until(self.account_data.email, sleep_until)

    async def handle_sleep(self, sleep_until):
        current_time = datetime.now(pytz.UTC)
        sleep_until = sleep_until.replace(tzinfo=pytz.UTC)

        if sleep_until > current_time:
            sleep_duration = (sleep_until - current_time).total_seconds()
            logger.debug(
                f"Account: {self.account_data.email} | Sleeping until {sleep_until} (duration: {sleep_duration:.2f} seconds)"
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
