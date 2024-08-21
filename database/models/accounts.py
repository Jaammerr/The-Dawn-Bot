import pytz

from datetime import datetime
from tortoise import Model, fields
from loguru import logger


class Accounts(Model):
    email = fields.CharField(max_length=255, unique=True)
    headers = fields.JSONField(null=True)
    sleep_until = fields.DatetimeField(null=True)
    wallet_private_key = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "dawn_accounts"

    @classmethod
    async def get_account(cls, email: str):
        return await cls.get_or_none(email=email)

    @classmethod
    async def get_accounts(cls):
        return await cls.all()

    @classmethod
    async def create_account(
        cls, email: str, headers: dict = None, wallet_private_key: str = None
    ):
        account = await cls.get_account(email=email)
        if account is None:
            account = await cls.create(
                email=email, headers=headers, wallet_private_key=wallet_private_key
            )
            return account
        else:
            account.headers = headers
            account.wallet_private_key = wallet_private_key
            await account.save()
            return account


    @classmethod
    async def get_account_private_key(cls, email: str):
        account = await cls.get_account(email=email)
        if account is None:
            return None

        return account.wallet_private_key

    @classmethod
    async def set_account_private_key(cls, email: str, private_key: str):
        account = await cls.get_account(email=email)
        if account is None:
            return False

        account.wallet_private_key = private_key
        await account.save()
        return True

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
