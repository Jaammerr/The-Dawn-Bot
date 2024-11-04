from datetime import datetime, timedelta
from typing import Tuple, Any, Optional

import pytz
from loguru import logger
from loader import config, file_operations
from models import Account, OperationResult, StatisticData

from .api import DawnExtensionAPI
from utils import check_email_for_link, check_if_email_valid
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

    async def process_reverify_email(self) -> OperationResult:
        await self.clear_account_and_session()

        try:
            confirm_url = await check_email_for_link(
                imap_server=self.account_data.imap_server,
                email=self.account_data.email,
                password=self.account_data.password,
            )

            if confirm_url is None:
                logger.error(
                    f"Account: {self.account_data.email} | Confirmation link not found"
                )
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.success(
                f"Account: {self.account_data.email} | Link found, confirming registration..."
            )
            response = await self.clear_request(url=confirm_url)
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
            if not await check_if_email_valid(
                self.account_data.imap_server,
                self.account_data.email,
                self.account_data.password,
            ):
                logger.error(f"Account: {self.account_data.email} | Invalid email")
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

            confirm_url = await check_email_for_link(
                imap_server=self.account_data.imap_server,
                email=self.account_data.email,
                password=self.account_data.password,
            )

            if confirm_url is None:
                logger.error(
                    f"Account: {self.account_data.email} | Confirmation link not found"
                )
                return OperationResult(
                    identifier=self.account_data.email,
                    data=self.account_data.password,
                    status=False,
                )

            logger.success(
                f"Account: {self.account_data.email} | Link found, confirming registration..."
            )
            response = await self.clear_request(url=confirm_url)
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
                    logger.warning(f"Account: {self.account_data.email} | Email already exists, re-verifying...")
                    return await self.process_reverify_email()

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
                    logger.error(
                        f"Account: {self.account_data.email} | Email not verified, run registration process again"
                    )

                    await file_operations.export_unverified_email(self.account_data.email, self.account_data.password)
                    for account in config.accounts_to_farm:
                        if account.email == self.account_data.email:
                            config.accounts_to_farm.remove(account)

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
