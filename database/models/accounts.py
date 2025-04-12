import asyncio
import pytz

from datetime import datetime
from tortoise import Model, fields


class Accounts(Model):
    email = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255, null=True)
    app_id = fields.CharField(max_length=50, null=True)
    auth_token = fields.CharField(max_length=1024, null=True)

    active_account_proxy = fields.CharField(max_length=255, null=True)
    sleep_until = fields.DatetimeField(null=True)

    class Meta:
        table = "dawn_accounts_v1.9"

    @classmethod
    async def get_account(cls, email: str):
        return await cls.get_or_none(email=email)

    @classmethod
    async def get_accounts(cls):
        return await cls.all()


    async def update_account_proxy(self, proxy: str):
        self.active_account_proxy = proxy
        await self.save()

    @classmethod
    async def get_account_proxy(cls, email: str) -> str:
        account = await cls.get_account(email=email)
        if account:
            return account.active_account_proxy

        return ""

    @classmethod
    async def create_or_update_account(cls, email: str, password: str = None, app_id: str = None, auth_token: str = None, proxy: str = None) -> "Accounts":
        account = await cls.get_account(email=email)
        if account is None:
            account = await cls.create(
                email=email,
                password=password,
                auth_token=auth_token,
                app_id=app_id,
                active_account_proxy=proxy,
            )
            return account
        else:
            if password:
                account.password = password
            if app_id:
                account.app_id = app_id
            if auth_token:
                account.auth_token = auth_token
            if proxy:
                account.active_account_proxy = proxy

            await account.save()
            return account

    async def update_account(self, password: str = None, app_id: str = None, auth_token: str = None, proxy: str = None) -> "Accounts":
        if password:
            self.password = password
        if app_id:
            self.app_id = app_id
        if auth_token:
            self.auth_token = auth_token
        if proxy:
            self.active_account_proxy = proxy

        await self.save()
        return self

    @classmethod
    async def get_app_id(cls, email: str) -> str | None:
        account = await cls.get_account(email=email)
        if account is None:
            return None

        return account.app_id

    @classmethod
    async def get_auth_token(cls, email: str) -> str | None:
        account = await cls.get_account(email=email)
        if account is None:
            return None

        return account.auth_token

    @classmethod
    async def delete_account(cls, email: str) -> bool:
        account = await cls.get_account(email=email)
        if account is None:
            return False

        await account.delete()
        return True

    async def set_sleep_until(self, sleep_until: datetime) -> "Accounts":
        if not isinstance(sleep_until, datetime):
            raise ValueError("sleep_until must be a datetime object")

        if sleep_until.tzinfo is None:
            sleep_until = pytz.UTC.localize(sleep_until)
        else:
            sleep_until = sleep_until.astimezone(pytz.UTC)

        self.sleep_until = sleep_until
        await self.save()
        return self

    async def clear_all_accounts_proxies(self) -> int:
        async def clear_proxy(account: Accounts):
            async with asyncio.Semaphore(500):
                if account.active_account_proxy:
                    account.active_account_proxy = None
                    await account.save()

        accounts = await self.all()
        tasks = [asyncio.create_task(clear_proxy(account)) for account in accounts]
        await asyncio.gather(*tasks)

        return len(accounts)
