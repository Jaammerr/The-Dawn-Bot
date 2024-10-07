import pytz

from datetime import datetime
from tortoise import Model, fields
from loguru import logger


class Accounts(Model):
    email = fields.CharField(max_length=255, unique=True)
    headers = fields.JSONField(null=True)
    sleep_until = fields.DatetimeField(null=True)
    session_blocked_until = fields.DatetimeField(null=True)

    class Meta:
        table = "dawn_accounts_v1.4"

    @classmethod
    async def get_account(cls, email: str):
        return await cls.get_or_none(email=email)

    @classmethod
    async def get_accounts(cls):
        return await cls.all()

    @classmethod
    async def create_account(cls, email: str, headers: dict = None):
        account = await cls.get_account(email=email)
        if account is None:
            account = await cls.create(email=email, headers=headers)
            return account
        else:
            account.headers = headers
            await account.save()
            return account

    @classmethod
    async def delete_account(cls, email: str):
        account = await cls.get_account(email=email)
        if account is None:
            return False

        await account.delete()
        return True

    @classmethod
    async def set_sleep_until(cls, email: str, sleep_until: datetime):
        account = await cls.get_account(email=email)
        if account is None:
            return False

        if sleep_until.tzinfo is None:
            sleep_until = pytz.UTC.localize(sleep_until)
        else:
            sleep_until = sleep_until.astimezone(pytz.UTC)

        account.sleep_until = sleep_until
        await account.save()
        logger.info(f"Account: {email} | Set new sleep_until: {sleep_until}")
        return True

    @classmethod
    async def set_session_blocked_until(
        cls, email: str, session_blocked_until: datetime
    ):
        account = await cls.get_account(email=email)
        if account is None:
            account = await cls.create_account(email=email)
            account.session_blocked_until = session_blocked_until
            await account.save()
            logger.info(
                f"Account: {email} | Set new session_blocked_until: {session_blocked_until}"
            )
            return

        if session_blocked_until.tzinfo is None:
            session_blocked_until = pytz.UTC.localize(session_blocked_until)
        else:
            session_blocked_until = session_blocked_until.astimezone(pytz.UTC)

        account.session_blocked_until = session_blocked_until
        await account.save()
        logger.info(
            f"Account: {email} | Set new session_blocked_until: {session_blocked_until}"
        )
