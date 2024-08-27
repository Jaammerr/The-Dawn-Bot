import asyncio
from datetime import datetime, timedelta

import pytz
from loguru import logger
from loader import config
from models import Account

from .api import DawnExtensionAPI
from utils import check_email_for_link, check_if_email_valid
from database import Accounts
from .exceptions.base import APIError


class Bot(DawnExtensionAPI):
    def __init__(self, account: Account):
        super().__init__(account)

    async def get_captcha_data(self) -> tuple[str, str]:
        while True:
            puzzle_id = await self.get_puzzle_id()
            image = await self.get_puzzle_image(puzzle_id)
            logger.info(
                f"Account: {self.account_data.email} | Got puzzle image, solving..."
            )
            answer, solved = await self.solve_puzzle(image)
            if solved:
                logger.success(
                    f"Account: {self.account_data.email} | Puzzle solved: {answer}"
                )
                return puzzle_id, answer
            logger.error(
                f"Account: {self.account_data.email} | Failed to solve puzzle: {answer} | Retrying..."
            )

    async def process_registration(self):
        try:
            if not await check_if_email_valid(
                self.account_data.imap_server,
                self.account_data.email,
                self.account_data.password,
            ):
                logger.error(f"Account: {self.account_data.email} | Invalid email")
                return False

            logger.info(f"Account: {self.account_data.email} | Registering...")
            puzzle_id, answer = await self.get_captcha_data()

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
                return False

            logger.success(
                f"Account: {self.account_data.email} | Link found, confirming registration..."
            )
            response = await self.clear_request(url=confirm_url)
            if response.status_code == 200:
                logger.success(
                    f"Account: {self.account_data.email} | Successfully confirmed registration"
                )
                return True

            logger.error(
                f"Account: {self.account_data.email} | Failed to confirm registration"
            )
            return False

        except APIError as error:
            if error.error_message in error.BASE_MESSAGES:
                logger.warning(
                    f"Account: {self.account_data.email} | Captcha expired or answer incorrect, re-solving..."
                )
                return await self.process_registration()

            logger.error(f"Account: {self.account_data.email} | Failed to register: {error}")

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to register: {error}"
            )
            return False

    @staticmethod
    def get_sleep_until() -> datetime:
        return datetime.now(pytz.UTC) + timedelta(seconds=config.keepalive_interval)

    async def process_farming(self):
        try:
            db_account_data = await Accounts.get_account(email=self.account_data.email)
            if db_account_data is None or db_account_data.headers is None:
                await self.login_new_account()
            else:
                await self.handle_existing_account(db_account_data)

            if not await Accounts.get_account_private_key(
                email=self.account_data.email
            ):
                await Accounts.set_account_private_key(
                    email=self.account_data.email,
                    private_key=(
                        self.wallet_data["wallet_private_key"]
                        if self.wallet_data
                        else None
                    ),
                )

            await self.perform_farming_actions()

        except APIError as error:
            if error.error_message in error.BASE_MESSAGES:
                logger.warning(
                    f"Account: {self.account_data.email} | Captcha expired or answer incorrect, re-solving..."
                )
                return await self.process_farming()

            logger.error(f"Account: {self.account_data.email} | Failed to farm: {error}")

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to farm: {error}"
            )

        return False

    async def process_complete_tasks(self):
        try:
            db_account_data = await Accounts.get_account(email=self.account_data.email)
            if db_account_data is None:
                await self.login_new_account()
            else:
                await self.handle_existing_account(db_account_data, check_sleep=False)

            logger.info(f"Account: {self.account_data.email} | Completing tasks...")
            await self.complete_tasks()
            logger.success(
                f"Account: {self.account_data.email} | Successfully completed tasks"
            )

        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to complete tasks: {error}"
            )

    async def login_new_account(self):
        logger.info(f"Account: {self.account_data.email} | Logging in...")
        puzzle_id, answer = await self.get_captcha_data()
        await self.login(puzzle_id, answer)
        logger.info(f"Account: {self.account_data.email} | Successfully logged in")
        await Accounts.create_account(
            email=self.account_data.email, headers=self.session.headers
        )

    async def handle_existing_account(self, db_account_data, check_sleep: bool = True):
        if check_sleep:
            if db_account_data.sleep_until is not None:
                await self.handle_sleep(db_account_data.sleep_until)

        self.session.headers = db_account_data.headers
        if not await self.verify_session():
            logger.warning(
                f"Account: {self.account_data.email} | Session is invalid, re-logging in..."
            )
            await Accounts.delete_account(email=self.account_data.email)
            return await self.process_farming()

        logger.info(f"Account: {self.account_data.email} | Using existing session")

    async def handle_sleep(self, sleep_until):
        current_time = datetime.now(pytz.UTC)
        sleep_until = sleep_until.replace(tzinfo=pytz.UTC)

        if sleep_until > current_time:
            sleep_duration = (sleep_until - current_time).total_seconds()
            logger.debug(
                f"Account: {self.account_data.email} | Sleeping until {sleep_until} (duration: {sleep_duration:.2f} seconds)"
            )
            await asyncio.sleep(sleep_duration)

    async def export_account_wallet(self) -> str:
        return await Accounts.get_account_private_key(email=self.account_data.email)

    async def close_session(self):
        try:
            await self.session.close()
        except Exception as error:
            logger.debug(f"Account: {self.account_data.email} | Failed to close session: {error}")

    async def perform_farming_actions(self):
        await self.keepalive()
        logger.success(f"Account: {self.account_data.email} | Sent keepalive request")

        try:
            user_info = await self.user_info()
            logger.info(
                f"Account: {self.account_data.email} | Total points earned: {user_info['rewardPoint']['points']}"
            )
        except Exception as error:
            logger.error(
                f"Account: {self.account_data.email} | Failed to get user info: {error}"
            )

        finally:
            new_sleep_until = self.get_sleep_until()
            await Accounts.set_sleep_until(
                email=self.account_data.email, sleep_until=new_sleep_until
            )

